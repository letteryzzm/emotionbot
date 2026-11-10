"""在 7 种基本表情之外，用现有动作空间拼几个演示需要的复合表情。

不修改 head/expressions.py：基本表情保持原样，复合表情只在本层定义。
"""
from __future__ import annotations

import numpy as np

from head.actuators import rest_vector, to_vector
from head.expressions import EXPRESSIONS, blend, expression

# blend: 基本表情加权叠加；sparse: 直接给舵机 u 值（和 EXPRESSIONS 的写法一致）
COMPOSITES: dict[str, dict] = {
    # 关切：心疼 + 一点点惊讶，用于"语气和字面矛盾"以及对方在诉苦时
    "concerned": {"blend": {"sad": 0.6, "surprised": 0.35}},
    # 思索：视线偏上、眉毛内侧抬起、嘴微张
    "thinking": {"sparse": {"UD": 0.68, "LI": 0.72, "RI": 0.72,
                            "LO": 0.45, "RO": 0.45, "JL": 0.06, "JR": 0.06}},
}

ALL_EXPRESSIONS = list(EXPRESSIONS) + list(COMPOSITES)


def expression_vector(name: str, intensity: float = 1.0) -> np.ndarray:
    """返回 22 维 u，已裁剪到 [0,1]。intensity 在 rest 和满强度之间插值。"""
    rest = rest_vector()
    if name in EXPRESSIONS:
        full = expression(name, 1.0)
    elif name in COMPOSITES:
        spec = COMPOSITES[name]
        full = blend(spec["blend"]) if "blend" in spec else to_vector(spec["sparse"])
    else:
        raise KeyError(f"未知表情 {name!r}，可用: {ALL_EXPRESSIONS}")
    v = rest + float(intensity) * (full - rest)
    return np.clip(v, 0.0, 1.0)
