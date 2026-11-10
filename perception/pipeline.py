"""实时感知管线：音频线程切句 -> 工作线程跑 ASR/SER/TER/FER -> 融合。

线程模型很简单：
- audio 线程只做 VAD，绝不做模型推理，保证不会因为推理慢而丢音频；
- worker 线程按句串行处理，一次一句话。3 天 demo 场景够用；
- FER 自己的线程持续跑，worker 按时间窗取最新一帧，缺脸就当成缺失模态。

任何模型都可以是 None：对应模态记为缺失，融合层仍然输出结果。
"""
from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass, field

import numpy as np

from .fusion import fuse
from .types import EmotionEstimate, FusionResult, ModalityResult
from .vad import VADSegmenter


@dataclass
class PerceptionEvent:
    fusion: FusionResult
    estimate: EmotionEstimate
    asr_text: str = ""
    latency_ms: float = 0.0
    t_start: float = 0.0
    t_end: float = 0.0
    sources: dict = field(default_factory=dict)


class PerceptionPipeline:
    def __init__(self, source, asr=None, ser=None, text=None, face=None,
                 echo_gate=None, sr: int = 16000, face_window: float = 1.5,
                 on_result=None):
        self.source = source
        self.asr = asr
        self.ser = ser
        self.text = text
        self.face = face
        self.echo_gate = echo_gate
        self.sr = sr
        self.face_window = face_window
        self.on_result = on_result
        self.vad = VADSegmenter(sr=sr)

        self.segments: queue.Queue = queue.Queue(maxsize=8)
        self.results: queue.Queue = queue.Queue(maxsize=200)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    # ---------- lifecycle ----------
    def start(self):
        self._spawn(self._audio_loop, "perception-audio")
        self._spawn(self._worker_loop, "perception-worker")
        if self.face is not None and hasattr(self.face, "start"):
            self.face.start()
        return self

    def _spawn(self, fn, name):
        t = threading.Thread(target=fn, name=name, daemon=True)
        t.start()
        self._threads.append(t)

    def stop(self):
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2.0)
        self._threads.clear()
        if self.face is not None and hasattr(self.face, "close"):
            self.face.close()

    def __enter__(self):
        return self.start()

    def __exit__(self, *exc):
        self.stop()

    # ---------- loops ----------
    def _audio_loop(self):
        muted_before = False
        try:
            for chunk in self.source.chunks():
                if self._stop.is_set():
                    break
                if self.echo_gate is not None and self.echo_gate.muted():
                    if not muted_before:
                        self.vad.reset()  # 别把说话前后的半句拼成一句
                        muted_before = True
                    continue  # 机器人自己在说话，丢弃麦克风输入
                muted_before = False
                for seg in self.vad.push(chunk):
                    self._enqueue(seg)
            tail = self.vad.flush()
            if tail is not None:
                self._enqueue(tail)
        except Exception as e:  # 麦克风被拔/声卡异常：明确报出来，不要静默死线程
            print(f"[perception] 音频源中断: {e}")
        finally:
            self.segments.put(None)  # 通知 worker 结束

    def _enqueue(self, seg: np.ndarray):
        if self.segments.full():
            try:
                self.segments.get_nowait()  # 丢最旧的一句，保证实时性
            except queue.Empty:
                pass
        self.segments.put(seg)

    def _worker_loop(self):
        while not self._stop.is_set():
            seg = self.segments.get()
            if seg is None:
                break
            t0 = time.monotonic()
            try:
                ev = self._process(seg, t0)
            except Exception as e:  # 单句失败不能拖垮整条管线
                print(f"[perception] 处理失败: {e}")
                continue
            if ev is not None:
                self.results.put(ev)
                if self.on_result is not None:
                    try:
                        self.on_result(ev)
                    except Exception as e:
                        print(f"[perception] 回调失败: {e}")

    # ---------- one utterance ----------
    def _process(self, wav: np.ndarray, t0: float) -> PerceptionEvent | None:
        t_start, t_end = t0 - len(wav) / self.sr, t0
        sources: dict = {}
        mods: list[ModalityResult] = []

        asr_text = ""
        sv_probs = None
        if self.asr is not None:
            asr_text, sv_probs = self.asr.transcribe(wav)
            sources["asr"] = "sensevoice"

        speech_probs, speech_src = None, ""
        if self.ser is not None:
            speech_probs = self.ser.infer(wav)
            if speech_probs is not None:
                speech_src = "emotion2vec"
        if speech_probs is None and sv_probs is not None:
            speech_probs, speech_src = sv_probs, "sensevoice"
        if speech_probs is not None:
            mods.append(ModalityResult("speech", speech_probs, t_start, t_end))
            sources["speech"] = speech_src

        if self.text is not None and asr_text.strip():
            tp, src = self.text.infer(asr_text)
            mods.append(ModalityResult("text", tp, t_start, t_end))
            sources["text"] = src

        if self.face is not None:
            f = self.face.get()
            if f is not None and abs(f.t_end - t_end) <= self.face_window:
                mods.append(f)
                sources["face"] = "emotieffnet"

        fused = fuse(mods)
        est = fused.to_estimate()
        return PerceptionEvent(fused, est, asr_text,
                               latency_ms=(time.monotonic() - t0) * 1000,
                               t_start=t_start, t_end=t_end, sources=sources)

    def wait(self, timeout: float | None = None) -> PerceptionEvent | None:
        """阻塞取一个结果（测试和命令行用）。"""
        try:
            return self.results.get(timeout=timeout)
        except queue.Empty:
            return None
