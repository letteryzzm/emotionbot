"""表情模仿：镜像方向、基线、平滑。不需要摄像头。"""
import pytest

from camera.mimic import BASE_CAP, Mimic, label, normalize, to_semantic
from culture.actions import REST


def run(blend, frames=12, **kw):
    m = Mimic(**kw)
    for i in range(frames):
        u = m.step(blend, i / 15)
    return u


def test_neutral_face_stays_at_rest():
    u = run({})
    for n in ("TL", "TR", "BL", "BR", "JL", "LR", "UD"):
        assert u[n] == pytest.approx(REST[n], abs=0.02), n


def test_own_left_eye_closes_viewer_left_eye_like_a_mirror():
    k = to_semantic({"eyeBlinkLeft": 0.9})
    assert k["lid_l"] < 0.2 and k["lid_r"] == 1.0
    assert to_semantic({"eyeBlinkLeft": 0.9}, swap=True)["lid_r"] < 0.2


def test_looking_to_own_left_turns_eyes_to_viewer_left():
    assert to_semantic({"eyeLookOutLeft": 0.6, "eyeLookInRight": 0.6})["gx"] < -0.5


def test_smile_and_open_mouth_reach_servos():
    u = run({"mouthSmileLeft": 0.8, "mouthSmileRight": 0.8, "jawOpen": 0.6})
    assert u["CUL"] > REST["CUL"] + 0.3 and u["CUR"] > REST["CUR"] + 0.3 and u["JL"] > 0.5 and u["JL"] == u["JR"]


def test_baseline_removes_resting_squint_but_not_a_quick_expression():
    m = Mimic()
    for i in range(30 * 15):                  # 30 秒一直有 0.3 的眯眼
        m.step({"eyeSquintLeft": 0.3}, i / 15)
    assert m.base["eyeSquintLeft"] == pytest.approx(0.3, abs=0.01)
    m2 = Mimic()
    for i in range(30):                       # 2 秒的笑不会被基线吃掉
        m2.step({"mouthSmileLeft": 0.8}, i / 15)
    assert m2.base["mouthSmileLeft"] < 0.05


def test_baseline_is_capped():
    m = Mimic()
    for i in range(300 * 15):
        m.step({"browDownLeft": 0.9}, i / 15)
    assert m.base["browDownLeft"] <= BASE_CAP


def test_calibration_file_is_the_starting_baseline():
    assert Mimic(neutral={"eyeSquintLeft": 0.4}).base["eyeSquintLeft"] == 0.4
    assert normalize({"eyeSquintLeft": 0.4}, {"eyeSquintLeft": 0.4})["eyeSquintLeft"] == 0


def test_motion_is_smoothed():
    m = Mimic()
    m.step({}, 0)
    u = m.step({"jawOpen": 1.0}, 1 / 15)
    assert 0 < u["JL"] < 1


@pytest.mark.parametrize("blend,name", [
    ({}, "平静"), ({"mouthSmileLeft": 0.7, "mouthSmileRight": 0.7}, "开心"),
    ({"jawOpen": 0.6, "browInnerUp": 0.6}, "惊讶"), ({"browDownLeft": 0.6, "browDownRight": 0.6}, "生气"),
    ({"eyeBlinkLeft": 0.9}, "眨一只眼"), ({"eyeBlinkLeft": 0.9, "eyeBlinkRight": 0.9}, "闭眼"),
])
def test_labels(blend, name):
    assert label(blend) == name
