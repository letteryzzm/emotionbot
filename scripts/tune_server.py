"""网页调试台：逐组通电、小步转动、记录现象。写入 outputs/tune_log.jsonl，和 tune.py 同一份日志。

  .venv/bin/python scripts/tune_server.py        # 只听 127.0.0.1:8770

运行时独占三块 Pico 的串口，不要同时跑 tune.py / servo_step.py。
启动时只读角度，不让舵机动，也不卸力。

每秒检查一次串口。USB 断开时 Pico 可能靠 5V 继续跑，舵机还在受力，
所以板子重新出现时先发 X。
"""
import glob
import json
import sys
import threading
import time
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import NamedTuple

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from head.actuators import BY_NAME, center, save_center, to_angles  # noqa: E402
from camera.behavior import gaze_to_u  # noqa: E402
from head.expressions import EXPRESSIONS, expression  # noqa: E402
from head.eye_motion import EYES, eye_frames, eye_pose  # noqa: E402
from head.hub import load_verified  # noqa: E402

LOG = ROOT / "outputs" / "tune_log.jsonl"
PORT = 8770
SPEED = 300
MAX_STEP = 5
JAW_SKEW = 5   # JL + JR 偏离 180 的上限，两个 MG996R 不能互相顶
SWING_AMPS = (15, 30)
BOARDS = ("eyes", "brows", "mouth")

# 从下到上，和 docs/舵机接线与上电检查.html 的嘴部图一致
GROUPS = [
    ("舌头", ["TON"]), ("下唇", ["LLL", "LLR"]), ("嘴角前后", ["CLL", "CLR"]), ("下巴", ["JL", "JR"]),
    ("嘴角上下", ["CUL", "CUR"]), ("上唇", ["LUL", "LUR"]),
    ("眉外侧", ["LO", "RO"]), ("眉内侧", ["LI", "RI"]),
    ("下眼皮", ["BL", "BR"]), ("上眼皮", ["TL", "TR"]), ("眼球左右", ["LR"]), ("眼球上下", ["UD"]),
]


INTENSITIES = (0.3, 0.6, 1.0)
GAZE = set(EYES)   # 每个表情都驱动整个眼部，UD 带补偿


# 视觉跟踪：只读 camera.web 的结果，不开摄像头。只跟有实测范围的 LR
VISION_URL = "http://127.0.0.1:8000"
TRACK_SERVO = "LR"
TRACK_HZ = 10
TRACK_STEP = 3        # 每拍最多转的度数，10Hz 时是 30°/s
TRACK_DEADBAND = 1    # 差不到这么多就不发，避免舵机抖
TRACK_ALPHA = 0.4
TRACK_LOST = 3.0      # 秒，看不到脸这么久才慢慢回中心
_no_proxy = urllib.request.build_opener(urllib.request.ProxyHandler({}))


def read_vision(path):
    with _no_proxy.open(VISION_URL + path, timeout=0.3) as r:
        return json.load(r)


class Refused(Exception):
    pass


class Frame(NamedTuple):
    """眼部动画的一帧：自己的速度和停留时间"""
    goal: dict
    speed: float
    hold: float


def expression_steps(name, k):
    """表情拆成一组一组的目标角度，只含表情写到的舵机和视线，其他舵机不通电"""
    ang = {**to_angles(expression(name, k)), **eye_pose(name, k)}
    wanted = set(EXPRESSIONS[name]) | GAZE
    steps = []
    for label, names in GROUPS:
        goal = {n: round(ang[n], 1) for n in names if n in wanted}
        if goal:
            steps.append({"label": label, "goal": goal})
    return steps


def tested_ranges(path=LOG):
    """日志里真机走过的角度范围。没走过的要提醒，不代表走过的就没问题"""
    seen = {}
    if not path.exists():
        return seen
    for line in path.read_text().splitlines():
        r = json.loads(line)
        if r.get("type") == "cmd" and r["cmd"].startswith("S "):
            for kv in r["cmd"].split()[1:]:
                n, _, v = kv.partition("=")
                lo, hi = seen.get(n, (float(v), float(v)))
                seen[n] = (min(lo, float(v)), max(hi, float(v)))
    return seen


def direction(name):
    a = BY_NAME[name]
    return 1 if a.b > a.a else -1


def clip(name, deg):
    a = BY_NAME[name]
    return float(min(max(deg, min(a.a, a.b)), max(a.a, a.b)))


def default_log(entry):
    LOG.parent.mkdir(exist_ok=True)
    with LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def discover(skip=()):
    import serial

    links = {}
    for p in glob.glob("/dev/serial/by-id/*MicroPython*"):
        if p in skip:
            continue
        s = serial.Serial(p, 115200, timeout=0.5)
        time.sleep(0.1)
        s.reset_input_buffer()
        s.write(b"?\n")
        line = s.readline().decode(errors="ignore").strip()
        if line.startswith("ROLE "):
            links[line.split()[1]] = s
        else:
            s.close()
    return links


class Bench:
    save_center = staticmethod(save_center)

    log_path = LOG
    vision = staticmethod(read_vision)

    def __init__(self, links, log=default_log, settle=0.4, pace=1.0, rediscover=None):
        self.links, self.log, self.settle, self.pace = links, log, settle, pace
        self.rediscover = rediscover
        self.lock = threading.Lock()
        self.stop = threading.Event()
        self.job = None        # 正在跑的回中或摆动
        self.script = None     # 当前表情的分步计划
        self.tracking = None   # 视觉跟踪的状态，None 是没开
        self.powered = set()   # 这个服务通过电的舵机；启动前已通电的不在内
        self.held = set()      # 用户要求一直保持的舵机，只有全部卸力才放开
        self.angles = {}
        self.error = ""
        for board in list(links):
            self._read(board)

    def _record(self, kind, **kw):
        self.log({"t": time.strftime("%Y-%m-%d %H:%M:%S"), "type": kind, **kw})

    def _ask(self, board, line):
        link = self.links.get(board)
        if link is None:
            raise Refused(f"{board} 板不在线")
        try:
            link.write((line + "\n").encode())
            return link.readline().decode(errors="ignore").strip()
        except Exception as e:
            self._lost(board)
            raise Refused(f"{board} 板串口断开：{e}")

    def _lost(self, board):
        # 跟踪值可能已回到 90，必须重新通电。舵机可能还在受力，所以要提醒
        link = self.links.pop(board, None)
        if link is not None and hasattr(link, "close"):
            try:
                link.close()
            except Exception:
                pass
        self.stop.set()
        self.powered -= {n for n in self.powered if BY_NAME[n].board == board}
        self.held -= {n for n in self.held if BY_NAME[n].board == board}
        self.error = f"{time.strftime('%H:%M:%S')} {board} 板掉线，舵机可能还在受力。听到嗡嗡声就断 5V"

    def _read(self, board):
        reply = self._ask(board, "G")
        got = {k: float(v) for k, v in (kv.split("=") for kv in reply.split()[1:])}
        self.angles.update(got)
        return got

    def beat(self):
        """每秒一次：发现掉线，并在板子回来时马上卸力"""
        with self.lock:
            for board in list(self.links):
                try:
                    if not self._ask(board, "?").startswith("ROLE "):
                        self._lost(board)
                except Refused:
                    pass
            if self.rediscover is None or set(BOARDS) <= set(self.links):
                return
            skip = {getattr(link, "port", None) for link in self.links.values()}
            for board, link in self.rediscover(skip).items():
                self.links[board] = link
                reply = self._ask(board, "X")
                self._read(board)
                self.error = f"{time.strftime('%H:%M:%S')} {board} 板已重连并卸力。查一下掉线原因再通电"
                self._record("cmd", board=board, cmd="X", reply=f"重连后自动卸力 {reply}", angles=self.angles)

    def _busy(self):
        return self.job is not None and self.job.is_alive()

    def _start(self, legs, additive=False, done=None, dwell=0.2):
        self.stop.clear()
        self.job = threading.Thread(target=self._legs, args=(legs, additive, done, dwell), daemon=True)
        self.job.start()

    def _legs(self, legs, additive=False, done=None, dwell=0.2):
        # 一步里每块板发一条 S，几块板同时动。等待时不占锁，卸力才能马上插进来
        try:
            for leg in legs:
                frame = leg if isinstance(leg, Frame) else None
                goal = frame.goal if frame else leg
                speed = frame.speed if frame else SPEED
                by_board = {}
                for n, v in goal.items():
                    by_board.setdefault(BY_NAME[n].board, {})[n] = v
                now = {}
                with self.lock:
                    if self.stop.is_set():
                        return
                    for board, part in by_board.items():
                        now.update(self._read(board))
                        self._ask(board, f"V {speed}")
                        line = "S " + " ".join(f"{n}={v:g}" for n, v in part.items())
                        reply = self._ask(board, line)
                        if reply != "OK":
                            raise Refused(reply)
                        if additive:
                            self.powered |= set(part)
                        self._record("cmd", board=board, cmd=line, reply=reply, angles=self.angles)
                dist = max(abs(v - now[n]) for n, v in goal.items())
                if self.stop.wait(self.pace * (frame.hold if frame else dist / SPEED + dwell)):
                    return
                with self.lock:
                    for board in by_board:
                        self._read(board)
            if done:
                done()
        except Refused as e:
            self.error = str(e)

    def expr(self, name, intensity):
        """准备一个表情，不动舵机"""
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if name not in EXPRESSIONS:
                raise Refused(f"没有这个表情：{name}")
            if intensity not in INTENSITIES:
                raise Refused(f"强度只能是 {INTENSITIES}")
            seen = tested_ranges(self.log_path)
            steps = expression_steps(name, intensity)
            for s in steps:
                s["new"] = [n for n, v in s["goal"].items()
                            if n not in seen or not seen[n][0] <= v <= seen[n][1]]
            self.script = {"name": name, "intensity": intensity, "steps": steps, "i": 0}

    def _finish(self):
        sc = self.script
        if sc is None:
            return
        lines = [f'{s["label"]}: S ' + " ".join(f"{n}={v:g}" for n, v in s["goal"].items()) for s in sc["steps"]]
        self._record("recipe", name=f'{sc["name"]} 强度 {sc["intensity"]}', text="分步走完，现象看过程记录", steps=lines)

    def expr_next(self):
        with self.lock:
            sc = self.script
            if self._busy():
                raise Refused("上一个动作还没结束")
            if sc is None or sc["i"] >= len(sc["steps"]):
                raise Refused("先选一个表情")
            step = sc["steps"][sc["i"]]
            sc["i"] += 1
            last = sc["i"] == len(sc["steps"])
            self._start([step["goal"]], additive=True, done=self._finish if last else None)

    def expr_all(self):
        with self.lock:
            sc = self.script
            if self._busy():
                raise Refused("上一个动作还没结束")
            if sc is None or sc["i"] >= len(sc["steps"]):
                raise Refused("先选一个表情")
            legs = [s["goal"] for s in sc["steps"][sc["i"]:]]
            sc["i"] = len(sc["steps"])
            self._start(legs, additive=True, done=self._finish)

    def _pose(self, name, k, active):
        """这个表情的完整目标：写到的舵机加视线，之前动过的回 rest。保持的舵机不碰"""
        ang = {**to_angles(expression(name, k)), **eye_pose(name, k)}
        names = (set(EXPRESSIONS[name]) | GAZE | active) - self.held - {"EXA"}
        return {n: round(ang[n], 1) for n in sorted(names)}

    def expr_go(self, name, intensity):
        """整个表情一起做"""
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if name not in EXPRESSIONS or intensity not in INTENSITIES:
                raise Refused("表情或强度不对")
            goal = self._pose(name, intensity, self.powered)
            done = lambda: self._record("recipe", name=f"{name} 强度 {intensity}", text="一起做",  # noqa: E731
                                        steps=["S " + " ".join(f"{n}={v:g}" for n, v in goal.items())])
            self._start([goal] + self._eye_legs(name, intensity), additive=True, done=done)

    @staticmethod
    def _eye_legs(name, k):
        return [Frame(goal, speed, hold) for hold, speed, goal in eye_frames(name, k)]

    def tour(self, intensity, dwell=0.5):
        """7 个表情轮一遍，最后回 neutral 并放开，只留保持的舵机"""
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if intensity not in INTENSITIES:
                raise Refused("强度不对")
            active, legs = set(self.powered), []
            for name in list(EXPRESSIONS) + ["neutral"]:
                pose = self._pose(name, intensity, active)
                legs += [pose] + self._eye_legs(name, intensity)
                active |= set(pose)
            self._start(legs, additive=True, done=self._release_free, dwell=dwell)

    def _release_free(self):
        with self.lock:
            for board in list(self.links):
                kept = sorted(n for n in self.held if BY_NAME[n].board == board)
                self._ask(board, " ".join(["O"] + kept) if kept else "X")
            self.powered = set()
            self._record("cmd", board="all", cmd="放开，只留保持的舵机", reply="OK", angles=self.angles)

    def home(self):
        """已通电的舵机慢速回 90°。不用 O，O 是瞬跳"""
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if not self.powered:
                raise Refused("没有通电的舵机")
            # 一条 S 只能发给一块板，所以按组走
            self._start([{n: center(n) for n in g if n in self.powered} for _, g in GROUPS
                         if self.powered & set(g)])

    def swing(self, amp):
        """90 → +A → 90 → -A → 90。+ 是 config 里 a 到 b 的方向，所以成对舵机自动镜像；超范围的截断"""
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if amp not in SWING_AMPS:
                raise Refused(f"幅度只能是 {SWING_AMPS}")
            if not self.powered or not any(self.powered <= set(g) for _, g in GROUPS):
                raise Refused("先通电，只能是同一组的舵机")
            if len({"JL", "JR"} & self.powered) == 1:
                raise Refused("下巴要成对摆动")
            names = sorted(self.powered)
            if any(abs(self.angles[n] - center(n)) > 0.5 for n in names):
                raise Refused("先回中心")
            mid = {n: center(n) for n in names}
            legs = []
            for sign in (1, -1):
                goal = {n: clip(n, center(n) + sign * direction(n) * amp) for n in names}
                if goal != mid:
                    legs += [goal, mid]
            if not legs:
                raise Refused("这一组两边都没有行程")
            self._start(legs)

    def power(self, names):
        if set(names) == self.powered:
            return self.home()
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if not any(set(names) <= set(g) for _, g in GROUPS):
                raise Refused("只能通同一组里的舵机")
            board = BY_NAME[names[0]].board
            self.held -= set(names)
            kept = lambda b: sorted(n for n in self.held if BY_NAME[n].board == b)  # noqa: E731
            for other in self.links:
                if other != board:
                    # 保持的舵机都在 90，O 不会让它们动
                    self._ask(other, " ".join(["O"] + kept(other)) if kept(other) else "X")
            self._ask(board, f"V {SPEED}")
            line = "O " + " ".join(list(names) + kept(board))
            reply = self._ask(board, line)
            if reply != "OK":
                raise Refused(reply)
            self.powered = set(names)
            self.error = ""
            self._read(board)
            self._record("cmd", board=board, cmd=line, reply=reply, angles=self.angles)
            # O 只能到 90，有实测中心的再慢速走过去
            off = {n: center(n) for n in names if center(n) != 90}
            if off:
                self._start([off])

    def hold(self, names):
        """让这些舵机一直保持在 90°，不受通别的组影响。S 90 只是通电，跟踪值已是 90 就不动"""
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if len({BY_NAME[n].board for n in names}) != 1:
                raise Refused("一次只能保持同一块板的舵机")
            if any(abs(self.angles[n] - 90) > 0.5 for n in names):
                raise Refused("先回 90°")
            board = BY_NAME[names[0]].board
            line = "S " + " ".join(f"{n}=90" for n in names)
            reply = self._ask(board, line)
            if reply != "OK":
                raise Refused(reply)
            self.held |= set(names)
            self.powered -= set(names)
            self._record("cmd", board=board, cmd=line, reply=f"保持 {reply}", angles=self.angles)

    def set_center(self, name):
        """把当前角度存成这个舵机的实测中心"""
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if name not in self.powered:
                raise Refused(f"{name} 没通电")
            deg = self.angles[name]
            self.save_center(name, deg)
            self._record("note", servo=name, status="info", text=f"实测中心设为 {deg:g}°")

    def move(self, deltas):
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            off = [n for n in deltas if n not in self.powered]
            if off:
                raise Refused(f"{off} 还没通电")
            if any(abs(d) > MAX_STEP for d in deltas.values()):
                raise Refused(f"一步不能超过 {MAX_STEP}°")
            boards = {BY_NAME[n].board for n in deltas}
            if len(boards) != 1:
                raise Refused("一次只能动一块板")
            board = boards.pop()
            now = self._read(board)
            goal = {n: now[n] + d for n, d in deltas.items()}
            for n, v in goal.items():
                a = BY_NAME[n]
                if not min(a.a, a.b) <= v <= max(a.a, a.b):
                    raise Refused(f"{n}={v:g} 超出 config 范围 {min(a.a, a.b):g}–{max(a.a, a.b):g}")
            if {"JL", "JR"} & set(goal):
                jl, jr = goal.get("JL", now.get("JL")), goal.get("JR", now.get("JR"))
                if abs(jl + jr - 180) > JAW_SKEW:
                    raise Refused(f"下巴两侧偏差过大：JL={jl:g} JR={jr:g}，要成对动")
            self._ask(board, f"V {SPEED}")
            line = "S " + " ".join(f"{n}={v:g}" for n, v in goal.items())
            reply = self._ask(board, line)
            if reply != "OK":
                raise Refused(reply)
            time.sleep(self.settle)
            self._read(board)
            self._record("cmd", board=board, cmd=line, reply=reply, angles=self.angles)

    def track(self, on):
        """跟踪也是一个动作：跑着时别的按钮锁住，全部卸力能马上停"""
        if not on:
            return self._track_stop()
        with self.lock:
            if self._busy():
                raise Refused("上一个动作还没结束")
            if TRACK_SERVO not in self.powered:
                raise Refused(f"先给 {TRACK_SERVO} 通电")
            lim = load_verified(self.log_path).get(TRACK_SERVO)
            if lim is None:
                raise Refused(f"{TRACK_SERVO} 没有实测范围，先记录")
            try:
                params = self.vision("/params")["params"]
            except (OSError, ValueError, KeyError) as e:
                raise Refused(f"连不上视觉服务 {VISION_URL}，先启动 camera.web：{e}")
            self._ask(BY_NAME[TRACK_SERVO].board, f"V {SPEED}")
            self.stop.clear()
            self.tracking = {"face": False, "deg": self.angles[TRACK_SERVO], "lo": lim[0], "hi": lim[1]}
            self.job = threading.Thread(target=self._track_loop, daemon=True,
                                        args=(lim, params.get("gain", 1.0), params.get("hfov", 65.0)))
            self.job.start()

    def _track_stop(self):
        if self.tracking is None:
            raise Refused("视觉跟踪没开")
        self.stop.set()
        self.job.join(2)
        with self.lock:
            if TRACK_SERVO in self.powered:
                self._start([{TRACK_SERVO: center(TRACK_SERVO)}])

    def _track_loop(self, lim, gain, hfov):
        a = BY_NAME[TRACK_SERVO]
        lo, hi = lim
        deg = smooth = seen_lo = seen_hi = self.angles[TRACK_SERVO]
        home = min(hi, max(lo, center(TRACK_SERVO)))
        lost_at, fails = None, 0
        try:
            while not self.stop.wait(1 / TRACK_HZ):
                try:
                    v = self.vision("/state")
                    fails = 0
                except (OSError, ValueError) as e:
                    fails += 1
                    if fails >= 5:
                        raise Refused(f"视觉服务断开，跟踪已停止：{e}")
                    continue
                face = bool(v.get("face")) and v.get("x") is not None
                if face:
                    lost_at = None
                    goal = a.angle(gaze_to_u(v["x"], 0, gain, hfov)[0])
                else:
                    lost_at = lost_at or time.monotonic()
                    goal = home if time.monotonic() - lost_at > TRACK_LOST else smooth
                smooth += TRACK_ALPHA * (min(hi, max(lo, goal)) - smooth)
                if abs(smooth - deg) >= TRACK_DEADBAND:
                    deg = round(deg + max(-TRACK_STEP, min(TRACK_STEP, smooth - deg)), 1)
                    with self.lock:
                        if self.stop.is_set():
                            break
                        reply = self._ask(a.board, f"S {TRACK_SERVO}={deg:g}")
                        if reply != "OK":
                            raise Refused(reply)
                        self.angles[TRACK_SERVO] = deg
                    seen_lo, seen_hi = min(seen_lo, deg), max(seen_hi, deg)
                self.tracking = {**self.tracking, "face": face, "deg": deg}
        except Refused as e:
            self.error = str(e)
        finally:
            self.tracking = None
            # 10Hz 的命令不逐条写日志，只记走过的范围
            self._record("note", servo=TRACK_SERVO, status="info", text=f"视觉跟踪结束，走过 {seen_lo:g}~{seen_hi:g}°")

    def relax(self):
        # 一块板失败也要继续卸其他板
        self.stop.set()
        with self.lock:
            errors = []
            for board in list(self.links):
                try:
                    self._ask(board, "X")
                except Refused as e:
                    errors.append(str(e))
            self.powered = set()
            self.held = set()
            self.script = None
            self._record("cmd", board="all", cmd="X", reply="; ".join(errors) or "OK", angles=self.angles)
            if errors:
                raise Refused("; ".join(errors))

    def note(self, servos, status, text):
        if status not in ("ok", "bad", "info"):
            raise Refused("状态不对")
        for s in servos:
            self._record("note", servo=s, status=status, text=text)

    def set_range(self, servo, lo, hi):
        if lo >= hi:
            raise Refused("下限要小于上限")
        self._record("range", servo=servo, lo=lo, hi=hi)

    def pose(self, name, text):
        if not self.powered:
            raise Refused("没有通电的舵机，没有可记录的姿态")
        kvs = " ".join(f"{n}={self.angles[n]:g}" for n in sorted(self.powered))
        self._record("recipe", name=name, text=text, steps=[f"S {kvs}"])

    def state(self):
        return {
            "groups": [{"label": label, "names": names} for label, names in GROUPS],
            "limits": {n: [min(a.a, a.b), max(a.a, a.b)] for n, a in BY_NAME.items()},
            "angles": self.angles,
            "powered": sorted(self.powered),
            "held": sorted(self.held),
            "script": self.script,
            "expressions": list(EXPRESSIONS),
            "centers": {n: center(n) for n in BY_NAME},
            "boards": sorted(self.links),
            "dirs": {n: direction(n) for n in BY_NAME},
            "busy": self._busy(),
            "tracking": self.tracking,
            "error": self.error,
        }


PAGE = r"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>舵机调试台</title><style>
:root{--bg:#f7f6f2;--card:#fff;--ink:#1f2328;--dim:#667;--line:#e2e0d8;--ok:#1a7f4b;--bad:#c0392b;--on:#b7791f}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--card:#1f2228;--ink:#e8e8e6;--dim:#99a;--line:#33363d;--ok:#4cc38a;--bad:#ff7b6b;--on:#e0a84a}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.5 -apple-system,"PingFang SC",sans-serif}
header{position:sticky;top:0;z-index:2;background:var(--bg);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;gap:12px;align-items:center;flex-wrap:wrap}
h1{font-size:18px;margin:0}main{max-width:760px;margin:0 auto;padding:12px 16px 60px}
#stop{margin-left:auto;background:var(--bad);color:#fff;border:0;border-radius:8px;padding:12px 22px;font-size:16px;font-weight:700;cursor:pointer}
#msg{min-height:22px;color:var(--bad);padding:6px 0}#alarm:not(:empty){background:var(--bad);color:#fff;border-radius:8px;padding:10px 12px;font-weight:600;margin-top:8px}.dim{color:var(--dim);font-size:13px}
.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px;margin:10px 0}.card.on{border-color:var(--on)}
.head{display:flex;justify-content:space-between;align-items:center;gap:8px}
.s{display:flex;align-items:center;gap:6px;flex-wrap:wrap;padding:6px 0}.s code{width:44px;font-weight:700}.deg{width:58px;font-variant-numeric:tabular-nums}
button{font:inherit;padding:6px 10px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink);cursor:pointer}
button:disabled{opacity:.4;cursor:default}input,select{font:inherit;padding:5px 8px;border:1px solid var(--line);border-radius:6px;background:var(--bg);color:var(--ink)}
input.w{width:72px}.st{padding:3px 0;font-size:14px}.st.done{color:var(--dim)}.st.now{font-weight:700}.new{color:var(--on)}.f{display:flex;gap:6px;flex-wrap:wrap;align-items:center;padding-top:8px}.f input.t{flex:1;min-width:180px}
</style></head><body>
<header><h1>舵机调试台</h1><span class="dim" id="st"></span><button id="stop">全部卸力 (Esc)</button></header>
<main><div id="alarm"></div><div id="msg"></div>
<div class="card"><b>表情</b><div class="dim">一组一组走。每步停下看，顶住或嗡嗡响就按 Esc。标“新角度”的是这次还没走过的</div>
<div class="f"><select id="en"></select><select id="ek"><option value="0.3">强度 0.3</option><option value="0.6">强度 0.6</option><option value="1">强度 1.0</option></select>
<button id="eb">准备</button><button id="ex">下一步</button><button id="ea">走完剩下的</button><button id="eg">一起做</button><button id="et">全部轮播</button></div><div id="es"></div></div>
<div class="card"><b>视觉跟踪</b><div class="dim">摄像头看到人脸时眼球左右（LR）跟着转，需要 camera.web 在运行。顶住或嗡嗡响就按 Esc</div>
<div class="f"><button id="tk">开启视觉跟踪</button><span class="dim" id="tks"></span></div></div>
<div id="list"></div>
<div class="card"><b>记录当前姿态</b><div class="dim">把通电舵机的当前角度存成一个能复现的动作</div>
<div class="f"><input id="pn" placeholder="名字，如 张嘴"><input id="pt" class="t" placeholder="说明"><button id="ps">保存姿态</button></div></div>
</main><script>
let S=null,drawn=false;
const $=i=>document.getElementById(i);
async function api(body){
  const r=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-Head':'1'},body:JSON.stringify(body)});
  const d=await r.json();$('msg').textContent=d.error||'';if(d.state){S=d.state;render()}return d}
function draw(){
  $('list').innerHTML=S.groups.map((g,i)=>`<div class="card" id="g${i}"><div class="head"><b>${i+1}. ${g.label}</b>
  <button data-power="${i}">只通这组到 90°</button></div>
  <div class="f"><button data-home="${i}">回中心</button><button data-hold="${i}">保持在 90°</button><button data-sw="${i}" data-amp="15">摆动 ±15</button><button data-sw="${i}" data-amp="30">摆动 ±30</button></div>
  ${g.names.map(n=>`<div class="s"><code>${n}</code><span class="deg" id="a${n}"></span>
    <button data-solo="${n}">只通它</button><button data-center="${n}">设为中心</button><span class="dim" id="c${n}"></span>
    ${[-5,-1,1,5].map(d=>`<button data-m="${n}" data-d="${d}">${d>0?'+':''}${d}</button>`).join('')}
    <span class="dim">config ${S.limits[n][0]}–${S.limits[n][1]}</span></div>`).join('')}
  ${g.names.length==2?`<div class="s"><span class="dim">成对</span>${[[5,-5],[1,-1],[-1,1],[-5,5]].map(p=>`<button data-pair="${i}" data-a="${p[0]}" data-b="${p[1]}">${g.names[0]} ${p[0]>0?'+':''}${p[0]} / ${g.names[1]} ${p[1]>0?'+':''}${p[1]}</button>`).join('')}</div>`:''}
  <div class="f"><select id="ns${i}">${g.names.length>1?`<option value="${g.names.join(',')}">整组</option>`:''}${g.names.map(n=>`<option>${n}</option>`).join('')}</select>
    <input class="t" id="nt${i}" placeholder="现象：方向、声音、顶住的位置">
    <button data-note="${i}" data-s="ok">通过</button><button data-note="${i}" data-s="bad">有问题</button><button data-note="${i}" data-s="info">记一下</button></div>
  <div class="f"><span class="dim">实测范围</span>${g.names.map(n=>`<code>${n}</code><input class="w" id="lo${n}" value="${S.limits[n][0]}"><input class="w" id="hi${n}" value="${S.limits[n][1]}"><button data-range="${n}">保存</button>`).join('')}</div></div>`).join('');
  drawn=true}
function render(){
  if(!drawn)draw();
  $('st').textContent=`在线: ${S.boards.join(' ')||'无'} · 通电: ${S.powered.join(' ')||'无'} · 保持: ${S.held.join(' ')||'无'}${S.busy?' · 动作中':''}`;
  $('alarm').textContent=S.error||'';
  const T=S.tracking;$('tk').textContent=T?'关闭视觉跟踪':'开启视觉跟踪';$('tk').disabled=S.busy&&!T;
  $('tks').textContent=T?`${T.face?'看到人脸':'没看到人脸'} · LR ${T.deg}° · 范围 ${T.lo}–${T.hi}°`:'';
  if(!$('en').options.length)$('en').innerHTML=S.expressions.map(n=>`<option>${n}</option>`).join('');
  const sc=S.script,html=sc?sc.steps.map((s,i)=>`<div class="st ${i<sc.i?'done':i==sc.i?'now':''}">${i+1}. ${s.label}：${Object.entries(s.goal).map(([n,v])=>`${n} ${v}°`).join('，')}${s.new.length?` <span class="new">新角度 ${s.new.join(' ')}</span>`:''}</div>`).join(''):'';
  if($('es').dataset.h!==html){$('es').innerHTML=html;$('es').dataset.h=html}
  $('ex').disabled=$('ea').disabled=S.busy||!sc||sc.i>=sc.steps.length;$('eb').disabled=$('eg').disabled=$('et').disabled=S.busy;
  S.groups.forEach((g,i)=>{$('g'+i).classList.toggle('on',g.names.some(n=>S.powered.includes(n)));
    g.names.forEach(n=>{$('a'+n).textContent=(S.angles[n]??'?')+'°';$('c'+n).textContent=S.centers[n]!=90?`中心 ${S.centers[n]}°`:''})});
  document.querySelectorAll('[data-m]').forEach(b=>b.disabled=S.busy||!S.powered.includes(b.dataset.m));
  const whole=i=>S.groups[i].names.every(n=>S.powered.includes(n)),some=i=>S.groups[i].names.some(n=>S.powered.includes(n));
  document.querySelectorAll('[data-pair]').forEach(b=>b.disabled=S.busy||!whole(b.dataset.pair));
  document.querySelectorAll('[data-home]').forEach(b=>b.disabled=S.busy||!some(b.dataset.home));
  document.querySelectorAll('[data-sw]').forEach(b=>b.disabled=S.busy||!some(b.dataset.sw));
  document.querySelectorAll('[data-hold]').forEach(b=>b.disabled=S.busy||!some(b.dataset.hold));
  document.querySelectorAll('[data-center]').forEach(b=>b.disabled=S.busy||!S.powered.includes(b.dataset.center));
  document.querySelectorAll('[data-power],[data-solo]').forEach(b=>b.disabled=S.busy)}
function plan(g,amp){return g.names.filter(n=>S.powered.includes(n)).map(n=>{const[l,h]=S.limits[n],c=v=>Math.min(h,Math.max(l,v)),d=S.dirs[n];m=S.centers[n];return `${n}: ${c(m+d*amp)} → ${m} → ${c(m-d*amp)} → ${m}`}).join('\n')}
document.addEventListener('click',e=>{const d=e.target.dataset;if(!d)return;
  if(d.power!==undefined){const g=S.groups[d.power];
    if(confirm(`只给 ${g.names.join(' ')} 通电到 90°，其他全部卸力。\n第一次通电会全速转到 90°，先用手把它推到 90 附近。继续？`))api({op:'power',names:g.names})}
  if(d.solo){if(confirm(`只给 ${d.solo} 通电到 90°，其他全部卸力。继续？`))api({op:'power',names:[d.solo]})}
  if(d.home!==undefined)api({op:'home'});
  if(d.hold!==undefined)api({op:'hold',names:S.groups[d.hold].names.filter(n=>S.powered.includes(n))});
  if(d.center){if(confirm(`把 ${d.center} 的中心设为 ${S.angles[d.center]}°？之后回中心、摆动、表情都按它算。`))api({op:'set_center',name:d.center})}
  if(d.sw!==undefined){if(confirm(`摆动 ±${d.amp}，超出 config 的部分已截断：\n${plan(S.groups[d.sw],+d.amp)}\n顶住或嗡嗡响就按 Esc。继续？`))api({op:'swing',amp:+d.amp})}
  if(d.m)api({op:'move',deltas:{[d.m]:+d.d}});
  if(d.pair!==undefined){const n=S.groups[d.pair].names;api({op:'move',deltas:{[n[0]]:+d.a,[n[1]]:+d.b}})}
  if(d.note!==undefined){const t=$('nt'+d.note);if(!t.value.trim()){$('msg').textContent='先写现象';return}
    api({op:'note',servos:$('ns'+d.note).value.split(','),status:d.s,text:t.value}).then(r=>{if(!r.error)t.value=''})}
  if(d.range)api({op:'range',servo:d.range,lo:+$('lo'+d.range).value,hi:+$('hi'+d.range).value})});
$('eb').onclick=()=>api({op:'expr',name:$('en').value,intensity:+$('ek').value});
$('ex').onclick=()=>api({op:'expr_next'});
$('eg').onclick=()=>api({op:'expr_go',name:$('en').value,intensity:+$('ek').value});
$('et').onclick=()=>api({op:'tour',intensity:+$('ek').value});
$('ea').onclick=()=>{if(confirm('剩下的组会依次自动走，每组之间不再等你确认。继续？'))api({op:'expr_all'})};
$('stop').onclick=()=>api({op:'relax'});
$('tk').onclick=async()=>{if(S.tracking)return api({op:'track',on:false});
  if(!S.powered.includes('LR')){if(!confirm('只给 LR 通电到 90°，其他卸力，保持的舵机不变。继续？'))return;
    if((await api({op:'power',names:['LR']})).error)return;await new Promise(f=>setTimeout(f,1000))}
  api({op:'track',on:true})};
document.addEventListener('keydown',e=>{if(e.key==='Escape')api({op:'relax'})});
$('ps').onclick=()=>{if(!$('pn').value.trim()){$('msg').textContent='先写名字';return}api({op:'pose',name:$('pn').value,text:$('pt').value})};
api({op:'state'});
setInterval(async()=>{try{const r=await fetch('/api',{method:'POST',headers:{'Content-Type':'application/json','X-Head':'1'},body:'{"op":"state"}'});S=(await r.json()).state;render()}catch(e){$('alarm').textContent='连不上调试台。要停舵机就断 5V'}},1000);
</script></body></html>"""


def make_handler(bench):
    class Handler(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def _send(self, code, body, ctype):
            self.send_response(code)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            self._send(200, PAGE.encode(), "text/html; charset=utf-8")

        def do_POST(self):
            # 自定义头让别的网页没法跨站发命令
            if self.path != "/api" or self.headers.get("X-Head") != "1":
                return self._send(403, b"{}", "application/json")
            req = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            out = {}
            try:
                op = req.pop("op")
                if op != "state":
                    {"power": bench.power, "move": bench.move, "relax": bench.relax, "note": bench.note,
                     "range": bench.set_range, "pose": bench.pose, "home": bench.home, "swing": bench.swing, "hold": bench.hold,
                     "expr": bench.expr, "expr_next": bench.expr_next, "expr_all": bench.expr_all,
                     "expr_go": bench.expr_go, "tour": bench.tour,
                     "set_center": bench.set_center, "track": bench.track}[op](**req)
            except Refused as e:
                out["error"] = str(e)
            out["state"] = bench.state()
            self._send(200, json.dumps(out, ensure_ascii=False).encode(), "application/json")

    return Handler


if __name__ == "__main__":
    bench = Bench(discover(), rediscover=discover)
    print("在线:", sorted(bench.links), flush=True)

    def heartbeat():
        while True:
            time.sleep(1)
            try:
                bench.beat()
            except Exception as e:
                bench.error = f"心跳出错：{e}"

    threading.Thread(target=heartbeat, daemon=True).start()
    ThreadingHTTPServer(("127.0.0.1", PORT), make_handler(bench)).serve_forever()
