"""视觉 -> 眼球跟随 + 按距离/运动变化的表情（Kismet 式互动调谐）。

纯逻辑，不依赖摄像头和硬件，输入 FaceObs，输出 22 维 u。

距离区间（米，单目估计，见 vision.py）：
  无人/太远 (> FAR)        bored   无聊犯困，视线偶尔游走
  舒适 (NEAR..FAR)         interested 感兴趣，眉毛微抬、微笑，眼睛盯着人
  太近 (CLOSE..NEAR)       annoyed 不舒服，皱眉
  贴脸 (< CLOSE)           fear    害怕，睁大眼、眉抬起、嘴角横拉
  人脸移动太快              surprised 受惊（一过性，叠加在上面）
眼皮随眼球上下联动：移植自上游 Will Cogley eyes.py 的 control_ud_and_lids。
"""
from dataclasses import dataclass
import math
import random

import numpy as np

from head.actuators import BY_NAME, LR_UP_IS_ROBOT_LEFT, NAMES, rest_vector, to_vector
from head.expressions import EXPRESSIONS, blend

# 距离阈值（米）
FAR, NEAR, CLOSE = 1.5, 0.45, 0.28
GAZE_GAIN = 1.0          # 画面边缘 -> 眼球极限
FAST_SPEED = 1.6         # 画面归一化坐标/秒，超过算「晃得太快」
LOST_AFTER = 0.6         # 秒，丢脸后眼睛先停在原处，再进入无聊/游走

EXTRA = {
    "bored": {
        "TL": 0.35, "TR": 0.35, "BL": 0.5, "BR": 0.5,
        "LI": 0.35, "RI": 0.35, "LO": 0.3, "RO": 0.3,
        "CUL": 0.35, "CUR": 0.35,
    },
    "annoyed": {  # 比 angry 弱：眉内侧压低、眼皮半眯、嘴角微下
        "LI": 0.15, "RI": 0.15, "LO": 0.6, "RO": 0.6,
        "TL": 0.7, "TR": 0.7, "BL": 0.6, "BR": 0.6,
        "CUL": 0.3, "CUR": 0.3, "CLL": 0.2, "CLR": 0.2,
    },
    "interested": {
        "LI": 0.7, "RI": 0.7, "LO": 0.65, "RO": 0.65,
        "TL": 1.0, "TR": 1.0, "CUL": 0.75, "CUR": 0.75,
    },
}


def _pose(name):
    return EXPRESSIONS[name] if name in EXPRESSIONS else EXTRA[name]


def pose_vector(weights: dict):
    rest = rest_vector()
    v = rest.copy()
    for n, w in weights.items():
        v += w * (to_vector(_pose(n)) - rest)
    return np.clip(v, 0, 1)


@dataclass
class FaceObs:
    x: float        # 人脸中心，画面归一化 [-1,1]，右为正（图像坐标）
    y: float        # 下为正
    dist_m: float   # 估计距离
    t: float        # 时间戳（秒）
    ipd_px: float = 0.0   # 两眼虹膜间距（像素），仅用于显示


def gaze_to_u(x, y, gain=GAZE_GAIN, hfov=65.0, aspect=4 / 3):
    """画面坐标 -> (LR, UD) 的 u，按实际角度算：人偏离光轴多少度，舵机从 rest 转多少度。

    摄像头在两眼中间上方，朝向和机器人一致：画面左侧 = 机器人左侧。
    gain=1 假设舵机角度和眼球角度 1:1，连杆比例不同时调 gain。
    """
    th = math.tan(math.radians(hfov) / 2)
    yaw = math.degrees(math.atan(float(np.clip(x, -1, 1)) * th))             # 右为正
    pitch = math.degrees(math.atan(float(np.clip(y, -1, 1)) * th / aspect))  # 下为正
    s = 1.0 if LR_UP_IS_ROBOT_LEFT else -1.0
    lr_a, ud_a = BY_NAME["LR"], BY_NAME["UD"]
    lr = lr_a.u(lr_a.rest - s * gain * yaw)
    ud = ud_a.u(ud_a.rest - gain * pitch)
    return float(np.clip(lr, 0, 1)), float(np.clip(ud, 0, 1))


def gaze_rest():
    """正视时的 (LR, UD) u。"""
    return BY_NAME["LR"].u(BY_NAME["LR"].rest), BY_NAME["UD"].u(BY_NAME["UD"].rest)


def lids_follow_ud(v, ud):
    """眼球向下看时上眼皮跟着压低、向上看时下眼皮抬一点（上游 control_ud_and_lids）。
    只在原有睁开程度上乘系数，眨眼/表情的闭合不受影响。"""
    c = gaze_rest()[1]   # 正视时不压眼皮
    down = max(0.0, (c - ud) / c)
    up = max(0.0, (ud - c) / (1 - c))
    for n in ("TL", "TR"):
        i = NAMES.index(n)
        v[i] *= 1 - 0.5 * down * 0.8
    for n in ("BL", "BR"):
        i = NAMES.index(n)
        v[i] *= 1 - 0.4 * up * 0.4
    return v


def zone(dist_m, far=FAR, near=NEAR, close=CLOSE):
    if dist_m is None or dist_m > far:
        return "bored"
    if dist_m > near:
        return "interested"
    if dist_m > close:
        return "annoyed"
    return "fear"


class Behavior:
    def __init__(self, seed=None, eye_alpha=0.5, expr_alpha=0.08):
        self.rng = random.Random(seed)
        self.eye_alpha, self.expr_alpha = eye_alpha, expr_alpha
        self.gaze = gaze_rest()
        self.expr = rest_vector()
        self.state = "bored"
        self.far, self.near, self.close = FAR, NEAR, CLOSE
        self.gain = GAZE_GAIN
        self.hfov, self.aspect = 65.0, 4 / 3
        self.fast_speed = FAST_SPEED
        self.force = None          # 调试：强制某个表情（zone 名或 EXPRESSIONS 名）
        self._last = None          # 上一次 FaceObs
        self._speed = 0.0
        self._startle_until = 0.0
        self._next_blink = 2.0
        self._blink_until = 0.0
        self._wander_to = 0.0
        self._wander = gaze_rest()

    def step(self, obs, t):
        """obs: FaceObs 或 None。返回 22 维 u。"""
        # --- 运动速度（EMA），用于「晃太快」 ---
        if obs and self._last and obs.t > self._last.t:
            dt = obs.t - self._last.t
            sp = np.hypot(obs.x - self._last.x, obs.y - self._last.y) / dt
            self._speed = 0.6 * self._speed + 0.4 * sp
        elif not obs:
            self._speed *= 0.9
        if obs:
            if self._speed > self.fast_speed and t > self._startle_until + 1.0:
                self._startle_until = t + 0.6
            self._last = obs
        lost = self._last is None or t - self._last.t > LOST_AFTER

        # --- 目标视线 ---
        if obs:
            target = gaze_to_u(obs.x, obs.y, self.gain, self.hfov, self.aspect)
        elif lost:
            if t > self._wander_to:  # 无聊时偶尔扫视
                c = gaze_rest()
                self._wander = (c[0] + self.rng.uniform(-0.25, 0.25), c[1] + self.rng.uniform(-0.1, 0.1))
                self._wander_to = t + self.rng.uniform(1.5, 4.0)
            target = self._wander
        else:
            target = self.gaze
        a = self.eye_alpha
        self.gaze = (a * target[0] + (1 - a) * self.gaze[0], a * target[1] + (1 - a) * self.gaze[1])

        # --- 表情 ---
        self.state = self.force or zone(None if lost else (obs.dist_m if obs else self._last.dist_m),
                                        self.far, self.near, self.close)
        w = {self.state: 1.0}
        if t < self._startle_until and self.state != "bored":
            w = {self.state: 0.4, "surprised": 0.8}
        target_expr = pose_vector(w)
        self.expr += self.expr_alpha * (target_expr - self.expr)

        v = self.expr.copy()
        v[NAMES.index("LR")], v[NAMES.index("UD")] = self.gaze
        lids_follow_ud(v, self.gaze[1])

        # --- 眨眼（无聊时慢而长）---
        if t >= self._next_blink:
            self._blink_until = t + (0.25 if self.state == "bored" else 0.12)
            self._next_blink = t + self.rng.uniform(2.0, 5.0)
        if t < self._blink_until:
            for n in ("TL", "TR", "BL", "BR"):
                v[NAMES.index(n)] = 0.0
        return np.clip(v, 0, 1)
