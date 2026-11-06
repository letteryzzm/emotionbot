"""空闲动画和说话嘴形。

机器人头静止不动会显得像死物。这里只叠两个很便宜的东西：
- 随机眨眼（2.5~5.5s 一次，140ms 闭合再打开）
- 极轻微的视线漂移
说话时用 TTS 音频的包络驱动下颌和嘴唇，形成"嘴在动"的观感。
"""
from __future__ import annotations

import math
import random
import time

import numpy as np

from head.actuators import NAMES

LID = [NAMES.index(n) for n in ("TL", "BL", "TR", "BR")]
LR, UD = NAMES.index("LR"), NAMES.index("UD")
JAW = [NAMES.index(n) for n in ("JL", "JR")]
LIPS = [NAMES.index(n) for n in ("LUL", "LUR", "LLL", "LLR")]


class IdleAnimator:
    def __init__(self, blink_interval=(2.5, 5.5), blink_s=0.14, seed=None):
        self.rng = random.Random(seed)
        self.blink_interval = blink_interval
        self.blink_s = blink_s
        self._next_blink = time.monotonic() + self.rng.uniform(*blink_interval)
        self._blink_start: float | None = None
        self._phase = self.rng.uniform(0, math.tau)

    def _blink_factor(self, now: float) -> float:
        if self._blink_start is None and now >= self._next_blink:
            self._blink_start = now
        if self._blink_start is None:
            return 1.0
        p = (now - self._blink_start) / self.blink_s
        if p >= 1.0:
            self._blink_start = None
            self._next_blink = now + self.rng.uniform(*self.blink_interval)
            return 1.0
        return abs(math.cos(math.pi * p))  # 1 -> 0 -> 1

    def apply(self, vec: np.ndarray, now: float | None = None) -> np.ndarray:
        now = time.monotonic() if now is None else now
        v = np.array(vec, dtype=np.float64, copy=True)
        f = self._blink_factor(now)
        for i in LID:
            v[i] *= f
        v[LR] += 0.015 * math.sin(0.31 * now + self._phase)
        v[UD] += 0.010 * math.sin(0.23 * now + self._phase * 1.7)
        return np.clip(v, 0.0, 1.0)


def mouth_pose(vec: np.ndarray, level: float) -> np.ndarray:
    """level: 0~1 的音频包络。只改嘴部，不动眼睛和眉毛。"""
    v = np.array(vec, dtype=np.float64, copy=True)
    level = float(np.clip(level, 0.0, 1.0))
    jaw = 0.08 + 0.75 * level
    for i in JAW:
        v[i] = jaw
    for i in LIPS:
        v[i] = 0.45 + 0.25 * level
    return np.clip(v, 0.0, 1.0)
