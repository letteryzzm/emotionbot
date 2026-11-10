"""Web 调试界面：摄像头在哪台机器上就在哪跑，浏览器远程看。
  python -m camera.web --camera 2 --port 8000       然后打开 http://<这台机器的IP>:8000
画面(MJPEG) + 实时状态 + 22 路舵机 u + 参数滑条 + 强制表情 + 「发送到真机」开关。
只用标准库，不依赖 Flask。
"""
import argparse
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import cv2

from head.actuators import NAMES
from head.expressions import EXPRESSIONS

from .behavior import EXTRA, Behavior
from .vision import FaceTracker



ZONE_BGR = {"fear": (60, 60, 230), "annoyed": (40, 140, 240), "interested": (90, 200, 90), "bored": (170, 170, 170)}


class Engine(threading.Thread):
    def __init__(self, camera, hfov, width=640, fps=15, quality=50):
        super().__init__(daemon=True)
        self.camera, self.width, self.fps_target, self.quality = camera, width, fps, quality
        self.seq = 0
        self.rotate180 = False
        self.tracker = FaceTracker(hfov)
        self.beh = Behavior()
        self.beh.hfov = hfov
        self.lock = threading.Lock()
        self.jpeg = None
        self.state = {}
        self.hw = False
        self.head = None
        self.hw_msg = ""
        self.fps = 0.0
        self.running = True

    # ---- 参数 ----
    def set_params(self, p):
        b = self.beh
        for k in ("far", "near", "close", "gain", "fast_speed", "eye_alpha", "expr_alpha"):
            if k in p:
                setattr(b, k, float(p[k]))
        if "hfov" in p:
            self.tracker.hfov = b.hfov = float(p["hfov"])
        if "force" in p:
            b.force = p["force"] or None
        if "rotate180" in p:
            self.rotate180 = bool(p["rotate180"])
        if "hw" in p:
            self._set_hw(bool(p["hw"]))

    def params(self):
        b = self.beh
        return dict(far=b.far, near=b.near, close=b.close, gain=b.gain, fast_speed=b.fast_speed,
                    eye_alpha=b.eye_alpha, expr_alpha=b.expr_alpha, hfov=self.tracker.hfov,
                    force=b.force or "", hw=self.hw, rotate180=self.rotate180)

    def _set_hw(self, on):
        if on and self.head is None:
            try:
                from head import HeadClient
                self.head = HeadClient()
                self.hw_msg = f"已连接: {sorted(self.head.links)}"
            except Exception as e:  # noqa: BLE001
                self.hw_msg, on = f"连接失败: {e}", False
        if not on and self.head is not None and self.hw:
            self.head.rest()
        self.hw = on

    # ---- 主循环 ----
    def _open(self):
        cap = cv2.VideoCapture(self.camera, cv2.CAP_V4L2) if hasattr(cv2, "CAP_V4L2") else cv2.VideoCapture(self.camera)
        cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*"MJPG"))  # 摄像头直接出 MJPG，USB 带宽和发热都低
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.width * 3 // 4)
        cap.set(cv2.CAP_PROP_FPS, self.fps_target)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        return cap

    def run(self):
        cap = self._open()
        t0 = last = time.time()
        fails = 0
        period = 1.0 / self.fps_target
        while self.running:
            ok, frame = cap.read()
            if not ok:
                fails += 1
                if fails > 20:  # 摄像头掉线/过热停流：释放后重开
                    cap.release()
                    time.sleep(1.0)
                    cap = self._open()
                    fails = 0
                time.sleep(0.1)
                continue
            fails = 0
            if self.rotate180:   # 先转正再做检测，视线方向才对
                frame = cv2.rotate(frame, cv2.ROTATE_180)
            now = time.time()
            t = now - t0
            self.fps = 0.9 * self.fps + 0.1 / max(now - last, 1e-3)
            last = now
            obs, lm, bs = self.tracker.process(frame, t)
            u = self.beh.step(obs, t)
            if self.hw and self.head:
                self.head.set(u)
            self._draw(frame, obs, lm)
            _, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, self.quality])
            with self.lock:
                self.jpeg = buf.tobytes()
                self.seq += 1
                self.state = dict(
                    face=bool(obs), x=obs.x if obs else None, y=obs.y if obs else None,
                    dist=obs.dist_m if obs else None, zone=self.beh.state, ipd=obs.ipd_px if obs else None, startle=t < self.beh._startle_until, speed=self.beh._speed,
                    gaze=list(self.beh.gaze), fps=self.fps, hw=self.hw, hw_msg=self.hw_msg,
                    u=dict(zip(NAMES, map(float, u))),
                    blend={k: round(float(v), 3) for k, v in bs.items() if k != "_neutral"} if obs else {},
                )
            time.sleep(max(0.0, period - (time.time() - now)))  # 限帧率，给摄像头和 CPU 降温

    def _draw(self, frame, obs, lm):
        h, w = frame.shape[:2]
        cv2.line(frame, (w // 2, 0), (w // 2, h), (90, 90, 90), 1)
        cv2.line(frame, (0, h // 2), (w, h // 2), (90, 90, 90), 1)
        bh = self.beh
        if lm and obs:
            pa = (int(lm[468].x * w), int(lm[468].y * h))
            pb = (int(lm[473].x * w), int(lm[473].y * h))
            mid = ((pa[0] + pb[0]) // 2, (pa[1] + pb[1]) // 2)
            col = ZONE_BGR.get(bh.state, (0, 255, 255))
            cv2.line(frame, pa, pb, col, 2)   # 瞳距连线
            for q in (pa, pb):
                cv2.circle(frame, q, 5, (0, 255, 0), -1)
            cv2.circle(frame, mid, 14, (0, 255, 255), 3)                              # 人脸位置
            cv2.putText(frame, f"IPD {obs.ipd_px:.0f}px", (mid[0] - 40, mid[1] + 34),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, col, 1, cv2.LINE_AA)
            cv2.putText(frame, f"{obs.dist_m:.2f} m", (mid[0] - 45, mid[1] - 22),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.9, col, 2, cv2.LINE_AA)
        # 底部距离标尺：0~2.5m，按分界线上色，三角标出当前距离
        x0, x1, y = 20, w - 20, h - 24
        dmax = 2.5
        px = lambda d: int(x0 + (x1 - x0) * min(d, dmax) / dmax)  # noqa: E731
        edges = [0, bh.close, bh.near, bh.far, dmax]
        for lo, hi, z in zip(edges, edges[1:], ("fear", "annoyed", "interested", "bored")):
            cv2.rectangle(frame, (px(lo), y), (px(hi), y + 8), ZONE_BGR[z], -1)
        for d in (bh.close, bh.near, bh.far):
            cv2.putText(frame, f"{d:.2f}", (px(d) - 14, y - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.35, (230, 230, 230), 1, cv2.LINE_AA)
        if obs:
            x = px(obs.dist_m)
            cv2.drawMarker(frame, (x, y - 14), (255, 255, 255), cv2.MARKER_TRIANGLE_DOWN, 12, 2)


def make_handler(eng):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _json(self, obj):
            b = json.dumps(obj).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(b)))
            self.end_headers()
            self.wfile.write(b)

        def do_GET(self):
            if self.path == "/":
                html = (Path(__file__).parent / "web.html").read_bytes()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(html)))
                self.end_headers()
                self.wfile.write(html)
            elif self.path == "/stream":
                self.send_response(200)
                self.send_header("Content-Type", "multipart/x-mixed-replace; boundary=f")
                self.end_headers()
                try:
                    last = -1
                    while True:
                        with eng.lock:
                            j, seq = eng.jpeg, eng.seq
                        if j and seq != last:   # 只发新帧
                            last = seq
                            self.wfile.write(b"--f\r\nContent-Type: image/jpeg\r\nContent-Length: %d\r\n\r\n" % len(j) + j + b"\r\n")
                        time.sleep(0.02)
                except (BrokenPipeError, ConnectionResetError):
                    pass
            elif self.path == "/state":
                with eng.lock:
                    self._json(eng.state)
            elif self.path == "/params":
                self._json({"params": eng.params(), "poses": sorted(set(EXPRESSIONS) | set(EXTRA))})
            else:
                self.send_error(404)

        def do_POST(self):
            if self.path == "/params":
                n = int(self.headers.get("Content-Length", 0))
                eng.set_params(json.loads(self.rfile.read(n) or b"{}"))
                self._json(eng.params())
            else:
                self.send_error(404)

    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--camera", type=int, default=2)
    ap.add_argument("--hfov", type=float, default=65.0)
    ap.add_argument("--width", type=int, default=640)
    ap.add_argument("--fps", type=float, default=15)
    ap.add_argument("--quality", type=int, default=50)
    ap.add_argument("--rotate180", action="store_true", help="把画面转 180°")
    ap.add_argument("--port", type=int, default=8000)
    ap.add_argument("--host", default="0.0.0.0")
    a = ap.parse_args()
    eng = Engine(a.camera, a.hfov, a.width, a.fps, a.quality)
    eng.rotate180 = a.rotate180
    eng.start()
    print(f"http://{a.host}:{a.port}")
    ThreadingHTTPServer((a.host, a.port), make_handler(eng)).serve_forever()


if __name__ == "__main__":
    main()
