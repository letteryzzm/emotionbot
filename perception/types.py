"""实时情绪的公共数据结构，字段和 docs/情感识别模块/README.md 的 EmotionEstimate 一致。

约定：
- 所有 prob 字典只含 7 类（LABEL7），和为 1；模型多出来的 other/unknown 在 normalize_probs 里丢掉。
- 时间戳都是 time.monotonic()，单调、可跨线程比较。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

import numpy as np

LABEL7 = ["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"]
IDX = {k: i for i, k in enumerate(LABEL7)}

# 7 类 -> 效价/唤醒的先验坐标。只用来把离散概率压成连续值，不是训练出来的，
# 和 06-实验报告 里用回归模型算的 V/A 含义不同（那个是模型输出，这里是先验投影）。
VALENCE = {"happy": 1.0, "surprise": 0.2, "neutral": 0.0,
           "sad": -0.8, "angry": -1.0, "fear": -0.9, "disgust": -0.8}
AROUSAL = {"happy": 0.7, "surprise": 0.9, "neutral": 0.0,
           "sad": -0.4, "angry": 0.9, "fear": 0.9, "disgust": 0.4}

MODALITIES = ("face", "speech", "text")


def normalize_probs(probs: dict[str, float]) -> dict[str, float]:
    """只保留 7 类，裁剪非负并归一化。空输入/全零返回均匀分布。"""
    p = np.array([max(float(probs.get(k, 0.0)), 0.0) for k in LABEL7], dtype=np.float64)
    s = p.sum()
    if s <= 1e-9:
        return {k: 1.0 / len(LABEL7) for k in LABEL7}
    p /= s
    return {k: float(v) for k, v in zip(LABEL7, p)}


def vector(probs: dict[str, float]) -> np.ndarray:
    return np.array([probs.get(k, 0.0) for k in LABEL7], dtype=np.float64)


def top_label(probs: dict[str, float]) -> str:
    return max(LABEL7, key=lambda k: probs.get(k, 0.0))


def valence(probs: dict[str, float]) -> float:
    """[-1, 1] 的期望效价。"""
    return float(sum(probs.get(k, 0.0) * v for k, v in VALENCE.items()))


def arousal(probs: dict[str, float]) -> float:
    """[-1, 1] 的期望唤醒度。"""
    return float(sum(probs.get(k, 0.0) * v for k, v in AROUSAL.items()))


@dataclass
class ModalityResult:
    """单个模态的一句话级结果。"""
    modality: str                      # "face" | "speech" | "text"
    probs: dict[str, float]
    t_start: float
    t_end: float
    confidence: float = 0.0
    extra: dict = field(default_factory=dict)

    def __post_init__(self):
        self.probs = normalize_probs(self.probs)
        if self.confidence <= 0:
            self.confidence = max(self.probs.values())


@dataclass
class EmotionEstimate:
    """对外统一输出，字段见 docs/情感识别模块/README.md:31-44。"""
    modality: str                      # "face" | "speech" | "text" | "fused"
    t_start: float
    t_end: float
    probs: dict[str, float]
    valence: Optional[float] = None
    arousal: Optional[float] = None
    confidence: float = 0.0
    extra: dict = field(default_factory=dict)


@dataclass
class FusionResult:
    probs: dict[str, float]
    label: str
    confidence: float
    conflict: bool
    missing: list[str]
    per_modality: dict[str, dict] = field(default_factory=dict)
    t_start: float = 0.0
    t_end: float = 0.0
    detail: dict = field(default_factory=dict)

    def to_estimate(self) -> EmotionEstimate:
        return EmotionEstimate(
            modality="fused", t_start=self.t_start, t_end=self.t_end,
            probs=self.probs, valence=valence(self.probs), arousal=arousal(self.probs),
            confidence=self.confidence,
            extra={"conflict": self.conflict, "missing": self.missing,
                   "per_modality": self.per_modality, **self.detail},
        )
