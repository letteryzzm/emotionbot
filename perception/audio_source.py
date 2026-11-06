"""音频输入：统一成 16kHz / 单声道 / float32，长度任意的 chunk。

三种来源：
- MicSource      笔记本麦克风（sounddevice），T5 板推流没做好时的兜底
- UdpPcmSource   T5 板用 UDP 推 16k/s16le PCM（建议协议，和队友确认）
- FileSource     读 wav，用于离线回归和没有麦克风时的演示
"""
from __future__ import annotations

import queue
import socket
import time
import wave
from pathlib import Path
from typing import Iterator, Protocol

import numpy as np


class AudioSource(Protocol):
    sr: int

    def chunks(self) -> Iterator[np.ndarray]: ...


class MicSource:
    def __init__(self, sr: int = 16000, block_ms: int = 30, device=None, max_queue: int = 50):
        self.sr = sr
        self.block = int(sr * block_ms / 1000)
        self.device = device
        self.q: queue.Queue[np.ndarray] = queue.Queue(maxsize=max_queue)

    def _callback(self, indata, frames, t, status):
        try:
            self.q.put_nowait(indata[:, 0].copy())
        except queue.Full:
            pass  # 消费端卡住时丢最旧的以外的新音频，避免内存涨

    def chunks(self) -> Iterator[np.ndarray]:
        import sounddevice as sd

        with sd.InputStream(samplerate=self.sr, channels=1, dtype="float32",
                            blocksize=self.block, device=self.device, callback=self._callback):
            while True:
                try:
                    yield self.q.get(timeout=1.0)
                except queue.Empty:
                    continue


class UdpPcmSource:
    """接收 16kHz / mono / int16 little-endian PCM。每个 UDP 包可以是任意长度。"""

    def __init__(self, sr: int = 16000, host: str = "0.0.0.0", port: int = 8770,
                 timeout: float = 1.0):
        self.sr = sr
        self.host, self.port = host, port
        self.timeout = timeout

    def chunks(self) -> Iterator[np.ndarray]:
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.bind((self.host, self.port))
        sock.settimeout(self.timeout)
        try:
            while True:
                try:
                    data, _ = sock.recvfrom(65536)
                except socket.timeout:
                    continue
                if len(data) % 2:  # 容忍半个采样
                    data = data[:-1]
                if not data:
                    continue
                yield np.frombuffer(data, dtype="<i2").astype(np.float32) / 32768.0
        finally:
            sock.close()


class FileSource:
    """读 16-bit PCM wav。非 16k 会做线性重采样；按 realtime=True 时按真实时间吐数据。"""

    def __init__(self, path: str | Path, sr: int = 16000, realtime: bool = False):
        self.path = Path(path)
        self.sr = sr
        self.realtime = realtime

    def _load(self) -> np.ndarray:
        with wave.open(str(self.path), "rb") as w:
            assert w.getsampwidth() == 2, "只支持 16-bit PCM wav"
            src_sr, ch, n = w.getframerate(), w.getnchannels(), w.getnframes()
            raw = np.frombuffer(w.readframes(n), dtype="<i2").astype(np.float32) / 32768.0
        x = raw.reshape(-1, ch).mean(1) if ch > 1 else raw
        if src_sr != self.sr:
            n_out = int(len(x) * self.sr / src_sr)
            x = np.interp(np.linspace(0, len(x) - 1, n_out), np.arange(len(x)), x).astype(np.float32)
        return x

    def chunks(self) -> Iterator[np.ndarray]:
        x = self._load()
        step = int(self.sr * 0.03)  # 和 MicSource 保持 30ms
        for i in range(0, len(x), step):
            if self.realtime:
                time.sleep(0.03)
            yield x[i:i + step]
