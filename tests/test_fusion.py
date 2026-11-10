import numpy as np
import pytest

from perception.fusion import detect_conflict, fuse
from perception.types import LABEL7, ModalityResult, normalize_probs, valence


def mod(name, **probs):
    d = {k: 0.0 for k in LABEL7}
    d.update(probs)
    return ModalityResult(name, d, 0.0, 1.0)


def test_normalize_drops_other_and_sums_to_one():
    p = normalize_probs({"happy": 2.0, "other": 5.0, "unknown": 1.0})
    assert abs(sum(p.values()) - 1.0) < 1e-9
    assert p["happy"] == pytest.approx(1.0)


def test_normalize_empty_is_uniform():
    p = normalize_probs({})
    assert all(v == pytest.approx(1 / 7) for v in p.values())


def test_consistent_modalities_fuse_to_happy():
    r = fuse([mod("face", happy=0.8), mod("speech", happy=0.7), mod("text", happy=0.9)])
    assert r.label == "happy"
    assert not r.conflict
    assert r.missing == []
    assert abs(sum(r.probs.values()) - 1.0) < 1e-9


def test_missing_modalities_lower_confidence():
    full = fuse([mod("face", happy=0.8), mod("speech", happy=0.8), mod("text", happy=0.8)])
    only = fuse([mod("speech", happy=0.8)])
    assert set(only.missing) == {"face", "text"}
    assert only.confidence < full.confidence


def test_contradiction_follows_speech():
    text = mod("text", happy=0.9)
    speech = mod("speech", angry=0.85)
    assert detect_conflict(text, speech)
    r = fuse([text, speech], conflict_min_conf=0.55)
    assert r.conflict
    assert r.label == "angry"
    assert r.detail["text_label"] == "happy"
    assert r.detail["speech_label"] == "angry"


def test_no_conflict_when_one_side_neutral():
    text = mod("text", neutral=0.9)
    speech = mod("speech", angry=0.85)
    assert not detect_conflict(text, speech)
    assert not fuse([text, speech]).conflict


def test_no_conflict_when_not_confident():
    text = mod("text", happy=0.5, neutral=0.5)
    speech = mod("speech", angry=0.5, neutral=0.5)
    assert not detect_conflict(text, speech)


def test_empty_results_are_safe():
    r = fuse([])
    assert r.label == "neutral"
    assert r.confidence == 0.0
    assert abs(sum(r.probs.values()) - 1.0) < 1e-9


def test_valence_signs():
    assert valence({"happy": 1.0}) > 0
    assert valence({"angry": 1.0}) < 0
    assert valence({"neutral": 1.0}) == pytest.approx(0.0)
