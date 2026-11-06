"""2D 卡通脸预览：没有硬件时先用它调表情、做表情学习的仿真。

只是示意图，几何和真机不对应；画的是机器人自己的左右（观众看到的右边是它的左边）。
"""
import matplotlib.pyplot as plt
import numpy as np
from matplotlib.patches import Ellipse

from .actuators import EYE_BROW_L_IS_ROBOT_LEFT, MOUTH_L_IS_ROBOT_LEFT, NAMES


def draw(v, ax=None, title=None):
    u = dict(zip(NAMES, np.asarray(v, dtype=float)))
    ax = ax or plt.gca()
    ax.clear()
    ax.set_xlim(-2, 2)
    ax.set_ylim(-2.2, 1.8)
    ax.set_aspect("equal")
    ax.axis("off")
    ax.add_patch(Ellipse((0, 0), 3.6, 4.2, fc="#f3dcc6", ec="k"))
    gx, gy = (u["LR"] - 0.5) * 0.3, (u["UD"] - 0.5) * 0.2
    # 机器人的左眼画在观众右侧
    lx = 0.7 if EYE_BROW_L_IS_ROBOT_LEFT else -0.7
    for side, x in (("L", lx), ("R", -lx)):
        top, bot = u[f"T{side}"], u[f"B{side}"]
        y0 = 0.45
        ax.add_patch(Ellipse((x, y0), 0.8, 0.5, fc="white", ec="k"))
        ax.add_patch(Ellipse((x + gx, y0 + gy), 0.25, 0.25, fc="#333"))
        ax.fill_between([x - 0.42, x + 0.42], y0 + 0.27, y0 + 0.27 - 0.27 * (1 - top), color="#f3dcc6")
        ax.fill_between([x - 0.42, x + 0.42], y0 - 0.27, y0 - 0.27 + 0.27 * (1 - bot), color="#f3dcc6")
        inner, outer = u[f"{side}I"], u[f"{side}O"]
        xi, xo = (x - 0.4, x + 0.4) if x > 0 else (x + 0.4, x - 0.4)
        ax.plot([xi, xo], [0.85 + 0.3 * (inner - 0.5), 0.85 + 0.3 * (outer - 0.5)], "k", lw=4)
    jaw = (u["JL"] + u["JR"]) / 2
    up_l, up_r = u["LUL"] - 0.5, u["LUR"] - 0.5
    cu_l, cu_r = u["CUL"] - 0.5, u["CUR"] - 0.5
    w_l, w_r = 0.45 + 0.25 * u["CLL"], 0.45 + 0.25 * u["CLR"]
    if not MOUTH_L_IS_ROBOT_LEFT:  # 下面的 _l 画在观众右侧，也就是机器人左侧
        up_l, up_r, cu_l, cu_r, w_l, w_r = up_r, up_l, cu_r, cu_l, w_r, w_l
    my = -1.0
    xs = np.array([-w_r, 0, w_l])
    upper = my + np.array([0.4 * cu_r, 0.08 + 0.15 * (up_l + up_r) / 2, 0.4 * cu_l])
    lower = my + np.array([0.4 * cu_r, -0.08 - 0.6 * jaw, 0.4 * cu_l])
    t = np.linspace(-1, 1, 30)
    curve = lambda ys: np.interp(t * max(w_l, w_r), xs, ys)  # noqa: E731
    ax.fill_between(t * max(w_l, w_r), curve(upper), curve(lower), color="#8b2c2c")
    ax.plot(t * max(w_l, w_r), curve(upper), "k", lw=2)
    ax.plot(t * max(w_l, w_r), curve(lower), "k", lw=2)
    if title:
        ax.set_title(title)
    return ax
