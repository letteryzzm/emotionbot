"""用内存串口验证滑块控制、观察记录、超时与卸力；不连接真机。"""
import time

import pytest

from head.calibration_session import PositionBook
from head.pose_library import PoseError
from test_tune_server import FakeLink, bench, sent, ts  # noqa: F401


OBS = {"reached": "yes", "buzz": "no", "jitter": "no", "heat": "no", "text": "人工观察样例"}


def wait_for(check, seconds=2):
    end = time.monotonic() + seconds
    while time.monotonic() < end:
        if check():
            return
        time.sleep(0.01)
    assert check()


@pytest.fixture
def cal(bench):
    yield bench
    bench.relax()
    if bench.job:
        bench.job.join(2)
        assert not bench.job.is_alive()


def start(cal, names=("TON",), explore=True):
    cal.cal_begin(list(names))
    token = cal.cal["token"]
    if explore:
        cal.cal_range(token, OBS)
    return token


@pytest.mark.parametrize("names", [["LLR"], ["LLL", "LLR"]])
def test_default_llr_supports_manual_positions_and_expression_library(tmp_path, names):
    b = ts.Bench({board: FakeLink(board) for board in ts.BOARDS}, log=lambda entry: None,
                 settle=0, pace=0, library_path=tmp_path / "expressions.json", mode="sim")
    b.log_path = tmp_path / "events.jsonl"
    assert all(set(link.sent) == {"G"} for link in b.links.values())
    assert "LLR" not in b.state()["blocked"] and "EXA" in b.state()["blocked"]
    try:
        b.cal_begin(names, manual=True)
        token = b.cal["token"]
        goal = {n: 92 if n == "LLR" else 88 for n in names}
        b.cal_target(token, 1, goal)
        wait_for(lambda: all(b.angles[n] == value for n, value in goal.items()))
        with pytest.raises(PoseError):
            b.cal_target(token, 2, {**goal, "LLR": 111})
        b.cal_capture(token, "LLR 人工观察", {**OBS, "buzz": "yes"})
        assert b.positions.data["records"][-1]["angles"] == goal
        b.save_expression("neutral", revision=0)
    finally:
        b.relax()
        if b.job:
            b.job.join(2)
    b.load_expression("neutral")
    assert b.preview["angles"] == goal
    assert all(sent(b, board)[-1] == "X" for board in ts.BOARDS)


@pytest.mark.parametrize("names", [["TON"], ["LO", "RO"], ["TON", "LR", "LO"], ["JL", "JR"]])
def test_single_pair_and_cross_board_group(cal, names):
    start(cal, names)
    assert cal.powered == set(names)
    for board in ts.BOARDS:
        outputs = [s for s in sent(cal, board) if s.startswith("O ")]
        expected = {n for n in names if ts.BY_NAME[n].board == board}
        assert outputs == (["O " + " ".join(sorted(expected))] if expected else [])


@pytest.mark.parametrize("names", [["EXA"], ["LLR"], ["TON", "LLR"], ["JL"], ["JR"]])
def test_preflight_blocks_all_motion_on_invalid_selection(cal, names):
    cal.blocked = {**ts.BLOCKED, "LLR": "测试注入的故障隔离"}
    with pytest.raises((PoseError, ts.Refused)):
        cal.cal_begin(names)
    assert all(not sent(cal, b) for b in ts.BOARDS)


def test_offline_group_rejected_before_any_output(cal):
    del cal.links["eyes"]
    with pytest.raises(PoseError, match="未连接"):
        cal.cal_begin(["TON", "LR"])
    assert not sent(cal, "mouth")


def test_optional_90_test_can_switch_to_manual_without_observations(cal):
    token = start(cal, explore=False)
    with pytest.raises(PoseError, match="转为手动"):
        cal.cal_target(token, 1, {"TON": 91})
    cal.cal_range(token)
    assert cal.cal["phase"] == "range"
    assert not cal.positions.data["records"]  # 不自动制造“通过”记录。
    cal.cal_target(token, 1, {"TON": 91})


def test_negative_observations_are_saved_without_locking_manual_control(cal):
    token = start(cal, explore=False)
    observation = {"reached": "no", "jitter": "yes", "heat": "unknown", "buzz": "yes", "text": "偏下"}
    cal.cal_range(token, observation)
    assert cal.positions.data["records"][-1]["observations"] == observation
    cal.cal_target(token, 1, {"TON": 91})


def test_manual_starts_from_controller_angle_without_center_compensation(cal):
    cal.links["eyes"].ang["UD"] = 97
    cal.cal_begin(["UD"], manual=True)
    token = cal.cal["token"]
    assert cal.cal["phase"] == "range"
    assert cal.cal["goal"] == {"UD": 97}
    assert "S UD=97" in sent(cal, "eyes")
    assert not any(s.startswith("O ") for b in ts.BOARDS for s in sent(cal, b))
    assert not cal.positions.data["records"]
    cal.cal_target(token, 1, {"UD": 98})
    wait_for(lambda: cal.angles["UD"] == 98)


def test_manual_does_not_require_90_inside_verified_range(cal):
    cal.log_path.write_text('{"type":"range","servo":"UD","lo":95,"hi":110}\n')
    cal.links["eyes"].ang["UD"] = 100
    cal.cal_begin(["UD"], manual=True)
    assert cal.cal["goal"] == {"UD": 100}


@pytest.mark.parametrize("names", [["LLR"], ["EXA"], ["JL"]])
def test_manual_preserves_channel_and_jaw_constraints(cal, names):
    cal.blocked = {**ts.BLOCKED, "LLR": "测试注入的故障隔离"}
    with pytest.raises((PoseError, ts.Refused)):
        cal.cal_begin(names, manual=True)
    assert all(not sent(cal, b) for b in ts.BOARDS)


def test_latest_target_replaces_previous_without_queue(cal):
    token = start(cal)
    cal.cal_target(token, 1, {"TON": 120}, speed=5)
    wait_for(lambda: any(s.startswith("S ") for s in sent(cal, "mouth")))
    cal.cal_target(token, 2, {"TON": 89}, speed=5)
    wait_for(lambda: abs(cal.angles["TON"] - 89) < .01)
    values = [float(s.split("=")[1]) for s in sent(cal, "mouth") if s.startswith("S TON=")]
    assert max(values) < 95  # 不会先走完旧目标 120°。
    assert all(abs(b-a) <= .51 for a, b in zip([90]+values, values))
    with pytest.raises(PoseError, match="过期"):
        cal.cal_target(token, 1, {"TON": 120})


def test_jaw_interpolation_stays_coupled(cal):
    token = start(cal, ["JL", "JR"])
    cal.cal_target(token, 1, {"JL": 84, "JR": 96}, speed=30)
    wait_for(lambda: cal.angles["JL"] == 84)
    for line in sent(cal, "mouth"):
        if line.startswith("S "):
            goal = dict((n, float(v)) for n, v in (p.split("=") for p in line.split()[1:]))
            assert goal["JL"] + goal["JR"] == 180
    with pytest.raises(PoseError, match="下巴"):
        cal.cal_target(token, 2, {"JL": 70, "JR": 96})


@pytest.mark.parametrize("goal,speed", [({"TON": 200},5), ({"TON": float("nan")},5), ({"TON": 91},100), ({"LO": 90},5)])
def test_bad_targets_do_not_change_goal(cal, goal, speed):
    token = start(cal)
    with pytest.raises(PoseError):
        cal.cal_target(token, 1, goal, speed)
    assert cal.cal["goal"] == {"TON": 90}


def test_disconnect_lease_releases_every_board(cal):
    cal.CAL_LEASE = .15
    start(cal)
    wait_for(lambda: cal.cal is None)
    assert not cal.powered
    assert all(sent(cal, b)[-1] == "X" for b in ts.BOARDS)


def test_center_timer_is_not_extended_by_keepalive(cal):
    token = start(cal, explore=False)
    cal.cal["deadline"] = time.monotonic() + .15
    cal.cal_touch(token)
    wait_for(lambda: cal.cal is None)
    assert not cal.powered


def test_stop_cancels_pending_motion_and_old_token(cal):
    token = start(cal)
    cal.cal_target(token, 1, {"TON": 120})
    cal.cal_stop(token)
    cal.job.join(2)
    before = list(sent(cal, "mouth"))
    with pytest.raises(PoseError, match="结束"):
        cal.cal_target(token, 2, {"TON": 100})
    time.sleep(.15)
    assert sent(cal, "mouth") == before
    assert before[-1] == "X"
    new_token = start(cal)
    with pytest.raises(PoseError, match="结束"):
        cal.cal_stop(token)
    assert cal.cal["token"] == new_token and cal.powered == {"TON"}


def test_position_survives_restart_and_preserves_observations(cal):
    token = start(cal)
    cal.cal_capture(token, "舌头起点", {**OBS, "buzz": "yes"}, {"TON": "增角时向下"})
    book = PositionBook(cal.positions.path, "sim")
    record = book.data["records"][-1]
    assert record["angles"] == {"TON": 90}
    assert record["observations"]["buzz"] == "yes"
    assert record["directions"] == {"TON": "增角时向下"}
    assert record["source"] == "controller_command_state"
    with pytest.raises(PoseError, match="模式"):
        PositionBook(cal.positions.path, "hardware")


def test_capture_waits_for_command_target(cal):
    token = start(cal)
    cal.cal_target(token, 1, {"TON": 120})
    with pytest.raises(PoseError, match="未到达"):
        cal.cal_capture(token, "不可抢拍", OBS)


def test_restore_rechecks_mask_and_configuration(cal):
    token = start(cal)
    record = cal.positions.data["records"][0]
    cal.cal_restore(token, record["id"], 1)
    record["context"] = "old-config"
    with pytest.raises(PoseError, match="配置"):
        cal.cal_restore(token, record["id"], 2)


def test_board_error_attempts_release_on_all_boards(cal):
    token = start(cal)
    original = cal._ask
    def fail(board, line, **kw):
        if line.startswith("S "):
            return "ERR test"
        return original(board, line, **kw)
    cal._ask = fail
    cal.cal_target(token, 1, {"TON": 92})
    wait_for(lambda: cal.cal is None)
    assert "未接受位置" in cal.error
    assert all(sent(cal, b)[-1] == "X" for b in ts.BOARDS)


def test_stale_position_writer_cannot_overwrite(cal):
    token = start(cal)
    stale = PositionBook(cal.positions.path, "sim")
    cal.cal_capture(token, "新记录", OBS)
    with pytest.raises(PoseError, match="另一进程"):
        stale.append(stale.data["records"][0])
    assert len(PositionBook(cal.positions.path, "sim").data["records"]) == 2


def test_expired_begin_after_stop_cannot_reenergize(cal):
    epoch = cal.cal_epoch
    cal.relax()
    with pytest.raises(PoseError, match="过期"):
        cal.cal_begin(["TON"], epoch=epoch)
    assert not cal.powered
    assert all(sent(cal, b) == ["X"] for b in ts.BOARDS)


def test_after_release_can_record_last_known_state_without_output(cal):
    token = start(cal)
    cal.cal_stop(token)
    cal.job.join(2)
    before = {b: list(sent(cal, b)) for b in ts.BOARDS}
    cal.cal_capture(token, "卸力后补记嗡声", {**OBS, "buzz": "yes"})
    record = cal.positions.data["records"][-1]
    assert record["source"] == "last_controller_state"
    assert record["ended_at"]
    assert {b: sent(cal, b) for b in ts.BOARDS} == before
