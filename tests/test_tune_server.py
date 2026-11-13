"""调试台的安全规则：用假串口测，不碰硬件。"""
import importlib.util
from pathlib import Path

import pytest

from head.actuators import ACTUATORS

path = Path(__file__).resolve().parent.parent / "scripts" / "tune_server.py"
spec = importlib.util.spec_from_file_location("tune_server", path)
ts = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ts)


class FakeLink:
    def __init__(self, board):
        self.ang = {a.name: 90.0 for a in ACTUATORS if a.board == board}
        self.sent = []
        self.reply = ""

    def write(self, data):
        line = data.decode().strip()
        self.sent.append(line)
        parts = line.split()
        self.reply = "OK"
        if parts[0] == "G":
            self.reply = "A " + " ".join(f"{k}={v}" for k, v in self.ang.items())
        elif parts[0] == "S":
            for kv in parts[1:]:
                n, _, v = kv.partition("=")
                self.ang[n] = float(v)

    def readline(self):
        return (self.reply + "\n").encode()


@pytest.fixture
def bench(tmp_path):
    links = {b: FakeLink(b) for b in ("eyes", "brows", "mouth")}
    logged = []
    b = ts.Bench(links, log=logged.append, settle=0, pace=0,
                 library_path=tmp_path / "expressions.json", mode="sim",
                 blocked={"EXA": "未接通道"})  # 原有通用控制测试不依赖现场故障状态。
    b.log_path = tmp_path / "tune_log.jsonl"
    b.logged = logged
    return b


def sent(bench, board):
    return [x for x in bench.links[board].sent if x != "G"]


def test_startup_sends_only_reads(bench):
    assert all(set(link.sent) == {"G"} for link in bench.links.values())


def test_power_releases_other_boards(bench):
    bench.power(["LLL", "LLR"])
    assert sent(bench, "eyes") == ["X"] and sent(bench, "brows") == ["X"]
    assert sent(bench, "mouth") == [f"V {ts.SPEED}", "O LLL LLR"]
    assert bench.powered == {"LLL", "LLR"}


def test_power_rejects_mixed_group(bench):
    with pytest.raises(ts.Refused):
        bench.power(["TON", "LLL"])
    assert bench.powered == set()


def test_move_needs_power(bench):
    with pytest.raises(ts.Refused):
        bench.move({"TON": 5})
    assert "S" not in " ".join(sent(bench, "mouth"))


def test_move_step_limit(bench):
    bench.power(["TON"])
    with pytest.raises(ts.Refused):
        bench.move({"TON": 6})
    bench.move({"TON": 5})
    assert bench.angles["TON"] == 95


def test_move_stays_in_config(bench):
    bench.power(["JL", "JR"])
    with pytest.raises(ts.Refused):
        bench.move({"JL": 5, "JR": -5})   # JL 上限 90


def test_jaw_cannot_skew(bench):
    bench.power(["JL", "JR"])
    bench.move({"JL": -5})                # 单侧 5° 允许
    with pytest.raises(ts.Refused):
        bench.move({"JL": -1})
    bench.move({"JR": 5})
    bench.move({"JL": -5, "JR": 5})
    assert bench.angles["JL"] + bench.angles["JR"] == 180


def test_relax_continues_after_failed_board(bench):
    bench.power(["TON"])
    bench.links["brows"].write = lambda data: (_ for _ in ()).throw(OSError("gone"))
    with pytest.raises(ts.Refused):
        bench.relax()
    assert "X" in sent(bench, "eyes") and sent(bench, "mouth")[-1] == "X"
    assert bench.powered == set()


def test_disconnect_clears_power(bench):
    bench.power(["TON"])
    bench.links["mouth"].write = lambda data: (_ for _ in ()).throw(OSError("gone"))
    with pytest.raises(ts.Refused):
        bench.move({"TON": 1})
    assert bench.powered == set() and "mouth" not in bench.links


def test_pose_records_powered_only(bench):
    bench.power(["TON"])
    bench.move({"TON": 5})
    bench.pose("舌头下", "")
    assert bench.logged[-1]["steps"] == ["S TON=95"]


def test_add_group_keeps_previous_pose_and_power(bench):
    bench.enable_group(["TON"])
    bench.move({"TON": 5})
    bench.enable_group(["LI", "RI"])
    assert bench.powered == {"TON", "LI", "RI"}
    assert bench.angles["TON"] == 95
    assert not any(cmd.startswith(("O", "X")) for board in ts.BOARDS for cmd in sent(bench, board))
    bench.home(names=["LI", "RI"])
    finish(bench)
    assert bench.angles["TON"] == 95


def calibrated(bench):
    bench.enable_group(["TON"])
    bench.enable_group(["UD"])
    bench.links["eyes"].ang["UD"] = 120
    bench.save_expression("neutral", revision=0)
    bench.move({"TON": 5})
    bench.move({"UD": 5})
    bench.save_expression("happy", revision=1, title="笑", text="测试")


def test_preview_has_no_serial_io_and_raw_angles_replay_once(bench):
    calibrated(bench)
    before = {b: list(link.sent) for b, link in bench.links.items()}
    bench.load_expression("happy", 0.5)
    assert bench.preview["angles"] == {"TON": 92.5, "UD": 122.5}
    assert before == {b: link.sent for b, link in bench.links.items()}
    bench.emotion("happy", intensity=0.5, transition=0.2)
    finish(bench)
    assert bench.angles["UD"] == 122.5  # 不再加 UD 的 +30° 中心补偿
    assert bench.angles["TON"] == 92.5
    assert not bench.error


def test_hold_returns_to_calibrated_neutral(bench):
    calibrated(bench)
    bench.emotion("happy", transition=0.2, hold=0)
    finish(bench)
    assert bench.angles["UD"] == 120
    assert bench.angles["TON"] == 90
    assert bench.logged[-1]["type"] == "replay"


def test_busy_save_and_external_power_rejected(bench):
    calibrated(bench)
    bench.enable_group(["LR"])
    with pytest.raises(ts.Refused, match="基准之外"):
        bench.emotion("happy")
    bench.relax()
    bench.pace = 1
    bench.emotion("happy", transition=10)
    try:
        with pytest.raises(ts.Refused, match="停止"):
            bench.save_expression("happy", revision=2)
        with pytest.raises(ts.Refused, match="当前有动作"):
            bench.emotion("neutral")
    finally:
        bench.relax()
        finish(bench)
    assert all(sent(bench, b)[-1] == "X" for b in ts.BOARDS)
    assert not bench.powered
    assert not any(row["type"] == "replay" for row in bench.logged)


def test_replay_rejects_offline_board_before_any_motor_write(bench):
    calibrated(bench)
    bench.relax()
    bench.links.pop("eyes")
    before = len(sent(bench, "mouth"))
    with pytest.raises(ts.Refused, match="不在线"):
        bench.emotion("happy")
    assert len(sent(bench, "mouth")) == before


def test_replay_respects_new_measured_range(bench):
    calibrated(bench)
    bench.log_path.write_text('{"type":"range","servo":"TON","lo":85,"hi":92}\n')
    with pytest.raises(ts.Refused, match="实测范围"):
        bench.emotion("happy")


def test_transition_caps_steps_and_preserves_paired_jaw():
    frames = ts.Bench._transition({"JL": 90, "JR": 90}, {"JL": 30, "JR": 150}, 0.2)
    last = {"JL": 90, "JR": 90}
    for f in frames:
        assert abs(f.goal["JL"] - last["JL"]) <= 5
        assert f.goal["JL"] + f.goal["JR"] == 180
        last = f.goal
    assert sum(f.hold for f in frames) == pytest.approx(0.6)


def test_http_save_restart_preview_and_label_call(bench):
    import json
    import threading
    from contextlib import contextmanager
    from http.client import HTTPConnection
    from http.server import ThreadingHTTPServer

    @contextmanager
    def running(b):
        server = ThreadingHTTPServer(("127.0.0.1", 0), ts.make_handler(b))
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        def request(body, method="POST", path="/api", header=True):
            conn = HTTPConnection(*server.server_address, timeout=2)
            try:
                conn.request(method, path, json.dumps(body), {"X-Head": "1"} if header else {})
                response = conn.getresponse()
                return response.status, json.loads(response.read())
            finally:
                conn.close()
        try:
            yield request
        finally:
            server.shutdown()
            server.server_close()
            thread.join(2)

    with running(bench) as call:
        for body in ({"op": "enable_group", "names": ["TON"]},
                     {"op": "save_expression", "label": "neutral", "revision": 0},
                     {"op": "move", "deltas": {"TON": 5}},
                     {"op": "save_expression", "label": "happy", "revision": 1}):
            code, result = call(body)
            assert code == 200, result
        assert call({}, method="GET", path="/expressions.json")[1]["revision"] == 2
        assert call([1, 2])[0] == 400
        assert call({"op": "typo"})[0] == 400
        assert call({"op": "state"}, header=False)[0] == 403

    restored = ts.Bench({b: FakeLink(b) for b in ts.BOARDS}, log=lambda row: None, settle=0, pace=0,
                        library_path=bench.library.path, mode="sim")
    restored.log_path = bench.log_path
    with running(restored) as call:
        code, result = call({"op": "load_expression", "label": "happy"})
        assert code == 200 and result["state"]["preview"]["angles"] == {"TON": 95}
        assert all(set(link.sent) == {"G"} for link in restored.links.values())
        assert call({"op": "emotion", "label": "fear"})[0] == 400
        assert call({"op": "emotion", "label": "happy", "revision": 1})[0] == 400
        assert call({"op": "emotion", "label": "happy", "intensity": 0.5})[0] == 200
        finish(restored)
        assert call({}, method="GET", path="/state")[1]["angles"]["TON"] == 92.5


def moves(bench, board="mouth"):
    return [x for x in sent(bench, board) if x.startswith("S ")]


def finish(bench):
    bench.job.join(2)
    assert not bench.job.is_alive()


def test_swing_mirrors_pair(bench):
    bench.power(["LUL", "LUR"])
    bench.swing(15)
    finish(bench)
    assert moves(bench) == ["S LUL=75 LUR=105", "S LUL=90 LUR=90", "S LUL=105 LUR=75", "S LUL=90 LUR=90"]


def test_swing_clips_to_config(bench):
    bench.power(["TON"])
    bench.swing(30)
    finish(bench)
    assert moves(bench) == ["S TON=60", "S TON=90", "S TON=120", "S TON=90"]


def test_swing_end_of_range_goes_one_way(bench):
    bench.power(["JL", "JR"])
    bench.swing(30)
    finish(bench)
    assert moves(bench) == ["S JL=60 JR=120", "S JL=90 JR=90"]


def test_swing_needs_whole_group_at_90(bench):
    with pytest.raises(ts.Refused):
        bench.swing(15)
    bench.power(["TON"])
    bench.move({"TON": 5})
    with pytest.raises(ts.Refused):
        bench.swing(15)
    with pytest.raises(ts.Refused):
        bench.swing(20)


def test_relax_stops_swing(bench):
    bench.pace = 1
    bench.power(["TON"])
    bench.swing(30)
    bench.relax()
    finish(bench)
    assert len(moves(bench)) <= 1 and sent(bench, "mouth")[-1] == "X"


def test_power_twice_homes_slowly(bench):
    bench.power(["TON"])
    bench.move({"TON": 5})
    bench.power(["TON"])
    finish(bench)
    assert moves(bench)[-1] == "S TON=90"
    assert sent(bench, "mouth").count("O TON") == 1


def test_beat_detects_loss_and_releases_on_return(bench):
    bench.power(["TON"])
    bench.links["mouth"].write = lambda data: (_ for _ in ()).throw(OSError("gone"))
    back = FakeLink("mouth")
    bench.rediscover = lambda skip: {"mouth": back}
    bench.beat()
    assert bench.powered == set() and "已重连" in bench.error
    assert back.sent[0] == "X"


def test_swing_single_servo(bench):
    bench.power(["LO"])
    bench.swing(15)
    finish(bench)
    assert moves(bench, "brows") == ["S LO=105", "S LO=90", "S LO=75", "S LO=90"]


def test_jaw_cannot_swing_alone(bench):
    bench.power(["JL"])
    with pytest.raises(ts.Refused):
        bench.swing(15)


def test_hold_survives_other_groups(bench):
    bench.power(["LLL", "LLR"])
    bench.hold(["LLL", "LLR"])
    bench.power(["UD"])
    bench.job and finish(bench)           # centers.json 里 UD 有中心，通电后会走过去
    assert sent(bench, "mouth")[-1] == "O LLL LLR"
    assert bench.held == {"LLL", "LLR"} and bench.powered == {"UD"}
    bench.power(["TON"])                  # 同一块板也不放开
    assert sent(bench, "mouth")[-1] == "O TON LLL LLR"


def test_relax_clears_hold(bench):
    bench.power(["LLL", "LLR"])
    bench.hold(["LLL", "LLR"])
    bench.relax()
    assert bench.held == set() and sent(bench, "mouth")[-1] == "X"


def test_hold_refuses_off_90(bench):
    bench.power(["TON"])
    bench.move({"TON": 5})
    with pytest.raises(ts.Refused):
        bench.hold(["TON"])


def test_center_shifts_home_and_swing(bench, monkeypatch):
    bench.mode = "hardware"  # 仍是假串口；验证真机模式的中心保存路径。
    saved = {}
    monkeypatch.setattr(ts, "center", lambda n: saved.get(n, 90.0))
    bench.save_center = lambda n, d: saved.__setitem__(n, d)
    bench.power(["UD"])
    for _ in range(3):
        bench.move({"UD": 5})
    bench.set_center("UD")
    assert saved == {"UD": 105.0}
    bench.swing(15)
    finish(bench)
    assert moves(bench, "eyes")[-4:] == ["S UD=120", "S UD=105", "S UD=90", "S UD=105"]


def test_sim_never_changes_real_center_file(bench):
    bench.enable_group(["UD"])
    with pytest.raises(ts.Refused, match="仿真"):
        bench.set_center("UD")


def test_hold_cannot_energize_disabled_channel(bench):
    with pytest.raises(ts.Refused):
        bench.hold(["EXA"])
    assert not sent(bench, "mouth")


@pytest.mark.parametrize("action", [lambda b: b.power(["LLR"]),
                                    lambda b: b.power(["LLL", "LLR"]),
                                    lambda b: b.enable_group(["LLL", "LLR"]),
                                    lambda b: b.hold(["LLR"]),
                                    lambda b: b.move({"LLR": 1}),
                                    lambda b: b._ask("mouth", "S TON=90 LLR=90"),
                                    lambda b: b._ask("mouth", "O LLR"),
                                    lambda b: b._ask("mouth", "R"),
                                    lambda b: b._start([{"UD": 120}, {"LLR": 90}])])
def test_fault_quarantine_rejects_before_any_motor_write(bench, action):
    bench.blocked = {**ts.BLOCKED, "LLR": "测试注入的故障隔离"}
    with pytest.raises(ts.Refused, match="LLR|EXA"):
        action(bench)
    assert all(not sent(bench, board) for board in ts.BOARDS)


def test_saved_pose_cannot_bypass_quarantine_and_release_still_works(bench):
    bench.enable_group(["LLL", "LLR"])
    bench.save_expression("neutral", revision=0)
    bench.blocked = {**ts.BLOCKED, "LLR": "测试注入的故障隔离"}
    before = {board: list(link.sent) for board, link in bench.links.items()}
    for action in (lambda: bench.load_expression("neutral"), lambda: bench.emotion("neutral"),
                   lambda: bench.save_expression("neutral", revision=1)):
        with pytest.raises(ts.Refused, match="LLR"):
            action()
    assert before == {board: link.sent for board, link in bench.links.items()}
    bench.relax()
    assert all(sent(bench, board)[-1] == "X" for board in ts.BOARDS)
    bench.enable_group(["TON"])
    assert bench.powered == {"TON"}


def test_unloaded_probe_is_disabled_by_default(bench):
    with pytest.raises(ts.Refused, match="尚未启用"):
        bench.probe_llr()
    assert all(not sent(bench, b) for b in ts.BOARDS)


def test_unloaded_probe_only_drives_llr_and_releases(bench):
    bench.blocked = {**ts.BLOCKED, "LLR": "测试注入的故障隔离"}
    bench.llr_unloaded = True
    bench.probe_llr()
    finish(bench)
    assert sent(bench, "mouth") == ["X", "O LLR", "X"]
    assert sent(bench, "eyes") == sent(bench, "brows") == ["X"]
    assert not bench.powered and not bench.error
    assert "已卸力" in bench.llr_probe
    assert [r["phase"] for r in bench.logged if r["type"] == "probe"] == ["start", "end"]
    with pytest.raises(ts.Refused):
        bench.power(["LLR"])


def test_unloaded_observation_allows_bounded_longer_hold(bench):
    bench.llr_unloaded = True
    bench.probe_llr(duration=30)
    finish(bench)
    assert bench.logged[0]["duration"] == 30
    assert sent(bench, "mouth") == ["X", "O LLR", "X"]
    assert not bench.powered


@pytest.mark.parametrize("duration", [0, 31, float("nan"), float("inf"), True])
def test_unloaded_observation_rejects_invalid_duration(bench, duration):
    bench.llr_unloaded = True
    with pytest.raises(ts.PoseError):
        bench.probe_llr(duration=duration)
    assert all(not sent(bench, b) for b in ts.BOARDS)


@pytest.mark.parametrize("board,line", [("eyes", "O LLR"), ("mouth", "O LLR LLL"),
                                      ("mouth", "S LLR=95"), ("mouth", "O EXA"), ("mouth", "R")])
def test_probe_exception_cannot_drive_other_commands(bench, board, line):
    bench.llr_unloaded = True
    with pytest.raises(ts.Refused):
        bench._ask(board, line, unloaded_probe=True)
    assert all(not sent(bench, b) for b in ts.BOARDS)


def test_probe_rejected_when_other_motor_is_powered(bench):
    bench.llr_unloaded = True
    bench.enable_group(["TON"])
    before = list(sent(bench, "mouth"))
    with pytest.raises(ts.Refused, match="全部卸力"):
        bench.probe_llr()
    assert sent(bench, "mouth") == before


def test_probe_can_be_cancelled(bench):
    import time
    bench.llr_unloaded = True
    bench.pace = 10
    bench.probe_llr()
    deadline = time.monotonic() + 1
    while "O LLR" not in sent(bench, "mouth") and time.monotonic() < deadline:
        time.sleep(.005)
    assert "O LLR" in sent(bench, "mouth")
    bench.relax()
    finish(bench)
    assert sent(bench, "mouth")[-1] == "X" and not bench.powered
    assert bench.logged[-1]["cancelled"]


def test_probe_attempts_release_when_activation_fails(bench):
    bench.llr_unloaded = True
    link = bench.links["mouth"]
    original = link.write
    def fail_activation(data):
        original(data)
        if data.strip() == b"O LLR":
            link.reply = "ERR test"
    link.write = fail_activation
    bench.probe_llr()
    finish(bench)
    assert sent(bench, "mouth")[-1] == "X"
    assert bench.error and not bench.powered


@pytest.mark.parametrize("servo,lo,hi", [("EXA", 80, 100), ("TON", float("nan"), 100),
                                      ("TON", 100, 90), ("TON", 0, 180)])
def test_measured_ranges_reject_invalid_input(bench, servo, lo, hi):
    with pytest.raises((ts.Refused, ts.PoseError)):
        bench.set_range(servo, lo, hi)
    assert not bench.logged


def test_power_walks_to_center(bench, monkeypatch):
    monkeypatch.setattr(ts, "center", lambda n: 110.0 if n == "UD" else 90.0)
    bench.power(["UD"])
    finish(bench)
    assert "O UD" in sent(bench, "eyes") and moves(bench, "eyes") == ["S UD=110"]


def test_steps_are_one_group_on_one_board():
    for name in ts.EXPRESSIONS:
        for s in ts.expression_steps(name, 1.0):
            assert len({ts.BY_NAME[n].board for n in s["goal"]}) == 1


def test_steps_keep_gaze_and_skip_unlisted(monkeypatch):
    from head import actuators

    monkeypatch.setitem(actuators.CENTERS, "UD", 120.0)
    goals = {n: v for s in ts.expression_steps("neutral", 1.0) for n, v in s["goal"].items()}
    assert set(goals) == set(ts.EYES) and goals["UD"] == 120.0 and goals["LR"] == 90.0
    happy = {n for s in ts.expression_steps("happy", 1.0) for n in s["goal"]}
    assert "TON" not in happy and "LLL" not in happy


def test_expr_prepares_without_moving(bench, tmp_path):
    bench.log_path = tmp_path / "none.jsonl"
    bench.expr("happy", 0.3)
    assert all(not moves(bench, b) for b in bench.links)
    assert bench.script["i"] == 0


def test_expr_steps_one_group_at_a_time(bench, tmp_path):
    bench.log_path = tmp_path / "none.jsonl"
    bench.expr("happy", 0.3)
    first = bench.script["steps"][0]["goal"]
    bench.expr_next()
    finish(bench)
    assert bench.powered == set(first)
    assert sum(len(moves(bench, b)) for b in bench.links) == 1


def test_expr_all_records_recipe(bench, tmp_path):
    bench.log_path = tmp_path / "none.jsonl"
    bench.expr("surprised", 0.3)
    bench.expr_all()
    finish(bench)
    assert bench.logged[-1]["type"] == "recipe"
    assert len(bench.logged[-1]["steps"]) == len(bench.script["steps"])


def test_relax_cancels_expression(bench, tmp_path):
    bench.pace = 1
    bench.log_path = tmp_path / "none.jsonl"
    bench.expr("happy", 0.3)
    bench.expr_all()
    bench.relax()
    finish(bench)
    assert bench.script is None and not any(r["type"] == "recipe" for r in bench.logged)


def test_home_after_expression_goes_per_board(bench, tmp_path):
    bench.log_path = tmp_path / "none.jsonl"
    bench.expr("happy", 0.3)
    bench.expr_all()
    finish(bench)
    bench.home()
    finish(bench)
    assert "ERR" not in bench.error


def test_expr_marks_untested_angles(bench, tmp_path):
    p = tmp_path / "log.jsonl"
    p.write_text('{"type": "cmd", "cmd": "S LR=60"}\n{"type": "cmd", "cmd": "S LR=120"}\n')
    bench.log_path = p
    bench.expr("neutral", 0.3)
    steps = {s["label"]: s["new"] for s in bench.script["steps"]}
    assert steps["眼球左右"] == [] and steps["眼球上下"] == ["UD"]


def test_expr_go_hits_all_boards_in_one_step(bench):
    bench.expr_go("happy", 1.0)
    finish(bench)
    assert len(moves(bench, "mouth")) == len(moves(bench, "brows")) == 1
    assert bench.logged[-1]["type"] == "recipe"


def test_next_expression_returns_unused_servos_to_rest(bench):
    bench.expr_go("surprised", 1.0)
    finish(bench)
    bench.expr_go("sad", 1.0)
    finish(bench)
    assert bench.angles["JL"] == 90 and bench.angles["JR"] == 90


def test_tour_leaves_only_held(bench):
    bench.power(["LLL", "LLR"])
    bench.hold(["LLL", "LLR"])
    bench.tour(1.0, dwell=0)
    finish(bench)
    assert bench.powered == set() and bench.held == {"LLL", "LLR"}
    assert sent(bench, "mouth")[-1] == "O LLL LLR" and sent(bench, "eyes")[-1] == "X"
    assert not any("LLL" in m for m in moves(bench)[1:])


def test_expr_go_plays_eye_frames_after_pose(bench):
    bench.expr_go("fear", 1.0)
    finish(bench)
    eyes = moves(bench, "eyes")
    assert len(eyes) == 1 + len(ts.eye_frames("fear", 1.0))
    assert sorted(eyes[0].split()) == sorted(eyes[-1].split())   # 动画结束回到静止姿态
    assert any(x.startswith("V 800") for x in sent(bench, "eyes"))


def test_relax_stops_eye_frames(bench):
    bench.pace = 1
    bench.expr_go("sad", 1.0)
    bench.relax()
    finish(bench)
    assert len(moves(bench, "eyes")) <= 1


# ---- 视觉跟踪 ----

class FakeVision:
    def __init__(self, x=None):
        self.x, self.fail = x, False

    def __call__(self, path):
        if self.fail:
            raise OSError("down")
        if path == "/params":
            return {"params": {"gain": 1.0, "hfov": 65.0}}
        return {"face": self.x is not None, "x": self.x}


@pytest.fixture
def tracked(bench, tmp_path, monkeypatch):
    log = tmp_path / "log.jsonl"
    log.write_text('{"type": "range", "servo": "LR", "lo": 30, "hi": 150}\n')
    monkeypatch.setattr(ts, "TRACK_HZ", 500)
    bench.log_path = log
    bench.vision = FakeVision()
    bench.power(["LR"])
    return bench


def wait_for(cond, timeout=3):
    end = ts.time.time() + timeout
    while ts.time.time() < end:
        if cond():
            return True
        ts.time.sleep(0.005)
    return False


def lr_sent(bench):
    return [float(x.split("=")[1]) for x in sent(bench, "eyes") if x.startswith("S LR=")]


def test_track_needs_power_range_and_vision(bench, tmp_path):
    bench.log_path = tmp_path / "none.jsonl"
    bench.vision = FakeVision()
    with pytest.raises(ts.Refused, match="通电"):
        bench.track(True)
    bench.power(["LR"])
    with pytest.raises(ts.Refused, match="实测范围"):
        bench.track(True)
    bench.log_path.write_text('{"type": "range", "servo": "LR", "lo": 30, "hi": 150}\n')
    bench.vision.fail = True
    with pytest.raises(ts.Refused, match="视觉服务"):
        bench.track(True)
    assert bench.tracking is None


def test_track_follows_slowly_and_blocks_other_actions(tracked):
    tracked.vision.x = -1          # 画面最左：LR 目标 122.5°
    tracked.track(True)
    assert wait_for(lambda: tracked.angles["LR"] > 120)
    with pytest.raises(ts.Refused, match="没结束"):
        tracked.swing(15)
    tracked.track(False)
    values = [90.0] + lr_sent(tracked)
    assert all(abs(b - a) <= ts.TRACK_STEP + 0.1 for a, b in zip(values, values[1:]))
    assert max(values) <= 122.6
    assert sent(tracked, "eyes")[-1] != "X"
    assert tracked.tracking is None


def test_track_stays_inside_measured_range(tracked):
    tracked.log_path.write_text('{"type": "range", "servo": "LR", "lo": 80, "hi": 100}\n')
    tracked.vision.x = -1
    tracked.track(True)
    assert wait_for(lambda: tracked.angles["LR"] >= 99)
    ts.time.sleep(0.05)
    tracked.relax()
    assert max(lr_sent(tracked)) <= 100


def test_track_holds_when_face_lost_then_goes_home(tracked, monkeypatch):
    monkeypatch.setattr(ts, "TRACK_LOST", 0.05)
    tracked.vision.x = -1
    tracked.track(True)
    assert wait_for(lambda: tracked.angles["LR"] > 110)
    tracked.vision.x = None
    assert wait_for(lambda: abs(tracked.angles["LR"] - 90) < 2)
    tracked.relax()


def test_relax_stops_tracking_at_once(tracked):
    tracked.vision.x = -1
    tracked.track(True)
    assert wait_for(lambda: tracked.angles["LR"] > 95)
    tracked.relax()
    assert wait_for(lambda: tracked.tracking is None)
    n = len(lr_sent(tracked))
    ts.time.sleep(0.05)
    assert len(lr_sent(tracked)) == n and sent(tracked, "eyes")[-1] == "X"


def test_track_stops_when_vision_dies(tracked):
    tracked.vision.x = -1
    tracked.track(True)
    assert wait_for(lambda: tracked.angles["LR"] > 95)
    tracked.vision.fail = True
    assert wait_for(lambda: tracked.tracking is None)
    assert "视觉服务断开" in tracked.error
