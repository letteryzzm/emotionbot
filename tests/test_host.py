import importlib.util
import sys
import types
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from head import ACTUATORS, EXPRESSIONS, HeadClient, NAMES, blend, expression, rest_vector  # noqa: E402
from head.blendshape_map import blendshapes_to_u  # noqa: E402


def load_fw(role):
    """每块板一份独立的固件实例，当作假串口的另一端"""
    sys.path.insert(0, str(ROOT / "firmware"))
    cfg = importlib.import_module(f"config_{role}")
    sys.modules["config"] = cfg
    sys.modules["servo"] = types.SimpleNamespace(
        Servo=type("S", (), {"__init__": lambda s, p: None, "write": lambda s, d: None, "off": lambda s: None})
    )
    spec = importlib.util.spec_from_file_location(f"fw_{role}", ROOT / "firmware/main.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.setup()
    return m


class Loopback:
    def __init__(self, fw):
        self.fw, self.reply = fw, b""

    def write(self, data):
        self.reply = ((self.fw.handle(data.decode()) or "") + "\n").encode()

    def readline(self):
        return self.reply


def test_action_space():
    assert len(ACTUATORS) == 22 and len(set(NAMES)) == 22
    r = rest_vector()
    assert r.shape == (22,) and np.all((r >= 0) & (r <= 1))


def test_expressions_in_range():
    for name in EXPRESSIONS:
        v = expression(name)
        assert v.shape == (22,) and np.all((v >= 0) & (v <= 1)), name
    assert np.allclose(expression("happy", 0), rest_vector())
    assert np.all((blend({"happy": 0.7, "surprised": 0.7}) <= 1))


def test_client_roundtrip():
    fws = {r: load_fw(r) for r in ("eyes", "brows", "mouth")}
    head = HeadClient(links={r: Loopback(f) for r, f in fws.items()})
    head.set(expression("surprised"))
    for f in fws.values():
        for _ in range(300):
            f.tick(0.01)
    got = head.angles()
    assert set(got) == set(NAMES)
    assert got["JL"] < 90 and got["JR"] > 90  # 张嘴
    assert got["TL"] == 160  # 上眼皮全睁


def test_blendshape_map():
    v = blendshapes_to_u({"jawOpen": 1.0, "eyeBlinkLeft": 1.0, "eyeBlinkRight": 1.0})
    u = dict(zip(NAMES, v))
    assert u["JL"] == 1 and u["TL"] == 0 and u["TR"] == 0
    v = blendshapes_to_u({"mouthSmileLeft": 1.0}, mirror=True)
    u = dict(zip(NAMES, v))
    assert u["CUR"] > 0.9 and u["CUL"] == 0.5  # 镜像：人的左嘴角 -> 机器人右嘴角


def test_mirror_uses_physical_side():
    # 人闭左眼 -> 机器人闭它自己的右眼；眼皮名字的 L 正好在机器人右侧
    u = dict(zip(NAMES, blendshapes_to_u({"eyeBlinkLeft": 1.0}, mirror=True)))
    assert u["TL"] == 0 and u["TR"] == 1
    # 人看自己的右边 -> 机器人看它自己的左边 -> LR 角度增大
    u = dict(zip(NAMES, blendshapes_to_u({"eyeLookOutRight": 1.0, "eyeLookInLeft": 1.0}, mirror=True)))
    assert u["LR"] > 0.5


def test_lower_lip_up_is_u1():
    from head.actuators import BY_NAME
    assert BY_NAME["LLL"].angle(1) == 55 and BY_NAME["LLR"].angle(1) == 110


def test_servo_step_guard():
    import importlib.util
    spec = importlib.util.spec_from_file_location("servo_step", ROOT / "scripts/servo_step.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    sent = []

    class C:
        links = {"eyes": None}

        def _send(self, b, line):
            sent.append(line)
            return "OK"

    m.run(C(), ["TL=100", "TL=160", "!TL=160", "UD=95", "TL=1 JL=85", "q"], out=lambda *a: None)
    assert sent == ["V 30", "S TL=100", "S TL=160", "S UD=95"]
    sent.clear()
    C.links = {"mouth": None}
    m.run(C(), ["JL=85 JR=95", "JL=50 JR=130", "q"], out=lambda *a: None)
    assert sent == ["V 30", "S JL=85 JR=95"]


def test_servo_check_moves_jaw_together():
    import importlib.util
    spec = importlib.util.spec_from_file_location("servo_check", ROOT / "scripts/servo_check.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.SWING, m.SPEED = 1, 1e9
    m.time.sleep = lambda s: None
    sent = []

    class C:
        def _send(self, b, line):
            sent.append(line)
            return "ROLE mouth JL,JR,TON" if line == "?" else "OK"

    res = m.check(C(), ["mouth"], ask=lambda p: "y")
    assert "S JL=91 JR=89" in sent and not any(s.startswith("S JR") for s in sent)
    assert res == {"JL": "ok", "TON": "ok"}


def test_demo_expressions_flags(monkeypatch):
    import runpy

    import head
    calls = []

    class Fake:
        def speed(self, d):
            calls.append(("speed", d))

        def set(self, v):
            calls.append(("set", v))

        def rest(self):
            calls.append(("rest",))

        def close(self):
            pass

    monkeypatch.setattr(head, "HeadClient", Fake)
    monkeypatch.setattr(sys, "argv", ["demo", "--only", "happy", "--intensity", "0.3", "--speed", "60", "--hold", "0"])
    runpy.run_path(str(ROOT / "scripts/demo_expressions.py"), run_name="__main__")
    assert calls[0] == ("speed", 60) and calls[-1] == ("rest",) and len(calls) == 3
    assert np.allclose(calls[1][1], expression("happy", 0.3))


def test_pico_ports_skip_other_serial(monkeypatch):
    from head import client
    found = {"/dev/cu.usbmodem*": [], "/dev/serial/by-id/*MicroPython*": ["/dev/serial/by-id/usb-MicroPython_Board-if00"]}
    monkeypatch.setattr(client.glob, "glob", lambda p: found[p])
    assert client.pico_ports() == ["/dev/serial/by-id/usb-MicroPython_Board-if00"]
