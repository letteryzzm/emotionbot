"""表情模仿：camera.web 给出的 52 个表情系数（MediaPipe，ARKit 命名）-> 舵机。

    .venv/bin/python -m camera.mimic            # 读 camera.web 的 /state，写 vision 层

像照镜子：你闭左眼，它闭你看到的左边那只眼；你往左看，它也往你的左边看。
系数里的 Left 指本人的左侧（拿真人照片涂掉一只眼验证过），方向反了用 --swap。
每个人放松时的系数不一样（尤其眯眼、皱眉），所以减去基线：基线取校准文件，没有就从 0 开始，
平时慢慢跟着最低值走，做表情时间短的话不会被吃掉。
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from culture.actions import semantic_to_u  # noqa: E402
from head.actuators import rest_vector, NAMES  # noqa: E402
from head.hub import NEVER_DRIVE  # noqa: E402
from head.hub_client import HubClient  # noqa: E402

NEUTRAL_FILE = ROOT / "outputs" / "mimic_neutral.json"
WEB_URL = "http://127.0.0.1:8000"
TTL = 0.5
RISE_PER_S = 0.01       # 基线往上爬的速度，100 秒爬 1.0
BASE_CAP = 0.5          # 基线最多到这里，免得一直皱眉的人被当成平静
SMOOTH = 0.5            # 每帧向新值走一半
REST = dict(zip(NAMES, (float(x) for x in rest_vector())))

LABELS = (   # 给页面看的，先满足的先算
    ("惊讶", lambda b: b["jawOpen"] > 0.35 and b["browInnerUp"] > 0.3),
    ("开心", lambda b: b["mouthSmile"] > 0.35),
    ("生气", lambda b: b["browDown"] > 0.35),
    ("厌恶", lambda b: b["mouthUpperUp"] > 0.35 or b["noseSneer"] > 0.35),
    ("难过", lambda b: b["mouthFrown"] > 0.3 or (b["browInnerUp"] > 0.4 and b["jawOpen"] < 0.2)),
    ("闭眼", lambda b: b["eyeBlinkLeft"] > 0.55 and b["eyeBlinkRight"] > 0.55),
    ("眨一只眼", lambda b: abs(b["eyeBlinkLeft"] - b["eyeBlinkRight"]) > 0.45),
    ("张嘴", lambda b: b["jawOpen"] > 0.35),
)


def clip(x, lo=0.0, hi=1.0):
    return min(hi, max(lo, x))


def load_neutral(path=NEUTRAL_FILE):
    try:
        return {k: float(v) for k, v in json.loads(path.read_text()).items()}
    except (OSError, ValueError, AttributeError):
        return {}


def normalize(raw, base):
    """减基线并拉回 0~1。"""
    return {k: clip((v - base.get(k, 0.0)) / max(1e-3, 1 - base.get(k, 0.0))) for k, v in raw.items()}


def both(b, name):
    return (b.get(name + "Left", 0.0) + b.get(name + "Right", 0.0)) / 2


def label(b):
    """b 是减过基线的系数。"""
    d = dict(b)
    for k in ("mouthSmile", "mouthFrown", "browDown", "noseSneer", "mouthUpperUp"):
        d[k] = both(b, k)
    d.setdefault("jawOpen", 0.0)
    d.setdefault("browInnerUp", 0.0)
    d.setdefault("eyeBlinkLeft", 0.0)
    d.setdefault("eyeBlinkRight", 0.0)
    for name, test in LABELS:
        if test(d):
            return name
    return "平静"


def to_semantic(b, swap=False, gain=1.0):
    """系数 -> 灵眸语义量（_l/_r = 观众看到的左右）。照镜子：本人左侧 = 观众左侧。"""
    g = lambda k: b.get(k, 0.0)  # noqa: E731
    own = {"l": "Right" if swap else "Left", "r": "Left" if swap else "Right"}
    k = {}
    for side, s in own.items():
        blink, squint = g("eyeBlink" + s), g("eyeSquint" + s)
        k[f"lid_{side}"] = clip(1 - 1.4 * gain * blink)
        k[f"low_{side}"] = clip(1 - 1.2 * gain * blink - 0.6 * gain * squint)
        down = g("browDown" + s)
        k[f"bi_{side}"] = clip(0.5 + gain * (0.6 * g("browInnerUp") - 0.7 * down))
        k[f"bo_{side}"] = clip(0.5 + gain * (0.6 * g("browOuterUp" + s) + 0.4 * down))
        k[f"smile_{side}"] = clip(gain * (1.6 * g("mouthSmile" + s) - 1.6 * g("mouthFrown" + s)), -1, 1)
        k[f"wide_{side}"] = clip(gain * max(1.2 * g("mouthStretch" + s), 0.8 * g("mouthSmile" + s)))
        k[f"lu_{side}"] = clip(REST["LUL"] + gain * 0.8 * g("mouthUpperUp" + s))
    k["jaw"] = clip(gain * 1.3 * max(0.0, g("jawOpen") - 0.05))
    # 本人往自己左边看：左眼往外、右眼往里。照镜子时灵眸看向观众左侧，gx 负
    look_own_left = (g("eyeLookOut" + own["l"]) + g("eyeLookIn" + own["r"])) / 2
    look_own_right = (g("eyeLookIn" + own["l"]) + g("eyeLookOut" + own["r"])) / 2
    k["gx"] = clip(-2 * gain * (look_own_left - look_own_right), -1, 1)
    k["gy"] = clip(2 * gain * (both(b, "eyeLookUp") - both(b, "eyeLookDown")), -1, 1)
    return k


class Mimic:
    def __init__(self, swap=False, gain=1.0, neutral=None):
        self.swap, self.gain = swap, gain
        self.base = dict(neutral or {})
        self.u = None
        self.last_t = None

    def step(self, raw, t):
        """raw: 一帧原始系数。返回 {舵机: u}。"""
        dt = 0.0 if self.last_t is None else max(0.0, t - self.last_t)
        self.last_t = t
        for k, v in raw.items():
            b = self.base.get(k, 0.0)
            self.base[k] = min(v, b + RISE_PER_S * dt, BASE_CAP)
        want = semantic_to_u(to_semantic(normalize(raw, self.base), self.swap, self.gain))
        if self.u is None:
            self.u = want
        else:
            self.u = {n: self.u[n] + SMOOTH * (x - self.u[n]) for n, x in want.items()}
        return {n: x for n, x in self.u.items() if n not in NEVER_DRIVE}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--web", default=WEB_URL)
    ap.add_argument("--fps", type=float, default=15)
    ap.add_argument("--hub-port", type=int, default=8780)
    ap.add_argument("--swap", action="store_true", help="左右互换")
    ap.add_argument("--gain", type=float, default=1.0, help="幅度")
    a = ap.parse_args()
    hub = HubClient(port=a.hub_port)
    mimic = Mimic(a.swap, a.gain, load_neutral())
    stamp = NEUTRAL_FILE.stat().st_mtime if NEUTRAL_FILE.exists() else None
    t0 = time.time()
    was = None
    try:
        while True:
            start = time.time()
            if NEUTRAL_FILE.exists() and NEUTRAL_FILE.stat().st_mtime != stamp:   # 控制台点了校准
                stamp = NEUTRAL_FILE.stat().st_mtime
                mimic.base = load_neutral()
            try:
                with urllib.request.urlopen(a.web + "/state", timeout=1) as r:
                    s = json.load(r)
            except (OSError, ValueError) as e:
                if was is not False:
                    print(f"读不到视觉结果：{e}", flush=True)
                was = False
                time.sleep(0.5)
                continue
            if s.get("face") and s.get("blend"):
                sent = hub.intent("vision", mimic.step(s["blend"], start - t0), ttl=TTL)
                if sent != was:
                    print("已连接控制进程" if sent else f"连不上控制进程：{hub.error}", flush=True)
                    was = sent
            # 没人时不发，意图过期后脸回待机
            time.sleep(max(0.0, 1 / a.fps - (time.time() - start)))
    except KeyboardInterrupt:
        pass
    finally:
        hub.clear("vision")
        hub.close()


if __name__ == "__main__":
    main()
