import numpy as np
import pytest

from agent.composite import ALL_EXPRESSIONS, expression_vector
from agent.policy import decide
from perception.types import LABEL7, FusionResult


def fuse(label, conf, conflict=False):
    probs = {k: (1 - conf) / 6 for k in LABEL7}
    probs[label] = conf
    return FusionResult(probs=probs, label=label, confidence=conf,
                        conflict=conflict, missing=["face"])


def test_happy_maps_to_happy():
    cmd = decide(fuse("happy", 0.9))
    assert cmd.name == "happy"
    assert cmd.intensity == pytest.approx(0.8)
    assert cmd.vector.shape == (22,)
    assert np.all((cmd.vector >= 0) & (cmd.vector <= 1))


def test_angry_is_tempered():
    assert decide(fuse("angry", 0.9)).intensity < decide(fuse("happy", 0.9)).intensity


def test_conflict_maps_to_concerned_even_if_label_is_positive():
    cmd = decide(fuse("happy", 0.8, conflict=True))
    assert cmd.name == "concerned"
    assert cmd.intensity > 0


def test_low_confidence_does_not_react():
    cmd = decide(fuse("happy", 0.3))
    assert cmd.name == "neutral"
    assert cmd.intensity == 0
    assert not cmd.is_active


def test_neutral_does_not_react():
    assert decide(fuse("neutral", 0.9)).name == "neutral"


def test_all_expressions_render_in_range():
    for name in ALL_EXPRESSIONS:
        v = expression_vector(name, 1.0)
        assert v.shape == (22,)
        assert np.all((v >= 0) & (v <= 1)), name


def test_unknown_expression_raises():
    with pytest.raises(KeyError):
        expression_vector("nonexistent")
