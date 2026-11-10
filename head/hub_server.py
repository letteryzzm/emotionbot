"""统一控制进程入口：表情控制、2D 渲染和真机开关都在这个网页里。

    .venv/bin/python -m head.hub_server                 # 默认只仿真，http://127.0.0.1:8780
    .venv/bin/python -m head.hub_server --port 8781

只听本机回环地址。在 Mac 上看 ROG：ssh -L 8780:127.0.0.1:8780 rog
启动时不碰串口，网页点“连接真机”才打开。其他程序用 head.hub_client.HubClient 提交意图。
"""
import argparse
import json
import signal
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from .actuators import (ACTUATORS, EYE_BROW_L_IS_ROBOT_LEFT, LR_UP_IS_ROBOT_LEFT, MOUTH_L_IS_ROBOT_LEFT, NAMES,
                        rest_vector)
from .expressions import EXPRESSIONS
from .hub import EXTERNAL_SOURCES, NEVER_DRIVE, Hub, Refused

try:  # 视觉模块额外的姿态；共用目录里可能没有 camera/
    from camera.behavior import EXTRA
except ImportError:
    EXTRA = {}

POSES = {**EXPRESSIONS, **EXTRA}
PAGE = Path(__file__).with_name("hub.html")
MAX_BODY = 65536


def pose_values(name, intensity):
    """只返回这个表情写到的舵机，视线和别的舵机留给其他层。"""
    if name not in POSES:
        raise Refused(f"没有这个表情：{name}")
    k = min(1.0, max(0.0, float(intensity)))
    rest = dict(zip(NAMES, rest_vector()))
    return {n: rest[n] + k * (x - rest[n]) for n, x in POSES[name].items()}


def meta(hub):
    return {
        "names": [n for n in NAMES if n not in NEVER_DRIVE],
        "rest": dict(zip(NAMES, (float(x) for x in rest_vector()))),
        "poses": list(POSES),
        "sources": EXTERNAL_SOURCES,
        "drivable": hub.drivable(),
        "total": len(ACTUATORS) - len(NEVER_DRIVE),
        "allow_unverified": hub.allow_unverified,
        "flags": {"eye_l_robot_left": EYE_BROW_L_IS_ROBOT_LEFT, "mouth_l_robot_left": MOUTH_L_IS_ROBOT_LEFT,
                  "lr_up_robot_left": LR_UP_IS_ROBOT_LEFT},
    }


def dispatch(hub, req):
    op = req.get("op")
    if op == "intent":
        values = req.get("values")
        if req.get("pose") is not None:
            values = pose_values(req["pose"], req.get("intensity", 1.0))
        if not isinstance(values, dict):
            raise Refused("缺少 values 或 pose")
        hub.intent(req.get("source", "manual"), values, req.get("ttl", 1.0), bool(req.get("merge")))
    elif op == "clear":
        hub.clear(req.get("source", "manual"))
    elif op == "life":
        hub.set_life(req.get("on", True))
    elif op == "arm":
        hub.arm()
    elif op == "estop":
        hub.release()
    else:
        raise Refused(f"没有这个操作：{op}")


def make_handler(hub):
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
                self._send(200, PAGE.read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/meta":
                self._json(meta(hub))
            elif self.path == "/state":
                self._json(hub.state())
            elif self.path == "/events":
                self.send_response(200)
                self.send_header("Content-Type", "text/event-stream")
                self.send_header("Cache-Control", "no-cache")
                self.send_header("Connection", "close")
                self.end_headers()
                self.close_connection = True
                try:
                    while not hub.halt.is_set():
                        self.wfile.write(b"data: " + json.dumps(hub.state()).encode() + b"\n\n")
                        self.wfile.flush()
                        time.sleep(0.04)
                except OSError:
                    pass
            else:
                self._send(404, b"{}")

        def do_POST(self):
            # 自定义头让别的网页没法跨站发命令
            length = int(self.headers.get("Content-Length") or 0)
            if self.path != "/api" or self.headers.get("X-Head") != "1" or not 0 < length <= MAX_BODY:
                self.close_connection = True
                return self._send(403, b"{}")
            try:
                dispatch(hub, json.loads(self.rfile.read(length)))
            except Refused as e:
                return self._json({"error": str(e)}, 400)
            except (TypeError, ValueError, AttributeError) as e:
                return self._json({"error": f"请求格式不对：{e}"}, 400)
            self._json({"ok": True})

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = False   # 端口被占说明已有一个控制进程，直接失败


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8780)
    ap.add_argument("--speed", type=float, default=300, help="舵机最大速度 deg/s")
    ap.add_argument("--allow-unverified", action="store_true", help="驱动没有实测范围的舵机，只用 config 范围")
    a = ap.parse_args()
    hub = Hub(allow_unverified=a.allow_unverified, speed=a.speed)
    server = Server(("127.0.0.1", a.port), make_handler(hub))
    threading.Thread(target=hub.run, daemon=True, name="control").start()

    def quit_(*_):
        threading.Thread(target=server.shutdown, daemon=True).start()

    signal.signal(signal.SIGTERM, quit_)
    signal.signal(signal.SIGINT, quit_)
    print(f"http://127.0.0.1:{a.port}  可驱动 {len(hub.drivable())} 个舵机", flush=True)
    try:
        server.serve_forever()
    finally:
        hub.stop()


if __name__ == "__main__":
    main()
