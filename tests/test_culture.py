"""灵眸戏台：动作库、模型结果校验、播放器。不联网，不碰硬件。"""
import json
import threading
import types

import cv2
import numpy as np
import pytest

from culture import analyze as an
from culture.actions import ACTIONS, EXCLUDE, REST, sample, semantic_to_u
from culture.server import Stage, make_handler


def jpeg(w=800, h=400):
    return cv2.imencode(".jpg", np.full((h, w, 3), 120, np.uint8))[1].tobytes()


def reply(obj):
    return 200, json.dumps(obj, ensure_ascii=False)


GOOD = {"category": "opera", "subject": "白脸", "evidence": "白色脸谱", "action": "lengxiao", "intensity": 0.9, "confidence": 0.8}


@pytest.fixture(autouse=True)
def tmp_cache(tmp_path, monkeypatch):
    monkeypatch.setattr(an, "CACHE", tmp_path / "cache")


@pytest.mark.parametrize("action", ACTIONS.values(), ids=lambda a: a.id)
def test_action_stays_in_range_and_returns_to_rest(action):
    times = [f.t for f in action.frames]
    assert times == sorted(times) and len(set(times)) == len(times)
    for t in np.arange(0, action.duration + 0.05, 0.02):
        u, _ = sample(action, float(t))
        assert all(0 <= v <= 1 for v in u.values())
        assert not EXCLUDE & set(u)
        assert u["JL"] == pytest.approx(u["JR"], abs=1e-3) or REST["JL"] != REST["JR"]
    start, _ = sample(action, 0)
    end, _ = sample(action, action.duration)
    for n, v in REST.items():
        if n not in EXCLUDE:
            assert start[n] == pytest.approx(v) and end[n] == pytest.approx(v)


def test_snap_arrives_quickly_after_holding_previous_pose():
    a = ACTIONS["liangxiang"]
    before, _ = sample(a, 1.85)
    after, beat = sample(a, 2.0)
    assert beat == "亮相！" and after["LO"] != before["LO"] and after["TL"] > before["TL"]


def test_viewer_sides_map_to_correct_servos():
    u = semantic_to_u({"lid_l": 0.1, "lid_r": 0.9, "smile_l": 1})
    assert u["TL"] == 0.1 and u["TR"] == 0.9          # 眼部 L = 观众左
    assert u["CUR"] == 1 and u["CUL"] == pytest.approx(REST["CUL"])   # 嘴部 L = 观众右


def test_gaze_positive_is_viewer_right_which_is_robot_left():
    assert semantic_to_u({"gx": 1})["LR"] == 1


def test_intensity_scales_toward_rest():
    a = ACTIONS["numu"]
    full, _ = sample(a, 3.0, 1.0)
    half, _ = sample(a, 3.0, 0.5)
    assert half["TL"] == pytest.approx((full["TL"] + REST["TL"]) / 2)


def test_prompt_lists_every_action():
    assert all(i in an.prompt() for i in ACTIONS)


def test_analyze_validates_and_caches():
    calls = []

    def post(body):
        calls.append(body)
        return reply(GOOD)

    r = an.analyze(jpeg(), post)
    assert r["action"] == "lengxiao" and r["cached"] is False
    assert an.analyze(jpeg(), post)["cached"] is True and len(calls) == 1


def test_upload_is_shrunk_before_sending():
    calls = []
    an.analyze(jpeg(3000, 1500), lambda b: calls.append(b) or reply(GOOD))
    import base64

    url = calls[0]["messages"][0]["content"][0]["image_url"]["url"]
    data = base64.b64decode(url.split(",", 1)[1])
    assert max(cv2.imdecode(np.frombuffer(data, np.uint8), 1).shape) == an.MAX_SIDE


@pytest.mark.parametrize("patch,want", [({"action": "nope"}, None), ({"action": "happy"}, None), ({"action": None}, None)])
def test_invented_or_mismatched_action_is_not_played(patch, want):
    assert an.analyze(jpeg(), lambda b: reply({**GOOD, **patch}))["action"] is want


def test_numbers_are_clamped_and_bad_values_defaulted():
    r = an.analyze(jpeg(), lambda b: reply({**GOOD, "intensity": 99, "confidence": "很高"}))
    assert r["intensity"] == 1.0 and r["confidence"] == 0.5


def test_other_category_has_no_action():
    r = an.analyze(jpeg(), lambda b: reply({**GOOD, "category": "other", "action": "numu"}))
    assert r["category"] == "other" and r["action"] is None


@pytest.mark.parametrize("post,msg", [
    (lambda b: (429, ""), "太忙"), (lambda b: (503, ""), "太忙"), (lambda b: (401, ""), "401"),
    (lambda b: (200, "没有括号"), "没有返回"), (lambda b: (200, ""), "没有返回"), (lambda b: (200, "{坏"), "没有返回"),
    (lambda b: (200, "{坏}"), "格式不对"),
])
def test_service_failures_become_user_messages(post, msg):
    with pytest.raises(an.AnalyzeError, match=msg):
        an.analyze(jpeg(), post)


def test_network_failure_message():
    def post(body):
        raise OSError("down")

    with pytest.raises(an.AnalyzeError, match="连不上"):
        an.analyze(jpeg(), post)


def test_failed_result_is_not_cached():
    with pytest.raises(an.AnalyzeError):
        an.analyze(jpeg(), lambda b: (503, ""))
    assert an.analyze(jpeg(), lambda b: reply(GOOD))["action"] == "lengxiao"


@pytest.mark.parametrize("data", [b"", b"not an image", b"x" * (an.MAX_UPLOAD + 1)])
def test_bad_files_are_rejected_before_any_upload(data):
    with pytest.raises(an.AnalyzeError):
        an.analyze(data, lambda b: pytest.fail("不该上传"))


class FakeHub:
    def __init__(self):
        self.sent = []

    def intent(self, source, values, ttl):
        self.sent.append(("intent", source, values, ttl))
        return True

    def clear(self, source):
        self.sent.append(("clear", source))
        return True


def rig():
    clock = types.SimpleNamespace(t=10.0)
    hub = FakeHub()
    return Stage(hub, clock=lambda: clock.t), clock, hub


def test_robot_gets_nothing_unless_enabled():
    s, clock, _ = rig()
    s.play("numu")
    clock.t += 1
    s.step()
    assert s.pending is None and s.state()["playing"] == "numu" and s.state()["beat"]


def test_robot_receives_frames_then_clear():
    s, clock, _ = rig()
    s.set_robot(True)
    s.pending = None
    s.play("shock", 1.0)
    clock.t += 1
    s.step()
    assert isinstance(s.pending, dict) and "EXA" not in s.pending
    clock.t += 10
    s.step()
    assert s.pending == "clear" and s.state()["playing"] is None and s.state()["beat"] == ""


def test_face_returns_to_rest_when_done():
    s, clock, _ = rig()
    s.play("shock")
    clock.t += 1
    s.step()
    assert s.u["JL"] > 0.5
    clock.t += 10
    s.step()
    assert s.u["JL"] == REST["JL"]


def test_sender_only_keeps_latest_frame_and_survives_missing_hub():
    s, clock, hub = rig()
    t = threading.Thread(target=s.sender, daemon=True)
    t.start()
    s.pending = {"LR": 0.5}
    s.send_event.set()
    for _ in range(100):
        if hub.sent:
            break
        threading.Event().wait(0.01)
    s.halt.set()
    assert hub.sent[0][1] == "dialog" and hub.sent[0][3] == 0.6


def test_unknown_action_rejected():
    s, _, _ = rig()
    with pytest.raises(ValueError):
        s.play("nope")


@pytest.fixture
def client():
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer

    s, _, _ = rig()
    srv = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(s))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield s, lambda: HTTPConnection("127.0.0.1", srv.server_address[1], timeout=2)
    srv.shutdown()


def test_cross_site_requests_blocked(client):
    s, conn = client
    c = conn()
    c.request("POST", "/api", json.dumps({"op": "play", "action": "numu"}))
    assert c.getresponse().status == 403 and s.action is None


def test_path_traversal_on_samples_is_blocked(client):
    _, conn = client
    c = conn()
    c.request("GET", "/samples/..%2Fanalyze.py")
    assert c.getresponse().status == 404
    c = conn()
    c.request("GET", "/samples/../analyze.py")
    assert c.getresponse().status == 404


def test_meta_never_contains_the_key(client, monkeypatch):
    monkeypatch.setenv("CULTURE_API_KEY", "secret-value-for-test")
    _, conn = client
    c = conn()
    c.request("GET", "/meta")
    assert b"secret-value-for-test" not in c.getresponse().read()
