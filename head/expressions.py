"""手工设计的 7 种基本表情（Ekman），作为表情学习的起点 / baseline。

只写和 rest 不同的舵机，其余用 rest。数值是按 FACS 的直觉估的，装好后要对着实物调。
"""
import numpy as np

from .actuators import rest_vector, to_vector


def _both(prefix_l, prefix_r, v):
    return {prefix_l: v, prefix_r: v}


EXPRESSIONS = {
    "neutral": {},
    "happy": {  # AU6 脸颊上提(眯眼) + AU12 嘴角上扬
        **_both("TL", "TR", 0.75), **_both("BL", "BR", 0.6),
        **_both("CUL", "CUR", 1.0), **_both("CLL", "CLR", 0.7),
        **_both("JL", "JR", 0.2), **_both("LO", "RO", 0.6), **_both("LI", "RI", 0.6),
    },
    "sad": {  # AU1 眉内侧上抬 + AU15 嘴角下拉 + 视线向下
        **_both("LI", "RI", 0.9), **_both("LO", "RO", 0.2),
        **_both("TL", "TR", 0.55), "UD": 0.3,
        **_both("CUL", "CUR", 0.0), **_both("CLL", "CLR", 0.3),
    },
    "angry": {  # AU4 皱眉(内侧压低) + AU5/7 瞪眼 + AU23 抿嘴
        **_both("LI", "RI", 0.0), **_both("LO", "RO", 0.8),
        **_both("TL", "TR", 0.9), **_both("BL", "BR", 0.5),
        **_both("CUL", "CUR", 0.3), **_both("CLL", "CLR", 0.0),
    },
    "surprised": {  # AU1+2 眉全抬 + AU5 睁大 + AU26 张嘴
        **_both("LI", "RI", 1.0), **_both("LO", "RO", 1.0),
        **_both("TL", "TR", 1.0), **_both("BL", "BR", 1.0),
        **_both("JL", "JR", 0.8),
    },
    "fear": {  # AU1+2+4 + AU5 + AU20 嘴角横拉
        **_both("LI", "RI", 1.0), **_both("LO", "RO", 0.6),
        **_both("TL", "TR", 1.0), **_both("JL", "JR", 0.3),
        **_both("CLL", "CLR", 1.0), **_both("CUL", "CUR", 0.35),
    },
    "disgust": {  # AU9/10 上唇上提 + AU4 + 眯眼
        **_both("LUL", "LUR", 1.0), **_both("LI", "RI", 0.2),
        **_both("TL", "TR", 0.6), **_both("BL", "BR", 0.5),
        **_both("CUL", "CUR", 0.25),
    },
}


def expression(name, intensity=1.0):
    """返回 22 维向量；intensity 在 rest 和满强度之间线性插值"""
    rest = rest_vector()
    full = to_vector(EXPRESSIONS[name])
    return rest + intensity * (full - rest)


def blend(weights: dict):
    """weights: {"happy": 0.6, "surprised": 0.4} -> 22 维向量"""
    rest = rest_vector()
    v = rest.copy()
    for name, w in weights.items():
        v += w * (to_vector(EXPRESSIONS[name]) - rest)
    return np.clip(v, 0, 1)
