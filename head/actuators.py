"""22 个舵机的统一动作空间。

每个舵机用归一化值 u ∈ [0,1]：u=0 对应 config 里的角度 a，u=1 对应角度 b。
固件 config_*.py 是唯一的数据源，这里直接读，避免两边对不上。

u 的语义（装好后要逐个核对方向）：
  眼皮 TL/BL/TR/BR: 睁开程度     眼球 LR: 左右  UD: 上下
  眉毛 LO/LI/RI/RO: 抬起程度     下颌 JL/JR: 张嘴程度
  嘴唇 LUL/LUR/LLL/LLR: 上抬     嘴角上 CUL/CUR: 笑(1)↔撇嘴(0)
  嘴角下 CLL/CLR: 宽(1)↔窄(0)   舌头 TON: 上抬
"""
import runpy
from dataclasses import dataclass
from pathlib import Path

import numpy as np

FIRMWARE = Path(__file__).resolve().parent.parent / "firmware"
BOARDS = ("eyes", "brows", "mouth")


@dataclass(frozen=True)
class Actuator:
    name: str
    board: str
    pin: int
    a: float
    b: float
    rest: float

    def angle(self, u):
        return self.a + float(np.clip(u, 0, 1)) * (self.b - self.a)

    def u(self, angle):
        return (angle - self.a) / (self.b - self.a)


def _load():
    acts = []
    for board in BOARDS:
        cfg = runpy.run_path(str(FIRMWARE / f"config_{board}.py"))
        assert cfg["ROLE"] == board
        for name, (pin, a, b, rest) in cfg["SERVOS"].items():
            acts.append(Actuator(name, board, pin, a, b, rest))
    return acts


ACTUATORS = _load()
NAMES = [a.name for a in ACTUATORS]
BY_NAME = {a.name: a for a in ACTUATORS}


def rest_vector():
    return np.array([a.u(a.rest) for a in ACTUATORS])


def to_angles(u):
    """u: dict 或长度 22 的向量 -> {name: angle}"""
    if not isinstance(u, dict):
        u = dict(zip(NAMES, np.asarray(u, dtype=float)))
    return {n: BY_NAME[n].angle(v) for n, v in u.items()}


def to_vector(u: dict, base=None):
    v = rest_vector() if base is None else np.array(base, dtype=float)
    for n, x in u.items():
        v[NAMES.index(n)] = x
    return v
