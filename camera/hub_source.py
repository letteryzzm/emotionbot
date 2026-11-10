"""摄像头 -> 统一控制进程：只提交“距离情绪”这一层，不开串口。

    .venv/bin/python -m camera.hub_source                         # 读 camera.web 的结果
    .venv/bin/python -m camera.hub_source --camera 2 --rotate180  # 自己开摄像头

摄像头只能被一个进程占用，camera.web 开着时用第一种，它只读 /state，不需要 opencv。
先启动 head.hub_server。这个程序退出或卡住时，意图 0.5 秒后过期，脸回到待机。
眨眼由控制进程统一做，这里关掉 Behavior 自己的眨眼，避免两边各眨一次。
"""
import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from camera.behavior import CLOSE, FAR, GAZE_GAIN, NEAR, Behavior, FaceObs  # noqa: E402
from head.actuators import NAMES  # noqa: E402
from head.hub import NEVER_DRIVE  # noqa: E402
from head.hub_client import HubClient  # noqa: E402

TTL = 0.5
WEB_URL = "http://127.0.0.1:8000"


def obs_from_state(s, t):
    """camera.web 的 /state -> FaceObs。它的 u 用的是它启动时的标定，这里只取观测，自己算。"""
    if not s.get("face") or s.get("x") is None or s.get("dist") is None:
        return None
    return FaceObs(s["x"], s["y"], s["dist"], t, s.get("ipd") or 0.0)


def web_reader(url):
    def read(t):
        with urllib.request.urlopen(url + "/state", timeout=1) as r:
            return obs_from_state(json.load(r), t)
    return read


def camera_reader(index, hfov, rotate):
    import cv2

    from camera.vision import FaceTracker

    tracker = FaceTracker(hfov)
    cap = cv2.VideoCapture(index)

    def read(t):
        ok, frame = cap.read()
        if not ok:
            raise OSError("摄像头读不到画面")
        if rotate:
            frame = cv2.rotate(frame, cv2.ROTATE_180)
        return tracker.process(frame, t)[0]
    return read


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=None, help="给了就自己开摄像头，不读 camera.web")
    ap.add_argument("--web", default=WEB_URL)
    ap.add_argument("--hfov", type=float, default=65.0)
    ap.add_argument("--fps", type=float, default=15)
    ap.add_argument("--rotate180", action="store_true")
    ap.add_argument("--hub-port", type=int, default=8780)
    ap.add_argument("--far", type=float, default=FAR)
    ap.add_argument("--near", type=float, default=NEAR)
    ap.add_argument("--close", type=float, default=CLOSE)
    ap.add_argument("--gain", type=float, default=GAZE_GAIN)
    ap.add_argument("--flip-x", action="store_true", help="眼球左右跟反了时打开")
    a = ap.parse_args()

    read = web_reader(a.web) if a.camera is None else camera_reader(a.camera, a.hfov, a.rotate180)
    beh = Behavior()
    beh.hfov = a.hfov
    beh.far, beh.near, beh.close, beh.gain = a.far, a.near, a.close, a.gain
    beh._next_blink = float("inf")
    hub = HubClient(port=a.hub_port)
    t0 = time.time()
    was_ok = None
    try:
        while True:
            start = time.time()
            t = start - t0
            try:
                obs = read(t)
                if obs and a.flip_x:
                    obs.x = -obs.x
            except OSError as e:
                # 读不到就不发，意图过期后脸回待机
                if was_ok is not False:
                    print(f"读不到视觉结果：{e}", flush=True)
                was_ok = False
                time.sleep(0.5)
                continue
            u = beh.step(obs, t)
            values = {n: float(x) for n, x in zip(NAMES, u) if n not in NEVER_DRIVE}
            sent = hub.intent("vision", values, ttl=TTL)
            if sent != was_ok:
                print("已连接控制进程" if sent else f"连不上控制进程：{hub.error}", flush=True)
                was_ok = sent
            time.sleep(max(0.0, 1 / a.fps - (time.time() - start)))
    except KeyboardInterrupt:
        pass
    finally:
        hub.clear("vision")
        hub.close()


if __name__ == "__main__":
    main()
