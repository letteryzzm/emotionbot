"""轮播 7 种基本表情。
  --viz      只画 2D 预览（不需要硬件），存到 outputs/expressions.png
  默认       连真机，每个表情停 2 秒
  --only happy,sad  只做这几个表情
  --intensity 0.3   强度 0~1，第一次上真机先用小强度
  --speed 60        舵机速度 deg/s
"""
import argparse
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from head import EXPRESSIONS, HeadClient, expression  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--viz", action="store_true")
ap.add_argument("--hold", type=float, default=2.0)
ap.add_argument("--only", help="逗号分隔的表情名")
ap.add_argument("--intensity", type=float, default=1.0)
ap.add_argument("--speed", type=float, default=300)
args = ap.parse_args()
names = args.only.split(",") if args.only else list(EXPRESSIONS)
unknown = set(names) - set(EXPRESSIONS)
if unknown:
    sys.exit(f"没有这些表情: {sorted(unknown)}，可选: {list(EXPRESSIONS)}")

if args.viz:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from head.viz import draw

    fig, axes = plt.subplots(1, len(names), figsize=(3 * len(names), 3.4), squeeze=False)
    for ax, name in zip(axes[0], names):
        draw(expression(name, args.intensity), ax, name)
    out = Path(__file__).resolve().parent.parent / "outputs" / "expressions.png"
    fig.savefig(out, dpi=90, bbox_inches="tight")
    print(out)
else:
    head = HeadClient()
    head.speed(args.speed)
    try:
        for name in names:
            print(name)
            head.set(expression(name, args.intensity))
            time.sleep(args.hold)
        head.rest()
    finally:
        head.close()
