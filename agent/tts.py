"""中文 TTS：edge-tts 在线合成 -> miniaudio 解码 -> sounddevice 播放。

播放是阻塞的，并且逐块把音量包络回调出去，供 idle.mouth_pose 驱动嘴形。
在线失败时退回本地 TTS：Linux 用 espeak-ng，Windows 用 SAPI（pyttsx3），
声音差一些但离线可用。输出设备可用 EMOBOT_AUDIO_OUT 指定（Linux 多声卡时有用）。
"""
from __future__ import annotations

import asyncio
import os
import shutil
import subprocess
import sys
import tempfile
import wave

import numpy as np

from .echo import EchoGate


def _rms(x: np.ndarray) -> float:
    return float(np.sqrt(np.mean(np.square(x), dtype=np.float64) + 1e-12))


def ensure_ssl_context():
    """修 Windows 证书库里损坏证书导致的 SSLError。

    Python 3.10 + Anaconda 在部分 Windows 机器上，`ssl.create_default_context()`
    会读到一张坏证书并抛 `ASN1: NOT_ENOUGH_DATA`，连 `import aiohttp/edge_tts`
    都会失败。把默认上下文换成 certifi 的 CA 包即可绕开。
    """
    import ssl

    try:
        ssl.create_default_context()
        return True
    except Exception:
        pass
    try:
        import certifi

        orig = ssl.create_default_context

        def patched(*a, **kw):
            if not (kw.get("cafile") or kw.get("capath") or kw.get("cadata")):
                kw["cafile"] = certifi.where()
            return orig(*a, **kw)

        ssl.create_default_context = patched
        print("[tts] Windows 证书库有损坏证书，已改用 certifi CA")
        return True
    except Exception as e:
        print(f"[tts] SSL 初始化失败: {e}")
        return False


def _espeak_exe() -> str | None:
    if sys.platform == "win32":
        return None
    return shutil.which("espeak-ng") or shutil.which("espeak")


def _local_backend() -> str | None:
    """离线兜底：Linux 优先 espeak-ng，Windows/macOS 走 pyttsx3。"""
    if _espeak_exe():
        return "espeak"
    import importlib.util

    if importlib.util.find_spec("pyttsx3") is not None:
        return "sapi"
    return None


def available_backend() -> str:
    """返回 edge / espeak / sapi / none，用于启动时如实报告实际会用的 TTS。"""
    import importlib.util

    if importlib.util.find_spec("edge_tts") is not None:
        ensure_ssl_context()  # 让后面真 import aiohttp 时不再炸
        return "edge"
    return _local_backend() or "none"


class TTSPlayer:
    def __init__(self, voice: str = "zh-CN-XiaoxiaoNeural", rate: str = "+0%"):
        self.voice = voice
        self.rate = rate
        self.online = available_backend() == "edge"

    # ---------- synthesis ----------
    def _edge_mp3(self, text: str) -> bytes:
        ensure_ssl_context()
        import edge_tts

        async def run():
            comm = edge_tts.Communicate(text, self.voice, rate=self.rate)
            buf = bytearray()
            async for chunk in comm.stream():
                if chunk["type"] == "audio":
                    buf.extend(chunk["data"])
            return bytes(buf)

        return asyncio.run(run())

    def _decode_mp3(self, data: bytes) -> tuple[np.ndarray, int]:
        import miniaudio

        dec = miniaudio.decode(data, output_format=miniaudio.SampleFormat.FLOAT32,
                               nchannels=1, sample_rate=24000)
        return np.frombuffer(dec.samples, dtype=np.float32).copy(), dec.sample_rate

    def _espeak_wav(self, text: str) -> tuple[np.ndarray, int]:
        exe = _espeak_exe()
        if not exe:
            raise RuntimeError("espeak-ng 未安装（sudo apt install espeak-ng）")
        path = os.path.join(tempfile.gettempdir(), "emobot_tts.wav")
        # cmn 是普通话；老版本 espeak 没这个音色时再退回默认音色
        for voice in ("cmn", None):
            cmd = [exe] + (["-v", voice] if voice else []) + ["-s", "165", "-w", path, text]
            if subprocess.run(cmd, capture_output=True).returncode == 0:
                break
        else:
            raise RuntimeError("espeak-ng 合成失败")
        with wave.open(path, "rb") as w:
            sr, ch = w.getframerate(), w.getnchannels()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
        return (x.reshape(-1, ch).mean(1) if ch > 1 else x), sr

    def _sapi_wav(self, text: str) -> tuple[np.ndarray, int]:
        import pyttsx3

        path = os.path.join(tempfile.gettempdir(), "emobot_tts.wav")
        eng = pyttsx3.init()
        for v in eng.getProperty("voices"):
            if "chinese" in str(v.name).lower() or "zh" in str(v.id).lower():
                eng.setProperty("voice", v.id)
                break
        eng.save_to_file(text, path)
        eng.runAndWait()
        with wave.open(path, "rb") as w:
            sr, ch = w.getframerate(), w.getnchannels()
            x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
        return (x.reshape(-1, ch).mean(1) if ch > 1 else x), sr

    def _local_wav(self, text: str) -> tuple[np.ndarray, int]:
        if _espeak_exe():
            return self._espeak_wav(text)
        return self._sapi_wav(text)

    def synthesize(self, text: str) -> tuple[np.ndarray, int]:
        if self.online:
            try:
                return self._decode_mp3(self._edge_mp3(text))
            except Exception as e:
                # 现场断网时不要每句话都重试一次，直接降级到底
                self.online = False
                print(f"[tts] edge-tts 失败，本次运行改用本地 TTS（{_local_backend()}）: {e}")
        return self._local_wav(text)

    # ---------- playback ----------
    def play(self, audio: np.ndarray, sr: int, gate: EchoGate | None = None,
             on_level=None):
        import sounddevice as sd

        dur = len(audio) / sr
        if gate is not None:
            gate.mute(dur + gate.tail)
        block = max(1, int(sr * 0.03))
        # Linux 上常有多块声卡，默认设备可能不是接扬声器的那个
        device = os.environ.get("EMOBOT_AUDIO_OUT") or None
        try:
            with sd.OutputStream(samplerate=sr, channels=1, dtype="float32",
                                 device=device) as stream:
                for i in range(0, len(audio), block):
                    chunk = audio[i:i + block].astype(np.float32)
                    stream.write(chunk)
                    if on_level is not None:
                        on_level(min(1.0, _rms(chunk) * 6.0))
        finally:
            if on_level is not None:
                on_level(0.0)

    def speak(self, text: str, gate: EchoGate | None = None, on_level=None):
        if not text.strip():
            return
        audio, sr = self.synthesize(text)
        self.play(audio, sr, gate, on_level)
