"""灵眸总控：模式切换、卸力、戏台接管、对账。假服务，不碰硬件和进程。"""
import json
import threading
from http.client import HTTPConnection
from http.server import ThreadingHTTPServer

import pytest

from lingmou import server as L


class Hub:
    def __init__(self):
        self.calls, self.error, self.fail = [], "", set()

    def _post(self, body):
        self.calls.append(("op", body))
        return body.get("op") not in self.fail

    def clear(self, source):
        self.calls.append(("clear", source))
        return True

    def pose(self, source, name, intensity=1.0, ttl=1.0):
        self.calls.append(("pose", source, name, ttl))
        return True

    def intent(self, source, values, ttl=1.0, merge=False):
        self.calls.append(("intent", source, values, ttl, merge))
        return True


class Svc:
    def __init__(self):
        self.up, self.stops = False, 0
        self.note = ""

    def running(self):
        return self.up

    def ensure(self, want):
        self.up = want

    def stop(self):
        self.stops += 1
        self.up = False


@pytest.fixture
def rig(tmp_path):
    posted = []

    def post(url, body, timeout=3.0):
        posted.append((url, body))
        return {"ok": True}

    hub = Hub()
    names = ("hub", "culture", "voice", "camera", "vision", "mimic")
    ctl = L.Controller(hub, {n: Svc() for n in names}, post=post, fetch=lambda *a, **k: {}, settings_path=tmp_path / "s.json")
    return ctl, hub, posted


@pytest.mark.parametrize("mode,camera,cmd,robot,life", [
    ("standby", False, "pause", False, True), ("track", True, "pause", False, True), ("talk", False, "listen", False, True),
    ("interact", True, "listen", False, True), ("opera", False, "pause", True, True), ("manual", False, "pause", False, False),
    ("mimic", True, "pause", False, False),
])
def test_mode_sets_every_part(rig, mode, camera, cmd, robot, life):
    ctl, hub, posted = rig
    ctl.set_mode(mode)
    ctl.reconcile()
    mimic = mode == "mimic"
    assert ctl.services["camera"].up is camera and ctl.services["vision"].up is (camera and not mimic)
    assert ctl.services["mimic"].up is mimic
    assert (L.VOICE + "/cmd", {"cmd": cmd}) in posted
    assert (L.CULTURE + "/api", {"op": "robot", "on": robot}) in posted
    assert ("op", {"op": "life", "on": life}) in hub.calls
    assert ("clear", "manual") in hub.calls and ("clear", "dialog") in hub.calls


def test_estop_releases_first_and_quiets_everything(rig):
    ctl, hub, posted = rig
    ctl.set_mode("interact")
    ctl.preview = True
    hub.calls.clear()
    posted.clear()
    ctl.dispatch({"op": "estop"})
    ctl.reconcile()
    assert hub.calls[0] == ("op", {"op": "estop"})
    assert ctl.mode == "standby" and not ctl.services["camera"].up
    assert (L.VOICE + "/cmd", {"cmd": "pause"}) in posted


def test_estop_failure_still_stops_the_rest(rig):
    ctl, hub, posted = rig
    hub.fail.add("estop")
    ctl.mode = "opera"
    with pytest.raises(L.Refused):
        ctl.estop()
    assert ctl.mode == "standby" and (L.CULTURE + "/api", {"op": "stop"}) in posted


def test_play_takes_over_from_other_modes(rig):
    ctl, _, posted = rig
    ctl.set_mode("interact")
    ctl.dispatch({"op": "play", "action": "numu", "intensity": 0.5})
    assert ctl.mode == "opera"
    assert posted[-1] == (L.CULTURE + "/api", {"op": "play", "action": "numu", "intensity": 0.5})


def test_changing_mode_cancels_tour(rig):
    ctl, _, _ = rig
    ctl.halt.set()     # 线程不实际开演
    ctl.start_tour()
    assert ctl.tour_left
    ctl.set_mode("standby")
    assert ctl.tour_left == []


def test_pose_hold_depends_on_mode(rig):
    ctl, hub, _ = rig
    ctl.pose("happy")
    assert hub.calls[-1] == ("pose", "manual", "happy", L.POSE_TTL)
    ctl.set_mode("manual")
    ctl.pose("happy")
    assert hub.calls[-1] == ("pose", "manual", "happy", L.HOLD_TTL)


def test_servos_enter_manual_and_reject_held_ones(rig):
    ctl, hub, _ = rig
    ctl.dispatch({"op": "servos", "values": {"LR": 0.7}})
    assert ctl.mode == "manual" and hub.calls[-1] == ("intent", "manual", {"LR": 0.7}, L.HOLD_TTL, True)
    for bad in ("LLL", "EXA", "NOPE"):
        with pytest.raises(L.Refused):
            ctl.dispatch({"op": "servos", "values": {bad: 0.5}})


def test_settings_validate_persist_and_restart_only_what_changed(rig):
    ctl, _, _ = rig
    with pytest.raises(L.Refused):
        ctl.dispatch({"op": "settings", "near": 5})
    ctl.dispatch({"op": "settings", "flip_x": True, "near": 0.5})
    assert ctl.services["vision"].stops == 1 and ctl.services["camera"].stops == 0 and ctl.services["voice"].stops == 0
    assert json.loads(ctl.settings_path.read_text())["flip_x"] is True
    ctl.dispatch({"op": "settings", "wake": "小表"})
    assert ctl.services["voice"].stops == 1


def test_reconcile_repairs_voice_and_robot_flags(rig):
    ctl, _, posted = rig
    ctl.mode = "talk"
    ctl.snap["voice"] = {"paused": True}
    ctl.snap["opera"] = {"robot": True}
    ctl.reconcile()
    assert (L.VOICE + "/cmd", {"cmd": "listen"}) in posted and (L.CULTURE + "/api", {"op": "robot", "on": False}) in posted


def test_frozen_camera_is_not_treated_as_live():
    now = [0.0]
    ctl = L.Controller(Hub(), {"camera": Svc(), "voice": Svc()}, clock=lambda: now[0])
    ctl.snap["camera"] = {"fps": 10.0, "face": True, "dist": 0.8, "x": 0, "y": 0}
    assert ctl.camera_view()["face"] is True
    now[0] = L.CAMERA_STALE_S + 1
    view = ctl.camera_view()
    assert view["ok"] is False and view["face"] is False and view["dist"] is None


def test_camera_is_found_by_name_not_number(tmp_path):
    for n, name, idx in ((0, "USB2.0 HD UVC WebCam", 0), (2, "USB 2.0 Camera: SHUNCCM", 0), (3, "USB 2.0 Camera: SHUNCCM", 1)):
        d = tmp_path / f"video{n}"
        d.mkdir()
        (d / "name").write_text(name)
        (d / "index").write_text(str(idx))
    assert L.camera_index(tmp_path) == 2
    assert L.camera_index(tmp_path / "none") is None


@pytest.fixture
def web(rig):
    ctl = rig[0]
    srv = ThreadingHTTPServer(("127.0.0.1", 0), L.make_handler(ctl))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    yield ctl, lambda: HTTPConnection("127.0.0.1", srv.server_address[1], timeout=2)
    srv.shutdown()


def test_cross_site_post_blocked(web):
    ctl, conn = web
    c = conn()
    c.request("POST", "/api", json.dumps({"op": "mode", "mode": "opera"}))
    assert c.getresponse().status == 403 and ctl.mode == "standby"


def test_refused_command_shows_message(web):
    _, conn = web
    c = conn()
    c.request("POST", "/api", json.dumps({"op": "mode", "mode": "nope"}), {"X-Head": "1"})
    r = c.getresponse()
    assert r.status == 400 and json.loads(r.read())["error"] == "没有这个模式"


@pytest.mark.parametrize("path", ["/", "/demo", "/face.js", "/meta"])
def test_pages_are_served(web, path):
    _, conn = web
    c = conn()
    c.request("GET", path)
    assert c.getresponse().status == 200


def test_camera_url_with_timestamp_reaches_the_proxy(web):
    _, conn = web
    c = conn()
    c.request("GET", "/cam?123")
    assert c.getresponse().status == 503      # 摄像头没开，但路由到了


def test_out_of_balance_is_explained():
    ctl = L.Controller(Hub(), {"voice": Svc()})
    ctl.snap["voice"] = {"paused": False, "voice": {"error": "HTTPError: HTTP Error 402: Payment Required", "all": []}}
    assert "余额不足" in ctl.voice_view()["error"]


def test_mimic_calibration_needs_a_face_and_writes_file(rig, tmp_path, monkeypatch):
    ctl, _, _ = rig
    monkeypatch.setattr(L, "NEUTRAL_FILE", tmp_path / "n.json")
    ctl.snap["camera"] = {"face": False}
    with pytest.raises(L.Refused):
        ctl.dispatch({"op": "mimic_calibrate"})
    ctl.snap["camera"] = {"face": True, "blend": {"eyeSquintLeft": 0.3}}
    ctl.dispatch({"op": "mimic_calibrate"})
    assert json.loads((tmp_path / "n.json").read_text()) == {"eyeSquintLeft": 0.3}
    ctl.dispatch({"op": "settings", "mimic_swap": True})
    assert ctl.services["mimic"].stops == 1


def test_camera_view_reports_expression():
    now = [0.0]
    ctl = L.Controller(Hub(), {"camera": Svc(), "voice": Svc()}, clock=lambda: now[0])
    ctl.neutral = {}
    ctl.snap["camera"] = {"fps": 9.0, "face": True, "dist": 0.8, "x": 0, "y": 0,
                          "blend": {"mouthSmileLeft": 0.8, "mouthSmileRight": 0.8}}
    v = ctl.camera_view()
    assert v["expr"] == "开心" and v["top"][0][0].startswith("mouthSmile")
