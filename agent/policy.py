"""情绪 -> 表情的规则策略。

设计原则（来自 docs/情感识别模块/05-后续优化.md）：
- 猜错情绪比不回应更伤体验：置信度不够就回到 neutral，不做夸张反应。
- anger 的强度要收着，避免把用户的表情回敬给对方。
- 矛盾场景单独映射到 concerned，这是整个 demo 的记忆点。
"""
from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from perception.types import FusionResult

from .composite import expression_vector

# 表情名, 强度, 持续时间（秒）
RULES: dict[str, tuple[str, float, float]] = {
    "happy":    ("happy", 0.80, 2.5),
    "sad":      ("sad", 0.70, 3.0),
    "angry":    ("angry", 0.55, 2.0),
    "surprise": ("surprised", 0.90, 1.5),
    "fear":     ("fear", 0.60, 2.0),
    "disgust":  ("disgust", 0.50, 2.0),
    "neutral":  ("neutral", 0.00, 1.0),
}
CONFLICT_RULE = ("concerned", 0.70, 3.0)


@dataclass
class ExpressionCommand:
    name: str
    intensity: float
    duration: float
    vector: np.ndarray
    reason: str = ""

    @property
    def is_active(self) -> bool:
        return self.intensity > 0 and self.name != "neutral"


def decide(fusion: FusionResult, min_confidence: float = 0.40) -> ExpressionCommand:
    if fusion.conflict:
        name, intensity, duration = CONFLICT_RULE
        reason = "语气与字面矛盾"
    elif fusion.label == "neutral" or fusion.confidence < min_confidence:
        name, intensity, duration = RULES["neutral"]
        reason = "低置信度或不明确，不做反应"
    else:
        name, intensity, duration = RULES.get(fusion.label, RULES["neutral"])
        reason = f"融合结果 {fusion.label} ({fusion.confidence:.2f})"
    return ExpressionCommand(name, intensity, duration,
                             expression_vector(name, intensity), reason)
