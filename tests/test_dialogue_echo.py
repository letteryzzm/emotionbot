import time

import numpy as np

from agent.dialogue import reply, pick_style
from agent.echo import EchoGate
from agent.idle import mouth_pose
from head.actuators import NAMES, rest_vector
from perception.types import LABEL7, FusionResult


def fusion(label, conflict=False):
    p = {k: 0.05 for k in LABEL7}
    p[label] = 0.7
    return FusionResult(p, label, 0.7, conflict, [], {}, 0.0, 0.0, {})


def test_every_label_has_a_reply():
    for label in LABEL7:
        assert reply(fusion(label)).strip()


def test_conflict_prefers_empathy_template():
    assert pick_style(fusion("happy", conflict=True)) == "conflict"
    assert pick_style(fusion("angry")) == "angry"


def test_echo_gate_mutes_then_expires():
    gate = EchoGate(tail=0.1)
    gate.mute(0.2)
    assert gate.muted()
    time.sleep(0.12)
    assert gate.muted()  # mute 时间未到
    time.sleep(0.25)
    assert not gate.muted()


def test_echo_unmute_is_immediate():
    gate = EchoGate()
    gate.mute(10)
    gate.unmute()
    assert not gate.muted()


def test_mouth_pose_moves_mouth_and_leaves_eyes():
    v = rest_vector()
    out = mouth_pose(v, 0.8)
    jaw = [NAMES.index(n) for n in ("JL", "JR")]
    assert all(out[i] > v[i] for i in jaw)
    eyes = [NAMES.index(n) for n in ("TL", "BL", "TR", "BR", "LR", "UD")]
    assert np.allclose(out[eyes], v[eyes])
    assert out.min() >= 0.0 and out.max() <= 1.0


def test_mouth_pose_clamps_input():
    out = mouth_pose(rest_vector(), 5.0)
    assert out.max() <= 1.0
