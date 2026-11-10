from agent.state import EmotionStateTracker
from perception.types import LABEL7, FusionResult


def fusion(label, peak=0.8, conflict=False, missing=()):
    p = {k: (1 - peak) / 6 for k in LABEL7}
    p[label] = peak
    return FusionResult(p, label, peak, conflict, list(missing),
                        {}, 0.0, 0.0, {})


def test_first_event_passes_through():
    t = EmotionStateTracker(alpha=0.35)
    out = t.update(fusion("happy"))
    assert out.label == "happy"
    assert abs(sum(out.probs.values()) - 1.0) < 1e-9


def test_single_flip_does_not_switch_label():
    t = EmotionStateTracker(alpha=0.35, switch_margin=0.08, confirm_events=99)
    t.update(fusion("happy"))
    out = t.update(fusion("sad", peak=0.45))
    assert out.label == "happy"  # EMA 还是 happy 占优


def test_sustained_flip_switches():
    t = EmotionStateTracker(alpha=0.5, switch_margin=0.05, confirm_events=2)
    t.update(fusion("happy"))
    for _ in range(6):
        out = t.update(fusion("sad", peak=0.9))
    assert out.label == "sad"


def test_conflict_bypasses_smoothing():
    t = EmotionStateTracker()
    t.update(fusion("happy"))
    out = t.update(fusion("sad", peak=0.7, conflict=True))
    assert out.label == "sad"
    assert out.conflict


def test_missing_modalities_lower_confidence():
    t = EmotionStateTracker()
    full = t.update(fusion("happy", peak=0.9))
    t2 = EmotionStateTracker()
    one = t2.update(fusion("happy", peak=0.9, missing=("face", "text")))
    assert one.confidence < full.confidence
