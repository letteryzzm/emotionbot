"""实时情绪感知：音频/视频输入 -> 三模态结果 -> 融合。"""
from .types import (AROUSAL, LABEL7, VALENCE, EmotionEstimate, FusionResult,
                    ModalityResult, arousal, normalize_probs, top_label,
                    valence, vector)

__all__ = [
    "AROUSAL", "LABEL7", "VALENCE", "EmotionEstimate", "FusionResult",
    "ModalityResult", "arousal", "normalize_probs", "top_label", "valence", "vector",
]
