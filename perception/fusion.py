"""置信度加权的 late fusion + 语气/字面矛盾检测。

融合公式沿用 emo_bench/src/fast_layer.py 的做法（对数概率加权平均），
额外补了三件实时管线需要的东西：
1. 缺失模态：权重归一化，并按缺失数量降低 confidence；
2. 低置信度：调用方可以直接据此选择"不反应"；
3. 矛盾检测：文本效价和语音效价相反且两边都自信时，判定为 conflict，
   融合结果跟语音走并在 detail 里记下两边的标签。
"""
from __future__ import annotations

import numpy as np

from .types import (LABEL7, MODALITIES, FusionResult, ModalityResult,
                    normalize_probs, top_label, valence, vector)

POSITIVE = {"happy"}
NEGATIVE = {"sad", "angry", "fear", "disgust"}


def _log_fuse(results: list[ModalityResult], weights: list[float]) -> dict[str, float]:
    logs = []
    for r, w in zip(results, weights):
        if w <= 0:
            continue
        logs.append(w * np.log(np.clip(vector(r.probs), 1e-6, 1.0)))
    if not logs:
        return normalize_probs({})
    L = np.sum(logs, axis=0)
    p = np.exp(L - L.max())
    p /= p.sum()
    return normalize_probs(dict(zip(LABEL7, p)))


def detect_conflict(text: ModalityResult, speech: ModalityResult,
                    min_conf: float = 0.55, min_abs_valence: float = 0.35) -> bool:
    """字面（text）和语气（speech）一个偏正一个偏负，且两边都有把握。"""
    vt, vs = valence(text.probs), valence(speech.probs)
    if vt * vs >= 0:
        return False
    if abs(vt) < min_abs_valence or abs(vs) < min_abs_valence:
        return False
    if min(text.confidence, speech.confidence) < min_conf:
        return False
    return not (top_label(text.probs) == "neutral" and top_label(speech.probs) == "neutral")


def fuse(results: list[ModalityResult], *, conflict_min_conf: float = 0.55,
         speech_boost: float = 1.0, confidence_decay: float = 0.9) -> FusionResult:
    """results 里可以缺任意模态；同模态重复只会取最后一个。"""
    by_mod: dict[str, ModalityResult] = {}
    for r in results:
        if r is not None and r.modality in MODALITIES:
            by_mod[r.modality] = r
    present = list(by_mod.values())
    missing = [m for m in MODALITIES if m not in by_mod]

    t0 = min((r.t_start for r in present), default=0.0)
    t1 = max((r.t_end for r in present), default=0.0)

    if not present:
        return FusionResult(normalize_probs({}), "neutral", 0.0, False, list(MODALITIES),
                            {}, t0, t1, {"reason": "no modality"})

    weights = [max(r.confidence, 1e-3) for r in present]
    if speech_boost != 1.0:
        weights = [w * speech_boost if r.modality == "speech" else w
                   for r, w in zip(present, weights)]

    fused = _log_fuse(present, weights)
    label = top_label(fused)
    confidence = max(fused.values()) * (confidence_decay ** len(missing))

    detail: dict = {}
    conflict = False
    text, speech = by_mod.get("text"), by_mod.get("speech")
    if text is not None and speech is not None and detect_conflict(text, speech, conflict_min_conf):
        conflict = True
        # 文本有 semantic dominance 偏差（06-实验报告 2.3）：矛盾时以语气为准。
        fused = _log_fuse([text, speech], [0.2, 0.8])
        label = top_label(fused)
        confidence = max(fused.values())
        detail = {"speech_label": top_label(speech.probs),
                  "text_label": top_label(text.probs),
                  "speech_valence": round(valence(speech.probs), 3),
                  "text_valence": round(valence(text.probs), 3)}

    return FusionResult(
        probs=fused, label=label, confidence=confidence, conflict=conflict,
        missing=missing,
        per_modality={m: {"probs": r.probs, "confidence": r.confidence}
                      for m, r in by_mod.items()},
        t_start=t0, t_end=t1, detail=detail,
    )
