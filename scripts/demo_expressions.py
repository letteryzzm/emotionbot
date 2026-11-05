"""轮播 7 种基本表情。
  --viz      只画 2D 预览（不需要硬件），存到 outputs/expressions.png
  默认       连真机，每个表情停 2 秒
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
args = ap.parse_args()

if args.viz:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    from head.viz import draw

    fig, axes = plt.subplots(1, len(EXPRESSIONS), figsize=(3 * len(EXPRESSIONS), 3.4))
    for ax, name in zip(axes, EXPRESSIONS):
        draw(expression(name), ax, name)
    out = Path(__file__).resolve().parent.parent / "outputs" / "expressions.png"
    fig.savefig(out, dpi=90, bbox_inches="tight")
    print(out)
else:
    head = HeadClient()
    head.speed(300)
    try:
        for name in EXPRESSIONS:
            print(name)
            head.set(expression(name))
            time.sleep(args.hold)
        head.rest()
    finally:
        head.close()
