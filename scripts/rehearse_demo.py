"""按 docs/情感识别模块/04-最终展示.md 的脚本做彩排：批量回放录音，打印每句的判定。

    python scripts/rehearse_demo.py --wav-dir tests/fixtures/demo
    python scripts/rehearse_demo.py --wav-dir tests/fixtures/demo --stub      # 只验流程
    python scripts/rehearse_demo.py --wav-dir tests/fixtures/demo --camera 0  # 连摄像头

文件名约定（可选，用于自动判定）：
    01_consistent_happy.wav          期望融合标签 happy
    03_conflict_sad.wav              期望 conflict=True 且融合跟语气走（sad）
    带 "conflict" 的文件会检查矛盾标志；带情绪名的检查融合标签。

退出码：有不符合预期的文件时返回 1，方便赛前一把过。
"""
from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from agent.policy import decide  # noqa: E402
from perception.audio_source import FileSource  # noqa: E402

LABELS = ("neutral", "happy", "sad", "angry", "surprise", "fear", "disgust")


def expectation(path: Path) -> tuple[str | None, bool | None]:
    name = path.stem.lower()
    label = next((l for l in LABELS if l in name), None)
    conflict = True if "conflict" in name else None
    return label, conflict


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--wav-dir", default="tests/fixtures/demo")
    ap.add_argument("--stub", action="store_true")
    ap.add_argument("--device", default="auto")
    ap.add_argument("--camera", type=int, default=None)
    args = ap.parse_args(argv)

    wavs = sorted(Path(args.wav_dir).glob("*.wav"))
    if not wavs:
        print(f"{args.wav_dir} 里没有 wav。先用手机/电脑录几句，命名见脚本顶部注释。")
        return 1

    if args.stub:
        from app.run import _StubASR, _StubSER, _StubText

        asr, ser, text = _StubASR(), _StubSER(), _StubText()
    else:
        from app.run import _models, parse_args as _pa

        asr, ser, text = _models(_pa(["--device", args.device]))

    face = None
    if args.camera is not None:
        from perception.fer import CameraFER

        face = CameraFER(camera=args.camera)
        face = face if face.ok else None

    from perception.pipeline import PerceptionPipeline

    print(f"\n{'文件':34s} {'文本':22s} {'人脸':8s} {'语音':8s} {'字面':8s} "
          f"{'融合':8s} {'矛盾':4s} {'表情':10s} {'延迟':>6s}")
    print("-" * 118)

    bad = 0
    for w in wavs:
        p = PerceptionPipeline(FileSource(w), asr=asr, ser=ser, text=text,
                               face=face).start()
        events = []
        while True:
            ev = p.wait(timeout=4.0)
            if ev is None:
                break
            events.append(ev)
        p.stop()
        if not events:
            print(f"{w.name:34s} <没有切出句子，检查音量或 VAD 阈值>")
            bad += 1
            continue

        for ev in events:
            pm = ev.fusion.per_modality
            def cell(mod):
                d = pm.get(mod)
                if not d:
                    return "-"
                probs = d["probs"]
                lab = max(probs, key=probs.get)
                return f"{lab[:7]}"
            cmd = decide(ev.fusion)
            print(f"{w.name:34s} {ev.asr_text[:20]:22s} {cell('face'):8s} "
                  f"{cell('speech'):8s} {cell('text'):8s} {ev.fusion.label:8s} "
                  f"{'是' if ev.fusion.conflict else '.':4s} {cmd.name:10s} "
                  f"{ev.latency_ms:6.0f}")

        label, conflict = expectation(w)
        last = events[-1].fusion
        if conflict is not None and last.conflict != conflict:
            print(f"    !! 期望 conflict={conflict}，实际 {last.conflict}")
            bad += 1
        if label and last.label != label:
            print(f"    !! 期望融合 {label}，实际 {last.label}")
            bad += 1

    print(f"\n共 {len(wavs)} 个文件，{bad} 处不符合预期。")
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
