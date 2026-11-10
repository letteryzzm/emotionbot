import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from head import NAMES  # noqa: E402
from head.actuators import BY_NAME, center  # noqa: E402
from camera.behavior import Behavior, FaceObs, gaze_rest, gaze_to_u, zone  # noqa: E402
from camera.vision import estimate_distance  # noqa: E402


def run(beh, x, y, d, seconds=4.0, t0=0.0, fps=30):
    u = None
    for i in range(int(seconds * fps)):
        t = t0 + i / fps
        u = beh.step(FaceObs(x, y, d, t), t)
    return u


def idx(n):
    return NAMES.index(n)


def test_zones():
    assert [zone(d) for d in (None, 3, 1, 0.35, 0.2)] == ["bored", "bored", "interested", "annoyed", "fear"]


def test_distance_pinhole():
    # 640px 宽、65° 视场：50cm 处瞳距约 63mm -> 像素
    f = 320 / np.tan(np.radians(32.5))
    px = f * 0.063 / 0.5
    assert abs(estimate_distance(px, 640) - 0.5) < 1e-6


def test_gaze_direction_and_range():
    lr_l, ud_up = gaze_to_u(-1, -1)   # 画面左上
    lr_r, ud_dn = gaze_to_u(1, 1)
    assert lr_l > lr_r and ud_up > ud_dn   # 左 = LR 大（LR_UP_IS_ROBOT_LEFT），上 = UD 大
    assert gaze_to_u(0, 0) == gaze_rest()
    assert abs(BY_NAME["UD"].angle(gaze_rest()[1]) - center("UD")) < 1e-6   # 正视回到实测中心，不是行程中点
    assert all(0 <= v <= 1 for v in gaze_to_u(5, -5))


def test_eyes_follow_face():
    b = Behavior(seed=0)
    u = run(b, -0.8, 0.0, 0.8)
    assert u[idx("LR")] > 0.7
    u = run(b, 0.8, 0.0, 0.8, t0=5)
    assert u[idx("LR")] < 0.3


def test_expression_by_distance():
    far, mid, near = Behavior(seed=1), Behavior(seed=1), Behavior(seed=1)
    run(far, 0, 0, 2.5, 8); run(mid, 0, 0, 0.8, 8); run(near, 0, 0, 0.2, 8)
    assert (far.state, mid.state, near.state) == ("bored", "interested", "fear")
    top = lambda b: b.expr[idx("TL")]  # noqa: E731
    assert top(far) < top(mid) <= top(near) + 1e-9    # 无聊眼皮半闭，害怕睁大
    assert mid.expr[idx("CUL")] > 0.6                  # 感兴趣微笑


def test_fast_motion_startles():
    b = Behavior(seed=2)
    run(b, 0, 0, 0.8, 3)
    for i in range(6):   # 突然大幅来回晃
        t = 3 + i / 30
        b.step(FaceObs(0.9 * (-1) ** i, 0, 0.8, t), t)
    assert b._startle_until > 3


def test_lost_face_goes_bored_and_stays_in_range():
    b = Behavior(seed=3)
    run(b, 0, 0, 0.8, 2)
    for i in range(300):
        u = b.step(None, 2 + i / 30)
        assert u.shape == (22,) and 0 <= u.min() and u.max() <= 1
    assert b.state == "bored"


def test_every_zone_has_a_pose_and_steps():
    for d in (3.0, 1.0, 0.35, 0.2):
        b = Behavior(seed=0)
        u = run(b, 0, 0, d, 2)
        assert u.shape == (22,) and 0 <= u.min() and u.max() <= 1


def test_gaze_uses_real_angle_not_servo_limit():
    # 65° 视场的画面边缘只偏 32.5°，舵机不该打到极限
    lr, _ = gaze_to_u(-1, 0)
    assert abs(BY_NAME["LR"].angle(lr) - (center("LR") + 32.5)) < 1e-6
    lr, _ = gaze_to_u(1, 0, gain=1.0, hfov=90)
    assert abs(BY_NAME["LR"].angle(lr) - (center("LR") - 45)) < 1e-6
