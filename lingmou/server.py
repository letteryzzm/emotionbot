"""灵眸总控：切模式、发指令、管其他服务。跑在 ROG 上，舵机仍然只由 head.hub_server 驱动。

    .venv/bin/python -m lingmou.server     # http://127.0.0.1:8800 控制台，/demo 演示页

模式决定该开哪些服务，后台每秒对账一次，所以服务崩了会被拉起来。不需要视觉的模式会关掉
camera.web，摄像头不用一直发热。全部卸力时同时关视觉、停戏台、暂停听。
"""
import argparse
import json
import os
import re
import signal
import subprocess
import threading
import time
import urllib.request
from collections import namedtuple
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from camera.behavior import CLOSE, FAR, GAZE_GAIN, NEAR, zone
from camera.mimic import NEUTRAL_FILE, label, load_neutral, normalize
from culture.actions import ACTIONS
from head.actuators import EYE_BROW_L_IS_ROBOT_LEFT, LR_UP_IS_ROBOT_LEFT, MOUTH_L_IS_ROBOT_LEFT, NAMES, rest_vector
from head.hub import HOLD, NEVER_DRIVE
from head.hub_client import HubClient
from head.hub_server import POSES

HERE = Path(__file__).parent
ROOT = HERE.parent
SAMPLES = ROOT / "culture" / "samples"
SETTINGS = ROOT / "outputs" / "lingmou.json"
CAMERA_HOME = Path.home() / "robotic" / "robothead"
CAMERA_NAME = "USB 2.0 Camera"     # 外接摄像头，笔记本自带的叫 USB2.0 HD
HUB, CAMERA, CULTURE, VOICE = (f"http://127.0.0.1:{p}" for p in (8780, 8000, 8790, 8767))
ENV = {"XDG_RUNTIME_DIR": os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}")}
MAX_BODY = 65536
SSE_HZ = 15
RESTART_GAP_S = 5.0
SCAN_S = 0.5
CAMERA_STALE_S = 5.0
HOLD_TTL = 3600.0
POSE_TTL = 4.0
TOUR_GAP_S = 0.8

Mode = namedtuple("Mode", "name note camera voice opera life mimic")
MODES = {
    "standby": Mode("待机", "只有眼球游动和眨眼", False, False, False, True, False),
    "track": Mode("视觉跟随", "眼睛跟人，表情随距离变", True, False, False, True, False),
    "talk": Mode("语音对话", "对着麦克风说话，脸跟着回答", False, True, False, True, False),
    "interact": Mode("全互动", "边看边听，说话时眼睛继续跟人", True, True, False, True, False),
    "mimic": Mode("表情模仿", "照镜子一样学你的脸：眨眼、挑眉、张嘴、笑", True, False, False, False, True),
    "opera": Mode("戏台", "演京剧和动漫动作", False, False, True, True, False),
    "manual": Mode("手动", "表情、视线和舵机由你摆，关掉待机动作", False, False, False, False, False),
}
DEFAULTS = {"far": FAR, "near": NEAR, "close": CLOSE, "gain": GAZE_GAIN, "flip_x": False, "wake": "", "camera_fps": 10,
            "mimic_swap": False, "mimic_gain": 1.0}


class Refused(Exception):
    """消息直接显示给用户。"""


def get_json(url, timeout=0.4):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.load(r)


def post_json(url, body, timeout=3.0):
    req = urllib.request.Request(url, json.dumps(body).encode(), {"Content-Type": "application/json", "X-Head": "1"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return json.loads(r.read() or b"{}")


def camera_index(root="/sys/class/video4linux"):
    for d in sorted(Path(root).glob("video*")):
        try:
            if CAMERA_NAME in (d / "name").read_text() and (d / "index").read_text().strip() == "0":
                return int(d.name[5:])
        except (OSError, ValueError):
            continue
    return None


_scan = (-1.0, [])


def process_table(fresh=False):
    """扫一次 /proc 要十几毫秒，几个服务共用一份。"""
    global _scan
    now = time.monotonic()
    if fresh or now - _scan[0] > SCAN_S:
        table = []
        for p in Path("/proc").glob("[0-9]*"):
            try:
                table.append((int(p.name), (p / "cmdline").read_bytes().split(b"\0")))
            except OSError:
                continue
        _scan = (now, table)
    return _scan[1]


class Service:
    """按命令行认进程，所以总控重启后还认得之前拉起来的服务。"""

    def __init__(self, name, match, cwd, command, env=None, clock=time.monotonic):
        self.name, self.match, self.cwd, self.command, self.env, self.clock = name, match, cwd, command, env or {}, clock
        self.proc = None
        self.last_start = -RESTART_GAP_S
        self.note = ""

    def pids(self, fresh=False):
        return [pid for pid, argv in process_table(fresh)
                if b"python" in argv[0] and any(self.match.encode() in a for a in argv[1:])]

    def running(self):
        if self.proc is not None:
            self.proc.poll()   # 收掉已退出的子进程
        return bool(self.pids())

    def ensure(self, want):
        up = self.running()
        if want and not up and self.clock() - self.last_start >= RESTART_GAP_S:
            self.start()
        elif not want and up:
            self.stop()

    def start(self):
        cmd = self.command()
        if cmd is None:
            return
        self.note = ""
        self.last_start = self.clock()
        log = open(ROOT / "outputs" / f"{self.name}.log", "ab")
        self.proc = subprocess.Popen(cmd, cwd=self.cwd, stdin=subprocess.DEVNULL, stdout=log, stderr=subprocess.STDOUT,
                                     start_new_session=True, env={**os.environ, **self.env})
        log.close()

    def stop(self):
        for pid in self.pids(fresh=True):
            try:
                os.kill(pid, signal.SIGTERM)
            except OSError:
                pass
        end = time.monotonic() + 2
        while self.pids(fresh=True) and time.monotonic() < end:
            time.sleep(0.05)
        for pid in self.pids(fresh=True):
            try:
                os.kill(pid, signal.SIGKILL)
            except OSError:
                pass


class Controller:
    def __init__(self, hub, services, post=post_json, fetch=get_json, clock=time.monotonic, settings_path=SETTINGS):
        self.hub, self.services, self.post, self.fetch, self.clock = hub, services, post, fetch, clock
        self.settings_path = settings_path
        self.settings = dict(DEFAULTS)
        try:
            self.settings.update(json.loads(settings_path.read_text()))
        except (OSError, ValueError):
            pass
        self.mode = "standby"
        self.preview = False
        self.message = ""
        self.lock = threading.RLock()
        self.hub_lock = threading.Lock()
        self.tour = 0
        self.tour_left = []
        self.snap = {"hub": None, "camera": None, "voice": None, "opera": None}
        self.volume = None
        self.mic = None
        self.camera_fps = None
        self.camera_changed = clock()
        self.up = {}
        self.neutral = load_neutral()
        self.payload = b"{}"
        self.halt = threading.Event()

    # ---- 控制进程 ----
    def _hub(self, method, *a, **k):
        with self.hub_lock:
            ok = getattr(self.hub, method)(*a, **k)
            error = self.hub.error
        if not ok:
            raise Refused(error or "控制进程没响应")

    def _hub_op(self, body):
        with self.hub_lock:
            ok = self.hub._post(body)
            error = self.hub.error
        if not ok:
            raise Refused(error or "控制进程没响应")

    # ---- 模式 ----
    def set_mode(self, name):
        if name not in MODES:
            raise Refused("没有这个模式")
        with self.lock:
            m = MODES[name]
            self.tour += 1
            self.tour_left = []
            self.mode = name
            self._quiet(self._opera, {"op": "stop"})
            self._quiet(self._opera, {"op": "robot", "on": m.opera})
            self._quiet(self._voice, "listen" if m.voice else "pause")
            self._hub("clear", "manual")
            self._hub("clear", "dialog")
            self._hub_op({"op": "life", "on": m.life})

    @staticmethod
    def _quiet(fn, arg):
        """服务可能还没起来，对账循环会补上。"""
        try:
            fn(arg)
        except OSError:
            pass

    def _opera(self, body):
        return self.post(CULTURE + "/api", body)

    def _voice(self, cmd):
        r = self.post(VOICE + "/cmd", {"cmd": cmd}, timeout=5.0)
        if not r.get("ok"):
            raise Refused(r.get("error") or "语音服务拒绝了这条指令")
        return r

    def estop(self):
        """先卸力，后面的步骤失败也不影响。"""
        try:
            self._hub_op({"op": "estop"})
        finally:
            with self.lock:
                self.tour += 1
                self.tour_left = []
                self.mode = "standby"
                self.preview = False
                self._quiet(self._opera, {"op": "stop"})
                self._quiet(self._opera, {"op": "robot", "on": False})
                self._quiet(self._voice, "pause")

    # ---- 戏台 ----
    def play(self, action, intensity=1.0):
        if action not in ACTIONS:
            raise Refused("没有这个动作")
        with self.lock:
            if self.mode != "opera":
                self.set_mode("opera")
            self.tour += 1
            self.tour_left = []
            self.post(CULTURE + "/api", {"op": "play", "action": action, "intensity": intensity})

    def stop_opera(self):
        with self.lock:
            self.tour += 1
            self.tour_left = []
            self._opera({"op": "stop"})

    def start_tour(self, group="opera", intensity=1.0):
        names = [a.id for a in ACTIONS.values() if a.group == group]
        if not names:
            raise Refused("没有这组动作")
        with self.lock:
            if self.mode != "opera":
                self.set_mode("opera")
            self.tour += 1
            self.tour_left = list(names)
            ticket = self.tour
        threading.Thread(target=self._tour, args=(ticket, intensity), daemon=True).start()

    def _tour(self, ticket, intensity):
        while not self.halt.is_set():
            with self.lock:
                if ticket != self.tour or not self.tour_left:
                    return
                action = self.tour_left.pop(0)
                try:
                    self._opera({"op": "play", "action": action, "intensity": intensity})
                except OSError as e:
                    self.message = f"巡演中断：{e}"
                    return
            self.halt.wait(ACTIONS[action].duration + TOUR_GAP_S)

    # ---- 手动 ----
    def pose(self, name, intensity=1.0):
        if name not in POSES:
            raise Refused("没有这个表情")
        self._hub("pose", "manual", name, intensity=intensity, ttl=HOLD_TTL if self.mode == "manual" else POSE_TTL)

    def servos(self, values):
        bad = set(values) - set(NAMES) - NEVER_DRIVE
        if bad or NEVER_DRIVE & set(values) or set(HOLD) & set(values):
            raise Refused("这个舵机不能手动驱动")
        if self.mode != "manual":
            self.set_mode("manual")
        self._hub("intent", "manual", values, ttl=HOLD_TTL, merge=True)

    # ---- 设置 ----
    def update_settings(self, req):
        new = dict(self.settings)
        for k in ("far", "near", "close", "gain"):
            if k in req:
                new[k] = float(req[k])
        if "flip_x" in req:
            new["flip_x"] = bool(req["flip_x"])
        if "mimic_swap" in req:
            new["mimic_swap"] = bool(req["mimic_swap"])
        if "mimic_gain" in req:
            new["mimic_gain"] = float(req["mimic_gain"])
        if "camera_fps" in req:
            new["camera_fps"] = min(15.0, max(3.0, float(req["camera_fps"])))
        if "wake" in req:
            new["wake"] = str(req["wake"]).strip()[:12]
        if not 0 < new["close"] < new["near"] < new["far"]:
            raise Refused("距离要满足 贴脸 < 太近 < 太远")
        if not 0.2 <= new["gain"] <= 3:
            raise Refused("跟随比例要在 0.2 到 3 之间")
        if not 0.3 <= new["mimic_gain"] <= 2.5:
            raise Refused("模仿幅度要在 0.3 到 2.5 之间")
        changed = {k for k in new if new[k] != self.settings[k]}
        self.settings = new
        try:
            self.settings_path.write_text(json.dumps(new, ensure_ascii=False))
        except OSError as e:
            self.message = f"设置没存上：{e}"
        restart = {"far": "vision", "near": "vision", "close": "vision", "gain": "vision", "flip_x": "vision",
                   "camera_fps": "camera", "wake": "voice", "mimic_swap": "mimic", "mimic_gain": "mimic"}
        for name in {restart[k] for k in changed}:
            self.services[name].stop()

    def calibrate_mimic(self):
        """把现在这一帧当成平静脸。模仿进程看到文件变了会自己读。"""
        c = self.snap["camera"] or {}
        if not (c.get("face") and c.get("blend")):
            raise Refused("摄像头里没看到人脸，先站到摄像头前做一个平静的脸")
        NEUTRAL_FILE.write_text(json.dumps(c["blend"]))
        self.neutral = dict(c["blend"])

    def set_volume(self, percent, kind="sink"):
        percent = min(150 if kind == "source" else 100, max(0, int(percent)))
        subprocess.run(["pactl", f"set-{kind}-volume", f"@DEFAULT_{kind.upper()}@", f"{percent}%"],
                       env={**os.environ, **ENV}, timeout=3, check=False, capture_output=True)
        if kind == "sink":
            self.volume = percent
        else:
            self.mic = percent

    def _read_level(self, kind):
        try:
            r = subprocess.run(["pactl", f"get-{kind}-volume", f"@DEFAULT_{kind.upper()}@"], env={**os.environ, **ENV},
                               timeout=2, capture_output=True, text=True, check=False)
        except (OSError, subprocess.SubprocessError):
            return None
        hit = re.search(r"(\d+)%", r.stdout)
        return int(hit.group(1)) if hit else None

    def read_volume(self):
        self.volume, self.mic = self._read_level("sink"), self._read_level("source")

    # ---- 对账和状态 ----
    def reconcile(self):
        m = MODES[self.mode]
        s = self.services
        for name in ("hub", "culture", "voice"):
            s[name].ensure(True)
        s["camera"].ensure(m.camera or self.preview)
        s["vision"].ensure(m.camera and not m.mimic)
        s["mimic"].ensure(m.mimic)
        voice, opera = self.snap["voice"], self.snap["opera"]
        if voice and voice.get("paused") == m.voice:
            self._quiet(self._voice, "listen" if m.voice else "pause")
        if opera and opera.get("robot") != m.opera:
            self._quiet(self._opera, {"op": "robot", "on": m.opera})

    def _watch_camera(self, state):
        if state is None:
            self.camera_fps = None
            self.camera_changed = self.clock()
            return True
        if state.get("fps") != self.camera_fps:
            self.camera_fps = state.get("fps")
            self.camera_changed = self.clock()
        return self.clock() - self.camera_changed < CAMERA_STALE_S

    def poll(self, what):
        try:
            if what == "hub":
                self.snap["hub"] = self.fetch(HUB + "/state")
            elif what == "opera":
                self.snap["opera"] = self.fetch(CULTURE + "/state")
            elif what == "camera":
                self.snap["camera"] = self.fetch(CAMERA + "/state")
            elif what == "voice":
                self.snap["voice"] = self.fetch(VOICE + "/state", timeout=1.0)
        except (OSError, ValueError):
            self.snap[what] = None

    def camera_view(self):
        c = self.snap["camera"]
        running = self.up.get("camera", False)
        fresh = self._watch_camera(c)
        if c is None:
            return {"running": running, "ok": False, "face": False, "dist": None, "x": None, "y": None, "zone": None,
                    "fps": 0, "note": self.services["camera"].note}
        st = self.settings
        face = bool(c.get("face")) and fresh
        blend = normalize(c.get("blend") or {}, self.neutral) if face else {}
        top = sorted(((k, round(v, 2)) for k, v in blend.items() if v >= 0.15), key=lambda kv: -kv[1])[:6]
        return {"running": running, "ok": fresh, "face": face, "dist": c.get("dist") if face else None,
                "x": c.get("x") if face else None, "y": c.get("y") if face else None,
                "zone": zone(c.get("dist") if face else None, st["far"], st["near"], st["close"]),
                "expr": label(blend) if blend else None, "top": top, "calibrated": bool(self.neutral),
                "fps": round(c.get("fps") or 0, 1), "note": self.services["camera"].note}

    def voice_view(self):
        s = self.snap["voice"]
        if s is None:
            return {"running": self.up.get("voice", False), "ready": False, "paused": True, "turns": []}
        v = s.get("voice", {})
        error = s.get("error") or v.get("error")
        if error and ("402" in error or "1008" in error):
            error = "MiniMax 余额不足，语音回答和合成都用不了，充值后恢复"
        return {"running": True, "ready": True, "paused": s.get("paused"), "status": v.get("status"),
                "emotion": v.get("emotion"), "rms": v.get("rms"), "threshold": v.get("threshold"),
                "awake": v.get("awake"), "error": error, "turns": v.get("all", [])[-8:]}

    def state(self):
        hub = self.snap["hub"]
        opera = self.snap["opera"]
        return {
            "mode": self.mode, "preview": self.preview, "message": self.message, "settings": self.settings,
            "volume": self.volume, "mic": self.mic, "tour_left": len(self.tour_left),
            "hub": hub, "opera": opera, "camera": self.camera_view(), "voice": self.voice_view(),
            "services": {n: self.up.get(n, False) for n in self.services},
        }

    def run(self):
        """状态轮询和对账放一个线程，彼此不会抢。"""
        tick = 0
        while not self.halt.is_set():
            start = time.monotonic()
            self.poll("hub")
            self.poll("opera")
            if tick % 3 == 0:
                self.poll("camera")
            if tick % 8 == 0:
                self.poll("voice")
            if tick % 15 == 0:
                with self.lock:
                    self._reconcile_safely()
                self.up = {n: s.running() for n, s in self.services.items()}
                c = self.camera_view()
                if c["running"] and not c["ok"] and self.snap["camera"] is not None:
                    self.services["camera"].stop()
            if tick % 75 == 0:
                self.read_volume()
            tick += 1
            self.payload = json.dumps(self.state(), ensure_ascii=False).encode()
            self.halt.wait(max(0.0, 1 / SSE_HZ - (time.monotonic() - start)))

    def _reconcile_safely(self):
        try:
            self.reconcile()
        except (OSError, Refused, subprocess.SubprocessError) as e:
            self.message = f"对账失败：{e}"

    # ---- 指令入口 ----
    def dispatch(self, req):
        op = req.get("op")
        if op == "mode":
            self.set_mode(req.get("mode"))
        elif op == "arm":
            self._hub_op({"op": "arm"})
        elif op == "estop":
            self.estop()
        elif op == "life":
            self._hub_op({"op": "life", "on": bool(req.get("on"))})
        elif op == "pose":
            self.pose(req.get("pose"), float(req.get("intensity", 1.0)))
        elif op == "clear_manual":
            self._hub("clear", "manual")
        elif op == "servos":
            self.servos({k: float(v) for k, v in dict(req.get("values") or {}).items()})
        elif op == "play":
            self.play(req.get("action"), float(req.get("intensity", 1.0)))
        elif op == "stop":
            self.stop_opera()
        elif op == "tour":
            self.start_tour(req.get("group", "opera"), float(req.get("intensity", 1.0)))
        elif op == "say":
            text = str(req.get("text", "")).strip()[:300]
            if not text:
                raise Refused("先写点什么")
            self._voice("say:" + text)
        elif op == "mimic_calibrate":
            self.calibrate_mimic()
        elif op == "preview":
            self.preview = bool(req.get("on"))
        elif op == "settings":
            self.update_settings(req)
        elif op == "volume":
            self.set_volume(req.get("percent"), "source" if req.get("mic") else "sink")
        else:
            raise Refused("没有这个指令")


def meta():
    rest = dict(zip(NAMES, (float(x) for x in rest_vector())))
    return {
        "modes": {k: {"name": m.name, "note": m.note} for k, m in MODES.items()},
        "poses": list(POSES),
        "actions": [{"id": a.id, "group": a.group, "name": a.name, "use": a.use, "note": a.note, "skin": a.skin,
                     "duration": a.duration} for a in ACTIONS.values()],
        "samples": json.loads((SAMPLES / "index.json").read_text()) if (SAMPLES / "index.json").exists() else [],
        "rest": rest,
        "names": [n for n in NAMES if n not in NEVER_DRIVE and n not in HOLD],
        "flags": {"eye_l_robot_left": EYE_BROW_L_IS_ROBOT_LEFT, "mouth_l_robot_left": MOUTH_L_IS_ROBOT_LEFT,
                  "lr_up_robot_left": LR_UP_IS_ROBOT_LEFT},
    }


def make_handler(ctl):
    pages = {"/": HERE / "console.html", "/demo": HERE / "demo.html"}

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

        def _stream_headers(self, ctype):
            self.send_response(200)
            self.send_header("Content-Type", ctype)
            self.send_header("Cache-Control", "no-cache")
            self.send_header("Connection", "close")
            self.end_headers()
            self.close_connection = True

        def do_GET(self):
            if self.path in pages:
                self._send(200, pages[self.path].read_bytes(), "text/html; charset=utf-8")
            elif self.path == "/face.js":
                self._send(200, (ROOT / "culture" / "face.js").read_bytes(), "text/javascript; charset=utf-8")
            elif self.path == "/meta":
                self._json(meta())
            elif self.path == "/state":
                self._send(200, ctl.payload)
            elif self.path == "/events":
                self._stream_headers("text/event-stream")
                try:
                    while not ctl.halt.is_set():
                        self.wfile.write(b"data: " + ctl.payload + b"\n\n")
                        self.wfile.flush()
                        time.sleep(1 / SSE_HZ)
                except OSError:
                    pass
            elif self.path.split("?")[0] == "/cam":   # 页面带时间戳，防止浏览器复用断开的流
                self._camera()
            elif self.path.startswith("/samples/"):
                name = self.path.rsplit("/", 1)[1]
                if name not in {s["file"] for s in meta()["samples"]}:
                    return self._send(404, b"{}")
                self._send(200, (SAMPLES / name).read_bytes(), "image/jpeg")
            else:
                self._send(404, b"{}")

        def _camera(self):
            try:
                up = urllib.request.urlopen(CAMERA + "/stream", timeout=3)
            except OSError:
                return self._send(503, b"{}")
            self._stream_headers(up.headers.get("Content-Type", "multipart/x-mixed-replace"))
            try:
                while not ctl.halt.is_set():
                    data = up.read1(65536)
                    if not data:
                        break
                    self.wfile.write(data)
                    self.wfile.flush()
            except OSError:
                pass
            finally:
                up.close()

        def do_POST(self):
            # 自定义头让别的网页没法跨站发命令
            length = int(self.headers.get("Content-Length") or 0)
            if self.headers.get("X-Head") != "1" or self.path != "/api" or not 0 < length <= MAX_BODY:
                self.close_connection = True
                return self._send(403, b"{}")
            try:
                ctl.dispatch(json.loads(self.rfile.read(length)))
            except Refused as e:
                return self._json({"error": str(e)}, 400)
            except (ValueError, KeyError, TypeError, AttributeError) as e:
                return self._json({"error": f"指令格式不对：{e}"}, 400)
            except OSError as e:
                return self._json({"error": f"服务没响应：{e}"}, 502)
            self._json({"ok": True})

    return Handler


class Server(ThreadingHTTPServer):
    daemon_threads = True


def services_for(ctl_settings):
    py = str(ROOT / ".venv" / "bin" / "python")

    def camera():
        index = camera_index()
        if index is None:
            svc["camera"].note = "没找到外接摄像头"
            return None
        return [str(CAMERA_HOME / ".venv" / "bin" / "python"), "-m", "camera.web", "--camera", str(index), "--port", "8000",
                "--host", "127.0.0.1", "--rotate180", "--fps", str(ctl_settings()["camera_fps"])]

    def vision():
        s = ctl_settings()
        return [py, "-m", "camera.hub_source", "--far", str(s["far"]), "--near", str(s["near"]), "--close", str(s["close"]),
                "--gain", str(s["gain"])] + (["--flip-x"] if s["flip_x"] else [])

    def mimic():
        s = ctl_settings()
        return [py, "-m", "camera.mimic", "--gain", str(s["mimic_gain"])] + (["--swap"] if s["mimic_swap"] else [])

    def voice():
        wake = ctl_settings()["wake"]
        return ["tools/voice_test/.venv/bin/python", "scripts/rog_voice.py", "--listen", "127.0.0.1:8767"] + \
            (["--wake", wake] if wake else [])

    svc = {
        "hub": Service("hub", "head.hub_server", ROOT, lambda: [py, "-m", "head.hub_server", "--allow-unverified", "--speed", "600"]),
        "culture": Service("culture", "culture.server", ROOT, lambda: [py, "-m", "culture.server", "--port", "8790"]),
        "voice": Service("voice", "scripts/rog_voice.py", ROOT, voice, env={**ENV, "PYTHONPATH": "."}),
        "camera": Service("camera", "camera.web", CAMERA_HOME, camera),
        "vision": Service("vision", "camera.hub_source", ROOT, vision),
        "mimic": Service("mimic", "camera.mimic", ROOT, mimic),
    }
    return svc


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8800)
    a = ap.parse_args()
    ctl = Controller(HubClient(timeout=5.0), {})
    ctl.services = services_for(lambda: ctl.settings)
    server = Server(("127.0.0.1", a.port), make_handler(ctl))
    threading.Thread(target=ctl.run, daemon=True).start()
    print(f"http://127.0.0.1:{a.port}  控制台    http://127.0.0.1:{a.port}/demo  演示", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        ctl.halt.set()


if __name__ == "__main__":
    main()
