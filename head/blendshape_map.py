"""MediaPipe FaceLandmarker 的 52 个 blendshape -> 22 个舵机 u。

这是手写的线性映射，用来做"表情模仿"的 baseline。之后要做表情学习时，
用这个映射采数据 (blendshape, u) 再训练一个学习到的映射去替代它。
mirror=True：机器人像照镜子一样模仿对面的人（人的左眼 -> 机器人的右眼）。
"""
import numpy as np

from .actuators import EYE_BROW_L_IS_ROBOT_LEFT, LR_UP_IS_ROBOT_LEFT, MOUTH_L_IS_ROBOT_LEFT, NAMES, rest_vector


def _c(x):
    return float(np.clip(x, 0, 1))


def blendshapes_to_u(bs: dict, mirror=True):
    g = lambda k: bs.get(k, 0.0)  # noqa: E731
    # MediaPipe 的 Left/Right 是被拍的人自己的左右
    robot_l, robot_r = ("Right", "Left") if mirror else ("Left", "Right")
    # L/R：嘴部舵机名；EL/ER：眼皮、眉毛舵机名。两组的左右定义不同，见 actuators.py
    L, R = (robot_l, robot_r) if MOUTH_L_IS_ROBOT_LEFT else (robot_r, robot_l)
    EL, ER = (robot_l, robot_r) if EYE_BROW_L_IS_ROBOT_LEFT else (robot_r, robot_l)

    look_r = (g("eyeLookOutRight") + g("eyeLookInLeft")) / 2
    look_l = (g("eyeLookOutLeft") + g("eyeLookInRight")) / 2
    look_up = (g("eyeLookUpLeft") + g("eyeLookUpRight")) / 2
    look_dn = (g("eyeLookDownLeft") + g("eyeLookDownRight")) / 2
    # 看向机器人左侧为正。镜像时人看自己的右边，机器人看它自己的左边
    gaze_robot_left = look_r - look_l if mirror else look_l - look_r
    lr = gaze_robot_left if LR_UP_IS_ROBOT_LEFT else -gaze_robot_left

    def lid_top(side):
        return _c(1 - g(f"eyeBlink{side}") - 0.3 * g(f"eyeSquint{side}") + 0.3 * g(f"eyeWide{side}"))

    def lid_bot(side):
        return _c(1 - g(f"eyeBlink{side}") - 0.6 * g(f"eyeSquint{side}"))

    u = {
        "LR": _c(0.5 + 0.8 * lr),
        "UD": _c(0.5 + 0.8 * (look_up - look_dn)),
        "TL": lid_top(EL), "BL": lid_bot(EL),
        "TR": lid_top(ER), "BR": lid_bot(ER),
        "LI": _c(0.5 + 0.5 * g("browInnerUp") - 0.6 * g(f"browDown{EL}")),
        "RI": _c(0.5 + 0.5 * g("browInnerUp") - 0.6 * g(f"browDown{ER}")),
        "LO": _c(0.5 + 0.5 * g(f"browOuterUp{EL}") - 0.3 * g(f"browDown{EL}")),
        "RO": _c(0.5 + 0.5 * g(f"browOuterUp{ER}") - 0.3 * g(f"browDown{ER}")),
        "JL": _c(1.2 * g("jawOpen")), "JR": _c(1.2 * g("jawOpen")),
        "LUL": _c(0.5 + 0.5 * g(f"mouthUpperUp{L}")),
        "LUR": _c(0.5 + 0.5 * g(f"mouthUpperUp{R}")),
        "LLL": _c(0.5 - 0.5 * g(f"mouthLowerDown{L}")),
        "LLR": _c(0.5 - 0.5 * g(f"mouthLowerDown{R}")),
        "CUL": _c(0.5 + 0.6 * g(f"mouthSmile{L}") - 0.6 * g(f"mouthFrown{L}")),
        "CUR": _c(0.5 + 0.6 * g(f"mouthSmile{R}") - 0.6 * g(f"mouthFrown{R}")),
        "CLL": _c(0.3 + 0.7 * g(f"mouthStretch{L}") - 0.3 * g("mouthPucker")),
        "CLR": _c(0.3 + 0.7 * g(f"mouthStretch{R}") - 0.3 * g("mouthPucker")),
    }
    v = rest_vector()
    for n, x in u.items():
        v[NAMES.index(n)] = x
    return v


class Smoother:
    """指数平滑，去掉 blendshape 的帧间抖动"""

    def __init__(self, alpha=0.4):
        self.alpha = alpha
        self.v = None

    def __call__(self, v):
        self.v = v if self.v is None else self.alpha * v + (1 - self.alpha) * self.v
        return self.v
