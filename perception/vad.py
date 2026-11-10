"""流式 VAD：把连续音频切成一句话，供 ASR / SER 使用。

不依赖外部模型：帧能量 + 自适应噪声底。对演示场景（一个近距离麦克风、安静房间）
足够用，而且没有额外的模型下载和延迟。切句规则：

- 连续 speech_ms 以上超过阈值 -> 开始一句话
- 连续 silence_ms 静音 -> 结束（尾部静音裁掉，只留 100ms）
- 单句最长 max_ms（06-实验报告 3.3：长音频会让注意力显存爆掉）
"""
from __future__ import annotations

import math

import numpy as np


def _db(x: np.ndarray) -> float:
    rms = float(np.sqrt(np.mean(np.square(x), dtype=np.float64) + 1e-12))
    return 20.0 * math.log10(rms + 1e-9)


class VADSegmenter:
    def __init__(self, sr: int = 16000, frame_ms: int = 30, start_db: float = -42.0,
                 margin_db: float = 9.0, hysteresis_db: float = 4.0,
                 silence_ms: int = 500, min_ms: int = 400, max_ms: int = 15000):
        self.sr = sr
        self.frame_len = int(sr * frame_ms / 1000)
        self.frame_ms = frame_ms
        self.start_db = start_db
        self.margin_db = margin_db
        self.hysteresis_db = hysteresis_db
        self.silence_frames = max(1, silence_ms // frame_ms)
        self.min_frames = max(1, min_ms // frame_ms)
        self.max_frames = max(self.min_frames, max_ms // frame_ms)

        self._buf = np.zeros(0, dtype=np.float32)
        self._frames: list[np.ndarray] = []
        self._silence = 0
        self.in_speech = False
        self.noise_db: float | None = None    # 非语音帧的能量滑动平均

    def _threshold(self) -> float:
        if self.noise_db is None:
            return self.start_db
        return max(self.start_db, self.noise_db + self.margin_db)

    def _reset(self):
        self._frames = []
        self._silence = 0
        self.in_speech = False

    def reset(self):
        """外部强制丢弃半句话（回声门控打开时用）。"""
        self._reset()

    def _finish(self, forced: bool = False) -> np.ndarray | None:
        frames = self._frames
        if not forced:
            # 去掉尾部静音，保留 100ms 自然收尾
            keep_tail = max(1, 100 // self.frame_ms)
            while len(frames) > self.min_frames and self._silence > keep_tail:
                frames.pop()
                self._silence -= 1
        self._reset()
        if len(frames) < self.min_frames:
            return None
        return np.concatenate(frames).astype(np.float32)

    def push(self, chunk: np.ndarray) -> list[np.ndarray]:
        """喂任意长度的 float32 音频，返回本次新切出的完整句子（可能 0 条或多条）。"""
        out: list[np.ndarray] = []
        if chunk is None or len(chunk) == 0:
            return out
        self._buf = np.concatenate([self._buf, np.asarray(chunk, dtype=np.float32).reshape(-1)])
        while len(self._buf) >= self.frame_len:
            frame = self._buf[:self.frame_len]
            self._buf = self._buf[self.frame_len:]
            db = _db(frame)

            if not self.in_speech:
                if db > self._threshold():
                    self.in_speech = True
                    self._frames = [frame]
                    self._silence = 0
                else:
                    # 噪声底只在不说话时更新，避免把语音算进去
                    self.noise_db = db if self.noise_db is None else 0.95 * self.noise_db + 0.05 * db
                continue

            self._frames.append(frame)
            if db < self._threshold() - self.hysteresis_db:
                self._silence += 1
            else:
                self._silence = 0

            if self._silence >= self.silence_frames:
                seg = self._finish()
                if seg is not None:
                    out.append(seg)
            elif len(self._frames) >= self.max_frames:
                seg = self._finish(forced=True)
                if seg is not None:
                    out.append(seg)
        return out

    def flush(self) -> np.ndarray | None:
        """输入结束时把没闭合的句子吐出来。"""
        if not self.in_speech:
            return None
        return self._finish(forced=True)
