"""眼部动作：静止表情之上的眼神。表情是姿态，眼睛的神采来自动作。

每帧是 (停留秒数, 速度 deg/s, {舵机: u})，帧之间累积；BLINK 是一次眨眼，眨完回到眨之前。
u 的含义和 actuators 一样：眼皮是睁开程度，UD 0.3 是正前（带补偿），LR 0.5 是正中。
只管这 6 个舵机，EXPRESSIONS 不变。
"""
from .actuators import NAMES, to_angles
from .expressions import EXPRESSIONS, expression

EYES = ("LR", "UD", "TL", "TR", "BL", "BR")
LIDS = ("TL", "TR", "BL", "BR")
RELAXED = {"TL": 0.8, "TR": 0.8, "BL": 0.75, "BR": 0.75}   # 没写到的眼皮半放松，全开像瞪眼
BLINK = "blink"
BLINK_SPEED = 800

MOTIONS = {
    "neutral": [(0.5, 200, {"LR": 0.62, "UD": 0.33}), BLINK, (0.7, 200, {"LR": 0.38}),
                (0.5, 200, {"LR": 0.5, "UD": 0.3}), BLINK],
    "happy": [BLINK, BLINK, (0.4, 250, {"UD": 0.36, "TL": 0.5, "TR": 0.5}),
              (0.4, 250, {"LR": 0.58}), (0.4, 250, {"LR": 0.42}), BLINK],
    "sad": [(0.7, 90, {"UD": 0.1, "TL": 0.25, "TR": 0.25}), (0.7, 90, {"LR": 0.38}),
            (0.6, 60, {"TL": 0.1, "TR": 0.1, "BL": 0.6, "BR": 0.6}), (0.6, 90, {"LR": 0.5, "TL": 0.3, "TR": 0.3})],
    "angry": [(0.5, 300, {"TL": 0.7, "TR": 0.7, "BL": 0.15, "BR": 0.15}), (0.35, 400, {"LR": 0.42}),
              (0.35, 400, {"LR": 0.58}), (0.45, 300, {"LR": 0.5, "TL": 0.85, "TR": 0.85}), BLINK],
    "surprised": [(0.35, 800, {"UD": 0.5}), BLINK, (0.4, 300, {"UD": 0.4, "LR": 0.6}), (0.4, 300, {"LR": 0.4})],
    "fear": [(0.22, 600, {"LR": 0.3}), (0.22, 600, {"LR": 0.7}), (0.22, 600, {"LR": 0.35, "UD": 0.38}),
             (0.22, 600, {"LR": 0.65}), BLINK, (0.4, 300, {"LR": 0.5, "UD": 0.22})],
    "disgust": [(0.5, 250, {"LR": 0.68, "UD": 0.22}), (0.5, 250, {"TL": 0.25, "TR": 0.25, "BL": 0.1, "BR": 0.1}),
                BLINK, (0.5, 250, {"LR": 0.32})],
}


def _base(name, k):
    u = dict(zip(NAMES, expression(name, k)))
    base = {n: float(u[n]) for n in EYES}
    for n, v in RELAXED.items():
        if n not in EXPRESSIONS[name]:
            base[n] = v
    return base


def _angles(u):
    ang = to_angles(u)
    return {n: round(ang[n], 1) for n in u}


def eye_pose(name, k=1.0):
    """这个表情静止时 6 个眼部舵机的角度"""
    return _angles(_base(name, k))


def eye_frames(name, k=1.0):
    """[(停留秒数, 速度, {舵机: 角度})]，最后回到静止姿态。k 缩放动作幅度，眨眼不缩放"""
    base = _base(name, k)
    state = dict(base)
    frames = []
    for f in MOTIONS[name]:
        if f == BLINK:
            frames.append((0.11, BLINK_SPEED, _angles({**state, **{n: 0.0 for n in LIDS}})))
            frames.append((0.16, BLINK_SPEED, _angles(state)))
            continue
        hold, speed, u = f
        state.update({n: base[n] + k * (v - base[n]) for n, v in u.items()})
        frames.append((hold, speed, _angles(state)))
    frames.append((0.3, 250, _angles(base)))
    return frames
