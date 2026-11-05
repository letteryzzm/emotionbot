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
