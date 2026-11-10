"""在 CPython 里跑固件逻辑：用假的 machine / servo 模块替掉硬件。"""
import importlib
import sys
import types
from pathlib import Path

import pytest

FW = Path(__file__).resolve().parent.parent / "firmware"


class FakeServo:
    def __init__(self, pin_id):
        self.pin, self.deg, self.on = pin_id, None, True

    def write(self, deg):
        self.deg, self.on = deg, True

    def off(self):
        self.on = False


@pytest.fixture(params=["eyes", "brows", "mouth"])
def fw(request, monkeypatch):
    monkeypatch.syspath_prepend(str(FW))
    cfg = importlib.import_module(f"config_{request.param}")
    monkeypatch.setitem(sys.modules, "config", cfg)
    monkeypatch.setitem(sys.modules, "servo", types.SimpleNamespace(Servo=FakeServo))
    sys.modules.pop("main", None)
    m = importlib.import_module("main")
    m.setup()
    return m


def test_role(fw):
    reply = fw.handle("?")
    assert reply.startswith("ROLE " + fw.config.ROLE)
    assert reply.split()[2].split(",") == list(fw.config.SERVOS)


def test_set_clamps_and_rate_limits(fw):
    name = next(iter(fw.servos))
    lo, hi = fw.limits[name]
    assert fw.handle(f"S {name}=999") == "OK"
    assert fw.tgt[name] == hi
    start = fw.cur[name]
    fw.tick(0.01)  # 600 deg/s * 10ms = 6°
    assert abs(fw.cur[name] - start) <= 6.0001
    for _ in range(200):
        fw.tick(0.01)
    assert fw.cur[name] == hi and fw.servos[name].deg == hi


def test_rest_center_relax(fw):
    fw.handle("C")
    assert all(s.deg == 90 for s in fw.servos.values())
    fw.handle("X")
    assert not any(s.on for s in fw.servos.values())
    fw.handle("R")
    for _ in range(300):
        fw.tick(0.01)
    assert all(fw.cur[n] == fw.rest[n] for n in fw.servos)


def test_errors(fw):
    assert fw.handle("S NOPE=10").startswith("ERR")
    assert fw.handle("Z").startswith("ERR")
    assert fw.handle("") is None


def run_ms(fw, ms):
    for _ in range(ms // 10):
        fw.watchdog(10)
        fw.tick(0.01)


def test_watchdog_off_by_default_keeps_holding(fw):
    name = next(iter(fw.servos))
    fw.safe_handle(f"O {name}")
    run_ms(fw, 20000)
    assert fw.servos[name].on and fw.handle("W") == "W 0"


def test_watchdog_returns_to_rest_then_releases_and_disarms(fw):
    name = next(iter(fw.servos))
    fw.safe_handle(f"S {name}=100")
    other = [n for n in fw.servos if n != name][0]
    assert fw.safe_handle("W 500") == "OK"
    run_ms(fw, 400)
    assert fw.servos[name].on and fw.tgt[name] == fw.clamp(name, 100)
    run_ms(fw, 200)
    assert fw.tgt[name] == fw.clamp(name, float(fw.rest[name]))
    assert fw.servos[name].on and other not in fw.active   # 没通电的舵机不会被带上电
    run_ms(fw, 2100)
    assert not any(s.on for s in fw.servos.values())
    assert fw.handle("W") == "W 0"


def test_any_line_feeds_watchdog_and_cancels_pending_release(fw):
    name = next(iter(fw.servos))
    fw.safe_handle(f"S {name}=100")
    fw.safe_handle("W 500")
    for _ in range(5):
        run_ms(fw, 400)
        fw.safe_handle("G")
    assert fw.tgt[name] == fw.clamp(name, 100)
    run_ms(fw, 600)                       # 触发，回 rest
    fw.safe_handle("W 500")               # 主机恢复
    run_ms(fw, 300)
    fw.safe_handle("G")
    run_ms(fw, 300)
    assert fw.servos[name].on


@pytest.mark.parametrize("bad", ["S {n}=nan", "S {n}=inf", "S {n}=abc", "S {n}", "V", "V nan", "V -1",
                                 "W abc", "W 5", "W 99999", "O"])
def test_bad_input_never_moves_or_crashes(fw, bad):
    name = next(iter(fw.servos))
    before = fw.tgt[name]
    reply = fw.safe_handle(bad.format(n=name))
    assert fw.tgt[name] == before
    assert reply == "OK" if bad == "O" else reply.startswith("ERR")


def test_bad_value_does_not_apply_half_a_line(fw):
    a, b = list(fw.servos)[:2]
    before = fw.tgt[a]
    assert fw.safe_handle(f"S {a}=100 {b}=nan").startswith("ERR")
    assert fw.tgt[a] == before and a not in fw.active


def test_speed_is_capped(fw):
    fw.safe_handle("V 99999")
    assert fw.speed == fw.MAX_SPEED
