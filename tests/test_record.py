"""锁定仪表盘依赖的事件 JSON 形状，改动 build_record 时能立刻发现。"""
import json

from app.run import build_record
from agent.policy import ExpressionCommand
from perception.types import LABEL7, EmotionEstimate, FusionResult
from perception.pipeline import PerceptionEvent


def probs(label, peak=0.7):
    p = {k: (1 - peak) / 6 for k in LABEL7}
    p[label] = peak
    return p


def test_record_is_json_serialisable_and_complete():
    fused = FusionResult(probs("sad"), "sad", 0.6, True,
                         ["face"], {"speech": {"probs": probs("sad"), "confidence": 0.7},
                                    "text": {"probs": probs("happy"), "confidence": 0.62}},
                         0.0, 1.0, {})
    est = EmotionEstimate("fused", 0.0, 1.0, fused.probs, valence=-0.4, arousal=0.1,
                          confidence=0.6)
    ev = PerceptionEvent(fused, est, "太好了，又要加班", latency_ms=123.4,
                         t_start=0.0, t_end=1.0, sources={"asr": "sensevoice"})
    cmd = ExpressionCommand("concerned", 0.7, 3.0, est.probs, "语气与字面矛盾")
    rec = build_record(ev, cmd)

    json.dumps(rec)  # 前端直接 JSON 解析，不能有 numpy 类型
    assert rec["fusion"]["conflict"] is True
    assert rec["fusion"]["missing"] == ["face"]
    assert rec["per_modality"]["text"]["label"] == "happy"
    assert rec["per_modality"]["speech"]["label"] == "sad"
    assert rec["expression"]["name"] == "concerned"
    assert rec["latency_ms"] == 123.4
