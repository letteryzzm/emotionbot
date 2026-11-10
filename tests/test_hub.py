"""统一控制进程：用真实固件逻辑当假串口，不碰硬件。"""
import importlib.util
import json
import sys
import threading
import time
import types
from http.server import ThreadingHTTPServer
from pathlib import Path

import numpy as np
import pytest

from head.actuators import ACTUATORS, BY_NAME, NAMES, rest_vector
from head.hub import PRIORITY, Hub, Life, Mixer, Refused, load_verified
from head.hub_client import HubClient
from head.hub_server import dispatch, make_handler, pose_values

FW = Path(__file__).resolve().parent.parent / "firmware"
ALL = {a.name: (min(a.a, a.b), max(a.a, a.b)) for a in ACTUATORS}


class FakeServo:
    def __init__(self, pin):
        self.deg, self.on = None, False

    def write(self, deg):
        self.deg, self.on = deg, True

    def off(self):
        self.on = False


def load_firmware(role):
    spec = importlib.util.spec_from_file_location(f"cfg_{role}", FW / f"config_{role}.py")
    cfg = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cfg)
    old = {k: sys.modules.get(k) for k in ("config", "servo")}
    sys.modules["config"] = cfg
    sys.modules["servo"] = types.SimpleNamespace(Servo=FakeServo)
    spec = importlib.util.spec_from_file_location(f"fw_{role}", FW / "main.py")
    fw = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(fw)
    for k, v in old.items():
        if v is None:
            sys.modules.pop(k, None)
        else:
            sys.modules[k] = v
    fw.setup()
    return fw


class FwLink:
    """串口接口，背后是真实固件的 safe_handle。"""

    def __init__(self, fw):
        self.fw, self.reply, self.sent, self.closed, self.dead, self.silent = fw, "", [], False, False, False

    def write(self, data):
        if self.dead:
            raise OSError("write failed")
        line = data.decode().strip()
        self.sent.append(line)
        r = self.fw.safe_handle(line)
        self.reply = "" if self.silent else r or ""

    def readline(self):
        r, self.reply = self.reply, ""
        return (r + "\n").encode() if r else b""

    def close(self):
        self.closed = True


@pytest.fixture
def rig():
    links = {b: FwLink(load_firmware(b)) for b in ("eyes", "brows", "mouth")}
    clock = types.SimpleNamespace(t=100.0)
    hub = Hub(opener=lambda: links, limits=dict(ALL), clock=lambda: clock.t, seed=1)
    hub.set_life(False)
    return hub, links, clock


def run(hub, clock, seconds, dt=0.02):
    for _ in range(int(seconds / dt)):
        clock.t += dt
        hub.step()
        for w in list(hub.workers.values()):
            w.cycle(clock.t)
    hub.step()


def test_priority_order_matches_design():
    order = sorted(PRIORITY, key=PRIORITY.get)
    assert order == ["idle", "vision", "dialog", "lips", "manual", "reflex"]


def test_higher_layer_only_overrides_servos_it_names():
    m = Mixer()
    m.set("vision", {"LR": 0.2, "CUL": 0.1}, 1, 0)
    m.set("dialog", {"CUL": 0.9}, 1, 0)
    v, order = m.compose(0.5)
    assert v[NAMES.index("LR")] == 0.2 and v[NAMES.index("CUL")] == 0.9
    assert order == ["vision", "dialog"]


def test_crashed_source_expires_back_to_lower_layer():
    m = Mixer()
    m.set("vision", {"CUL": 0.1}, 10, 0)
    m.set("dialog", {"CUL": 0.9}, 0.5, 0)
    assert m.compose(0.4)[0][NAMES.index("CUL")] == 0.9
    v, order = m.compose(0.6)
    assert v[NAMES.index("CUL")] == 0.1 and order == ["vision"]


@pytest.mark.parametrize("args", [("nope", {"LR": 1}, 1), ("vision", {"XX": 1}, 1), ("vision", {"LR": float("nan")}, 1),
                                  ("vision", {"LR": 1}, -1), ("vision", {"LR": 1}, 1e9)])
def test_mixer_rejects_bad_intent(args):
    with pytest.raises(Refused):
        Mixer().set(*args, 0)


@pytest.mark.parametrize("source", ["idle", "reflex"])
def test_outside_programs_cannot_write_internal_layers(rig, source):
    with pytest.raises(Refused):
        rig[0].intent(source, {"LR": 1})


def test_blink_closes_and_reopens_lids():
    life = Life(seed=1)
    life._blink(10.0)
    assert life.update(10.07)[1]["TL"] == 0
    assert life.update(10.2)[1]["TL"] > 0
    assert life.update(10.4)[1] is None


def test_blink_overrides_expression_but_not_gaze(rig):
    hub, _, clock = rig
    hub.set_life(True)
    hub.intent("manual", {"LR": 0.9, "TL": 0.8}, ttl=None)
    hub.life._blink(clock.t)
    run(hub, clock, 0.06)
    assert hub.v[NAMES.index("TL")] < 0.1
    run(hub, clock, 0.5)
    assert hub.v[NAMES.index("LR")] == pytest.approx(0.9)


def test_unverified_servos_never_get_commands():
    hub = Hub(opener=None, limits={"LR": (80, 100), "UD": (80, 100)}, clock=lambda: 0)
    assert hub.drivable() == ["LR", "UD"]
    v = np.ones(len(NAMES))
    assert hub.commands(v)["LR"] == 100


def test_arm_refused_when_nothing_is_calibrated():
    hub = Hub(opener=lambda: pytest.fail("不该打开串口"), limits={})
    with pytest.raises(Refused, match="标定"):
        hub.arm()


@pytest.mark.parametrize("limits", [{"JL": (50, 90)}, {"JR": (90, 130)}])
def test_jaw_never_driven_from_one_side(limits):
    assert Hub(opener=None, limits=limits).drivable() == []


def test_jaw_pair_stays_mirrored_inside_tighter_side():
    hub = Hub(opener=None, limits={"JL": (70, 90), "JR": (90, 130)})
    v = rest_vector()
    v[NAMES.index("JL")], v[NAMES.index("JR")] = 1.0, 0.3
    c = hub.commands(v)
    assert c["JL"] + c["JR"] == 180 and c["JR"] <= 110


def test_spare_port_is_never_driven(rig):
    assert "EXA" not in rig[0].commands(rest_vector())


def test_control_goes_through_firmware_with_watchdog(rig):
    hub, links, clock = rig
    hub.intent("manual", {"LR": 1.0}, ttl=None)
    hub.arm(start_threads=False)
    assert links["eyes"].fw.handle("W") == "W 1000"
    run(hub, clock, 1.0)
    assert links["eyes"].fw.tgt["LR"] == BY_NAME["LR"].angle(1.0)
    assert "EXA" not in links["mouth"].fw.active
    run(hub, clock, 3.0)
    assert links["eyes"].sent.count("V 300") == 1


def test_only_changes_are_sent(rig):
    hub, links, clock = rig
    hub.arm(start_threads=False)
    run(hub, clock, 3.5)
    links["eyes"].sent.clear()
    run(hub, clock, 1.0)
    assert not [s for s in links["eyes"].sent if s.startswith("S ")]
    assert [s for s in links["eyes"].sent if s.startswith("W ")]


def test_process_death_is_handled_by_firmware(rig):
    hub, links, clock = rig
    hub.intent("manual", {"LR": 1.0}, ttl=None)
    hub.arm(start_threads=False)
    run(hub, clock, 1.0)
    fw = links["eyes"].fw
    for _ in range(340):   # 主机不再发任何东西
        fw.watchdog(10)
        fw.tick(0.01)
    assert not any(s.on for s in fw.servos.values())


def test_old_firmware_is_refused_and_ports_closed(rig):
    hub, links, _ = rig
    links["brows"].fw.safe_handle = lambda line: "ERR unknown command"
    with pytest.raises(Refused, match="重刷"):
        hub.arm(start_threads=False)
    assert all(l.closed for l in links.values()) and not hub.workers


def test_missing_board_is_refused(rig):
    hub, links, _ = rig
    del links["mouth"]
    with pytest.raises(Refused, match="mouth"):
        hub.arm(start_threads=False)


def test_board_loss_releases_everything_and_latches(rig):
    hub, links, clock = rig
    hub.arm(start_threads=False)
    run(hub, clock, 0.5)
    links["brows"].dead = True
    run(hub, clock, 0.5)
    assert "brows" in hub.state()["fault"] and not hub.workers
    for b in ("eyes", "mouth"):
        assert not any(s.on for s in links[b].fw.servos.values()) and links[b].closed
    assert hub.state()["armed"] == []


def test_silent_board_faults_after_misses(rig):
    hub, links, clock = rig
    hub.arm(start_threads=False)
    links["eyes"].silent = True
    run(hub, clock, 1.0)
    assert "没有回应" in hub.state()["fault"]


def test_stalled_control_loop_stops_feeding_watchdog(rig):
    hub, links, clock = rig
    hub.arm(start_threads=False)
    run(hub, clock, 0.5)
    links["eyes"].sent.clear()
    clock.t += 1.0                     # 控制循环这段时间没跑
    hub.workers["eyes"].cycle(clock.t)
    assert not links["eyes"].sent and "卡住" in hub.fault_msg
    hub.step()
    assert not hub.workers


def test_estop_works_and_needs_rearm(rig):
    hub, links, clock = rig
    hub.arm(start_threads=False)
    run(hub, clock, 0.5)
    dispatch(hub, {"op": "estop"})
    assert not any(s.on for l in links.values() for s in l.fw.servos.values())
    assert all(l.fw.handle("W") == "W 0" for l in links.values())
    run(hub, clock, 0.5)
    assert not any(s.on for l in links.values() for s in l.fw.servos.values())


def test_real_threads_shutdown_cleanly():
    links = {b: FwLink(load_firmware(b)) for b in ("eyes", "brows", "mouth")}
    hub = Hub(opener=lambda: links, limits=dict(ALL), seed=1)
    t = threading.Thread(target=hub.run, daemon=True)
    t.start()
    hub.arm()
    time.sleep(0.3)
    assert hub.state()["armed"] == ["brows", "eyes", "mouth"] and links["eyes"].sent
    hub.stop()
    t.join(1)
    assert all(l.closed for l in links.values())


def test_load_verified_uses_last_range_inside_config(tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text("\n".join([
        json.dumps({"type": "range", "servo": "LR", "lo": 0, "hi": 80}),
        json.dumps({"type": "range", "servo": "LR", "lo": 60, "hi": 200}),
        "坏行",
        json.dumps({"type": "range", "servo": "NOPE", "lo": 1, "hi": 2}),
    ]))
    assert load_verified(p) == {"LR": (60, 140)}
    assert load_verified(tmp_path / "none") == {}


def test_pose_values_only_touch_named_servos():
    v = pose_values("happy", 0.5)
    assert "LR" not in v and "CUL" in v
    assert pose_values("neutral", 1) == {}
    with pytest.raises(Refused):
        pose_values("nope", 1)


@pytest.fixture
def server(rig):
    hub = rig[0]
    s = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(hub))
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield hub, s.server_address[1]
    s.shutdown()


def test_client_round_trip_and_errors(server):
    hub, port = server
    c = HubClient(port=port)
    assert c.pose("dialog", "happy", 0.5, ttl=5)
    assert "dialog" in hub.mixer.layers
    assert not c.intent("vision", {"XX": 1}) and "没有这个舵机" in c.error
    assert c.clear("dialog") and "dialog" not in hub.mixer.layers
    c.close()


def test_cross_site_post_is_blocked(server):
    import http.client

    hub, port = server
    conn = http.client.HTTPConnection("127.0.0.1", port)
    conn.request("POST", "/api", json.dumps({"op": "arm"}), {"Content-Type": "application/json"})
    assert conn.getresponse().status == 403 and not hub.workers


def test_client_survives_missing_server():
    c = HubClient(port=1)
    assert c.intent("vision", {"LR": 0.5}) is False and c.error


def test_allow_unverified_uses_config_range_and_holds_lower_lips():
    from head.actuators import BY_NAME, NAMES, rest_vector
    from head.hub import Hub

    h = Hub(opener=dict, limits={"CUL": (80.0, 90.0)}, allow_unverified=True)
    v = rest_vector()
    v[NAMES.index("CUL")] = 1.0
    v[NAMES.index("LLL")] = 1.0
    out = h.commands(v)
    assert out["CUL"] == BY_NAME["CUL"].b and out["LLL"] == 90.0 and out["LLR"] == 90.0 and "EXA" not in out
