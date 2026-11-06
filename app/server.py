"""仪表盘 HTTP 服务。

只用标准库：现场不会有 `pip install` 失败的风险，开发机现在就能跑。
接口：
  GET  /                静态页面 app/dashboard.html
  GET  /api/state       当前状态 + 历史事件（前端 200ms 轮询）
  GET  /api/video.mjpg  摄像头 MJPEG 预览
  GET  /api/health      模型/设备/串口状态
  POST /api/rest        回到 rest 姿态（现场救急用）
  POST /api/expression  手动指定表情，彩排用
  POST /api/say         手动让机器人说一句话
"""
from __future__ import annotations

import json
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

HERE = Path(__file__).resolve().parent
DASHBOARD = HERE / "dashboard.html"


class StateStore:
    """线程安全的状态仓。仪表盘和 agent 线程都只通过它交换数据。"""

    def __init__(self, history: int = 300):
        self._lock = threading.Lock()
        self._history: deque[dict] = deque(maxlen=history)
        self._now: dict = {
            "started": time.time(),
            "asr_text": "",
            "fusion": None,
            "per_modality": {},
            "expression": None,
            "latency_ms": 0.0,
            "head": [],
            "speaking": False,
            "status": {},
        }

    def update(self, **fields):
        with self._lock:
            self._now.update(fields)

    def add_event(self, record: dict):
        with self._lock:
            self._history.append(record)
            self._now.update({k: record[k] for k in
                              ("asr_text", "fusion", "per_modality", "expression",
                               "latency_ms") if k in record})

    def snapshot(self) -> dict:
        with self._lock:
            return {"now": dict(self._now), "history": list(self._history)}


class DashboardServer:
    def __init__(self, store: StateStore, *, host: str = "127.0.0.1", port: int = 8000,
                 jpeg_provider=None, on_rest=None, on_expression=None, on_say=None):
        self.store = store
        self.host, self.port = host, port
        self.jpeg_provider = jpeg_provider or (lambda: None)
        self.on_rest, self.on_expression, self.on_say = on_rest, on_expression, on_say
        self.httpd: ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self):
        handler = _make_handler(self)
        self.httpd = ThreadingHTTPServer((self.host, self.port), handler)
        self.httpd.daemon_threads = True
        self.port = self.httpd.server_address[1]  # 支持 port=0 让系统分配
        self._thread = threading.Thread(target=self.httpd.serve_forever,
                                        name="dashboard", daemon=True)
        self._thread.start()
        print(f"[dashboard] http://{self.host}:{self.port}")
        return self

    def stop(self):
        if self.httpd is not None:
            self.httpd.shutdown()
            self.httpd.server_close()
            self.httpd = None


def _make_handler(srv: DashboardServer):
    class Handler(BaseHTTPRequestHandler):
        server_version = "emobot/0.1"

        def log_message(self, fmt, *args):  # 关掉每请求一行的噪音
            pass

        # ---------- helpers ----------
        def _send(self, code: int, body: bytes, ctype: str):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)

        def _json(self, obj, code: int = 200):
            self._send(code, json.dumps(obj, ensure_ascii=False).encode(),
                       "application/json; charset=utf-8")

        def _body(self) -> dict:
            n = int(self.headers.get("Content-Length") or 0)
            if n <= 0:
                return {}
            try:
                return json.loads(self.rfile.read(n).decode("utf-8") or "{}")
            except (ValueError, UnicodeDecodeError):
                return {}

        # ---------- GET ----------
        def do_GET(self):
            url = urlparse(self.path)
            if url.path in ("/", "/index.html"):
                try:
                    html = DASHBOARD.read_bytes()
                except OSError as e:
                    self._send(500, f"dashboard.html 缺失: {e}".encode(), "text/plain; charset=utf-8")
                    return
                self._send(200, html, "text/html; charset=utf-8")
            elif url.path == "/api/state":
                self._json(srv.store.snapshot())
            elif url.path == "/api/health":
                self._json(srv.store.snapshot()["now"].get("status", {}))
            elif url.path == "/api/video.mjpg":
                self._mjpeg()
            else:
                self._send(404, b"not found", "text/plain")

        def _mjpeg(self):
            self.send_response(200)
            self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=frame")
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            try:
                while True:
                    frame = srv.jpeg_provider()
                    if frame:
                        self.wfile.write(b"--frame\r\nContent-Type: image/jpeg\r\n"
                                         b"Content-Length: " + str(len(frame)).encode() +
                                         b"\r\n\r\n" + frame + b"\r\n")
                    time.sleep(0.1)
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass

        # ---------- POST ----------
        def do_POST(self):
            path = urlparse(self.path).path
            body = self._body()
            try:
                if path == "/api/rest" and srv.on_rest:
                    srv.on_rest()
                elif path == "/api/expression" and srv.on_expression:
                    srv.on_expression(str(body.get("name", "neutral")),
                                      float(body.get("intensity", 1.0)))
                elif path == "/api/say" and srv.on_say:
                    srv.on_say(str(body.get("text", "")))
                else:
                    self._json({"ok": False, "error": f"未知接口 {path}"}, 404)
                    return
            except Exception as e:  # 接口出错不能把服务带走
                self._json({"ok": False, "error": str(e)}, 500)
                return
            self._json({"ok": True})

        def do_OPTIONS(self):  # 方便用别的端口调试前端
            self.send_response(204)
            self.send_header("Access-Control-Allow-Origin", "*")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.end_headers()

    return Handler


def serve_in_thread(store: StateStore, **kwargs) -> DashboardServer:
    return DashboardServer(store, **kwargs).start()
