"""灵眸戏台：给一张京剧或动漫图片，机器人头做出对应的动作。

    .venv/bin/python -m culture.server          # http://127.0.0.1:8790

动作由这个进程按 30 Hz 算出来，网页和真机看到的是同一份数据。同步到真机时只向 head.hub_server
提交 dialog 层意图，不碰串口，保护规则全部沿用控制进程。真机在 ROG 上时：
    ssh -L 8780:127.0.0.1:8780 rog
识图的密钥只留在这台机器上。
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from head.actuators import EYE_BROW_L_IS_ROBOT_LEFT, LR_UP_IS_ROBOT_LEFT, MOUTH_L_IS_ROBOT_LEFT
from head.hub_client import HubClient

from .actions import ACTIONS, REST, EXCLUDE, sample
from .analyze import MAX_UPLOAD, MODEL, AnalyzeError, analyze

HERE = Path(__file__).parent
SAMPLES = HERE / "samples"
FPS = 30
HUB_TTL = 0.6
MIN_INTENSITY, MAX_INTENSITY = 0.2, 1.0


class Stage:
    """播放器：只有一个动作在演，新动作直接接替。"""

    def __init__(self, hub=None, clock=time.monotonic):
        self.hub, self.clock = hub, clock
        self.lock = threading.Lock()
        self.action = None
        self.started = 0.0
        self.intensity = 1.0
        self.robot = False
        self.hub_ok = None
        self.u = {n: v for n, v in REST.items() if n not in EXCLUDE}
        self.beat = ""
        self.halt = threading.Event()
        self.send_event = threading.Event()
        self.pending = None

    def play(self, action_id, intensity=1.0):
        if action_id not in ACTIONS:
            raise ValueError("没有这个动作")
        with self.lock:
            self.action = ACTIONS[action_id]
            self.intensity = min(MAX_INTENSITY, max(MIN_INTENSITY, float(intensity)))
            self.started = self.clock()

    def stop(self):
        with self.lock:
            self.action = None

    def set_robot(self, on):
        self.robot = bool(on)
        if not on:
            self._clear()

    def _clear(self):
        self.pending = "clear"
        self.send_event.set()

    def step(self):
        with self.lock:
            action, intensity, t = self.action, self.intensity, self.clock() - self.started
            done = action is not None and t >= action.duration
            if done:
                self.action = None
        if action is None or done:
            if done:
                self.beat = ""
                self.u = {n: v for n, v in REST.items() if n not in EXCLUDE}
                if self.robot:
                    self._clear()
            return
        self.u, self.beat = sample(action, t, intensity)
        if self.robot:
            self.pending = dict(self.u)
            self.send_event.set()

    def run(self):
        while not self.halt.is_set():
            start = time.monotonic()
            self.step()
            self.halt.wait(max(0.0, 1 / FPS - (time.monotonic() - start)))

    def sender(self):
        """单独线程发给控制进程，只发最新一帧。控制进程没开时不拖慢播放。"""
        while not self.halt.is_set():
            if not self.send_event.wait(0.5):
                continue
            self.send_event.clear()
            job, self.pending = self.pending, None
            if self.hub is None or job is None:
                continue
            self.hub_ok = self.hub.clear("dialog") if job == "clear" else self.hub.intent("dialog", job, ttl=HUB_TTL)

    def state(self):
        with self.lock:
            action = self.action
            elapsed = self.clock() - self.started if action else 0.0
        return {
            "u": {n: round(x, 4) for n, x in self.u.items()},
            "beat": self.beat,
            "playing": action.id if action else None,
            "progress": min(1.0, elapsed / action.duration) if action else 0.0,
            "robot": self.robot,
            "hub_ok": self.hub_ok,
        }


def action_list():
    return [{"id": a.id, "group": a.group, "name": a.name, "use": a.use, "note": a.note, "skin": a.skin,
             "duration": a.duration} for a in ACTIONS.values()]


def samples():
    try:
        return json.loads((SAMPLES / "index.json").read_text())
    except FileNotFoundError:
        return []


def make_handler(stage):
    class Handler(BaseHTTPRequestHandler):
        protocol_version = "HTTP/1.1"

        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype="application/json"):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code=200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode())

        def do_GET(self):
            if self.path == "/":
                self._send(200, (HERE / "page.html").read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/face.js":
                self._send(200, (HERE / "face.js").read_bytes(), "text/javascript; charset=utf-8")
            elif self.path == "/state":
                self._json(stage.state())
            elif self.path == "/meta":
                self._json({
                    "actions": action_list(), "samples": samples(), "rest": REST, "model": MODEL,
                    "flags": {"eye_l_robot_left": EYE_BROW_L_IS_ROBOT_LEFT, "mouth_l_robot_left": MOUTH_L_IS_ROBOT_LEFT,
                              "lr_up_robot_left": LR_UP_IS_ROBOT_LEFT},
                })
            elif self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                try:
                    while not stage.halt.is_set():
                        self.wfile.write(b"data: " + json.dumps(stage.state(), ensure_ascii=False).encode() + b"\n\n")
                        self.wfile.flush()
                        time.sleep(1 / FPS)
                except OSError:
                    pass
            elif self.path.startswith("/samples/"):
                name = self.path.rsplit("/", 1)[1]
                known = {s["file"] for s in samples()}
                if name not in known:
                    return self._send(404, b"{}")
                self._send(200, (SAMPLES / name).read_bytes(), "image/jpeg")
            else:
                self._send(404, b"{}")

        def do_POST(self):
            # 自定义头让别的网页没法跨站发命令
            length = int(self.headers.get("Content-Length") or 0)
            if self.headers.get("X-Head") != "1" or not 0 < length <= MAX_UPLOAD:
                self.close_connection = True
                return self._send(403 if self.headers.get("X-Head") != "1" else 413, b"{}")
            data = self.rfile.read(length)
            if self.path == "/analyze":
                try:
                    return self._json(analyze(data))
                except AnalyzeError as e:
                    return self._json({"error": str(e)}, 400)
            if self.path != "/api":
                return self._send(404, b"{}")
            try:
                req = json.loads(data)
                op = req.get("op")
                if op == "play":
                    stage.play(req["action"], req.get("intensity", 1.0))
                elif op == "stop":
                    stage.stop()
                elif op == "robot":
                    stage.set_robot(req.get("on"))
                else:
                    raise ValueError("没有这个操作")
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                return self._json({"error": str(e)}, 400)
            self._json({"ok": True})

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8790)
    ap.add_argument("--hub-port", type=int, default=8780)
    a = ap.parse_args()
    stage = Stage(HubClient(port=a.hub_port))
    server = Server(("127.0.0.1", a.port), make_handler(stage))
    threading.Thread(target=stage.run, daemon=True).start()
    threading.Thread(target=stage.sender, daemon=True).start()
    print(f"http://127.0.0.1:{a.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        stage.halt.set()
        if stage.hub:
            stage.hub.clear("dialog")


if __name__ == "__main__":
    main()
