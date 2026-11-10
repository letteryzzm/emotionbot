"""真机模型 smoke test：加载本地 SenseVoice + emotion2vec，跑一次真实推理。

    python scripts/smoke_models.py
    python scripts/smoke_models.py --wav demo.wav
    python scripts/smoke_models.py --text "烦死了，真的受不了"

没给 --wav 时用 edge-tts 现场合成一句中文（需要联网），然后走和 app.run 完全
相同的封装类，验证：模型能加载、GPU 能用、文本能出来、7 类概率和为 1。
"""
from __future__ import annotations

import argparse
import os
import sys
import time
import wave
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from perception.types import LABEL7  # noqa: E402


def synth(text: str) -> np.ndarray:
    from agent.tts import ensure_ssl_context

    ensure_ssl_context()
    import asyncio

    import edge_tts
    import miniaudio

    async def run() -> bytes:
        buf = bytearray()
        async for chunk in edge_tts.Communicate(text, "zh-CN-XiaoxiaoNeural").stream():
            if chunk["type"] == "audio":
                buf.extend(chunk["data"])
        return bytes(buf)

    data = asyncio.run(run())
    dec = miniaudio.decode(data, output_format=miniaudio.SampleFormat.FLOAT32,
                           nchannels=1, sample_rate=16000)
    return np.frombuffer(dec.samples, dtype=np.float32).copy()


def read_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as w:
        sr, ch = w.getframerate(), w.getnchannels()
        x = np.frombuffer(w.readframes(w.getnframes()), dtype="<i2").astype(np.float32) / 32768.0
    if ch > 1:
        x = x.reshape(-1, ch).mean(1)
    if sr != 16000:
        raise SystemExit(f"{path} 是 {sr} Hz，需要 16k 单声道 wav")
    return x


def top(probs: dict[str, float]) -> str:
    name = max(probs, key=probs.get)
    return f"{name} {probs[name]:.2f}"


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav", type=Path)
    ap.add_argument("--text", default="今天天气不错，我有点想出去走走")
    ap.add_argument("--no-e2v", action="store_true")
    ap.add_argument("--no-sv", action="store_true")
    args = ap.parse_args(argv)

    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    model_dir = os.environ.get("EMOBOT_MODEL_DIR")
    print(f"模型目录: {model_dir or '（未设置，走 FunASR 默认）'}")

    import torch

    if torch.cuda.is_available():
        print(f"设备: cuda — {torch.cuda.get_device_name(0)}")
    else:
        print("设备: cpu（CUDA 不可用，推理会慢很多）")

    if args.wav:
        wav = read_wav(args.wav)
        print(f"音频: {args.wav} ({len(wav) / 16000:.1f}s)")
    else:
        print(f"合成: {args.text}")
        wav = synth(args.text)
    print(f"输入: {len(wav) / 16000:.2f}s, dtype={wav.dtype}, peak={np.abs(wav).max():.3f}\n")

    ok = True
    if not args.no_sv:
        from perception.asr_ser import SenseVoice

        t = time.perf_counter()
        sv = SenseVoice()
        print(f"[加载] SenseVoice {time.perf_counter() - t:.1f}s")
        t = time.perf_counter()
        text, p_sv = sv.transcribe(wav)
        dt = (time.perf_counter() - t) * 1000
        print(f"[ASR ] {dt:.0f}ms  text={text!r}")
        print(f"[ASR ] 情感 {top(p_sv)}")
        ok &= bool(text.strip()) and abs(sum(p_sv.values()) - 1) < 1e-3

    if not args.no_e2v:
        from perception.ser import Emotion2Vec

        t = time.perf_counter()
        e2v = Emotion2Vec()
        print(f"\n[加载] emotion2vec {time.perf_counter() - t:.1f}s")
        t = time.perf_counter()
        p_e2v = e2v.infer(wav)
        dt = (time.perf_counter() - t) * 1000
        if p_e2v is None:
            print("[SER ] 模型没有分类头")
            ok = False
        else:
            print(f"[SER ] {dt:.0f}ms  {top(p_e2v)}")
            print("       " + "  ".join(f"{k}={p_e2v[k]:.2f}" for k in LABEL7))
            ok &= abs(sum(p_e2v.values()) - 1) < 1e-3

    if torch.cuda.is_available():
        print(f"\n显存占用: {torch.cuda.memory_allocated() / 2**30:.2f} GB "
              f"(峰值 {torch.cuda.max_memory_allocated() / 2**30:.2f} GB)")

    print("\n" + ("SMOKE OK" if ok else "SMOKE FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
