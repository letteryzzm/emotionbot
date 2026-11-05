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
