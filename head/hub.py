"""统一控制进程的核心：唯一持有三块 Pico 串口，别的程序只提交意图。

    视觉 / T5 / 网页  --意图-->  Mixer（按优先级合成） --> 安全过滤 --> 每块板一个发送线程

优先级从低到高：待机 < 距离情绪 < 对话情绪 < 嘴型 < 手动 < 眨眼。高优先级只覆盖它写到的舵机，
所以眨眼时眼球和嘴还能继续动。意图都带存活时间，来源崩了会自动过期，脸回到下一层。

真机保护：
  - 只驱动 tune_log 里有实测范围的舵机，没标定的不发信号（--allow-unverified 才放开）
  - EXA 备用口永不驱动；下巴 JL/JR 总是成对，JL+JR=180，只标定一侧时两侧都不动
  - 连接时要求固件支持 W 失联保护，这个进程死掉时板子自己回 rest 再卸力
  - 任何一块板不回话或报错，全部卸力并锁定，要人看过之后重新连接（板子可能掉电重启过）
"""
from __future__ import annotations

import fcntl
import glob
import json
import math
import os
import random
import sys
import termios
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import numpy as np

from .actuators import ACTUATORS, BY_NAME, NAMES, rest_vector
from .client import pico_ports

ROOT = Path(__file__).resolve().parent.parent
TUNE_LOG = ROOT / "outputs" / "tune_log.jsonl"

PRIORITY = {"idle": 10, "vision": 20, "dialog": 30, "lips": 40, "manual": 45, "reflex": 50}
EXTERNAL_SOURCES = ("vision", "dialog", "lips", "manual")   # reflex 由待机动作每拍改写，不对外开放
MAX_TTL = 3600.0
NEVER_DRIVE = {"EXA"}
HOLD = {"LLL": 90.0, "LLR": 90.0}   # 下唇先固定在 90，不跟表情动
LIDS = ("TL", "TR", "BL", "BR")

WATCHDOG_MS = 1000
SEND_HZ = 25
HEARTBEAT_S = 0.25
RAMP_SPEED = 60       # 刚连接时慢速走到第一个姿态
RAMP_S = 3.0
MIN_STEP_DEG = 0.3    # 变化小于这个不发，减少串口量和舵机抖动
MAX_MISSES = 2
LOOP_STALL_S = 0.5

# u 每秒最多变化多少：眼皮最快，眼球其次，其余慢一些，和固件限速是两层
SLEW = {**{n: 30.0 for n in LIDS}, "LR": 8.0, "UD": 8.0}
SLEW_DEFAULT = 8.0


class Refused(Exception):
    """操作被拒绝，消息直接显示给用户。"""


def load_verified(path=TUNE_LOG):
    """tune_log 里每个舵机最后一次实测范围，和 config 范围取交集。"""
    limits = {}
    try:
        lines = Path(path).read_text().splitlines()
    except FileNotFoundError:
        return limits
    for line in lines:
        try:
            e = json.loads(line)
        except ValueError:
            continue
        a = BY_NAME.get(e.get("servo"))
        if e.get("type") != "range" or a is None:
            continue
        lo, hi = max(e["lo"], min(a.a, a.b)), min(e["hi"], max(a.a, a.b))
        if lo < hi:
            limits[a.name] = (lo, hi)
    return limits


def ports_held(paths):
    """Linux：列出已被别的进程打开的串口。只能看到有权限读的进程，所以只是提前提醒，不是保证。"""
    real = {os.path.realpath(p): p for p in paths}
    held = []
    for fd_dir in glob.glob("/proc/[0-9]*/fd"):
        pid = fd_dir.split("/")[2]
        if pid == str(os.getpid()):
            continue
        try:
            fds = os.listdir(fd_dir)
        except OSError:
            continue
        for fd in fds:
            try:
                target = os.readlink(f"{fd_dir}/{fd}")
            except OSError:
                continue
            if target in real:
                held.append(real[target])
    return sorted(set(held))


def open_links(baud=115200):
    """打开并独占三块 Pico。TIOCEXCL 让之后别的程序（tune_server 等）打不开同一个串口。"""
    import serial

    ports = pico_ports()
    held = ports_held(ports) if sys.platform == "linux" else []
    if held:
        raise Refused(f"串口正被别的程序占用，先关掉调试台等程序：{held}")
    links = {}
    try:
        for p in ports:
            s = serial.Serial(p, baud, timeout=0.3, exclusive=True)
            fcntl.ioctl(s.fileno(), termios.TIOCEXCL)
            time.sleep(0.1)
            s.reset_input_buffer()
            s.write(b"?\n")
            for _ in range(5):
                line = s.readline().decode(errors="ignore").strip()
                if line.startswith("ROLE "):
                    links[line.split()[1]] = s
                    break
            else:
                s.close()
    except Exception as e:
        for s in links.values():
            s.close()
        raise Refused(f"打开串口失败：{e}") from e
    return links


@dataclass
class Layer:
    values: dict
    expires: float | None


class Mixer:
    def __init__(self):
        self.rest = rest_vector()
        self.layers = {}
        self.lock = threading.Lock()

    def set(self, source, values, ttl, now, merge=False):
        if source not in PRIORITY:
            raise Refused(f"没有这个来源：{source}")
        clean = {}
        for n, x in values.items():
            if n not in BY_NAME:
                raise Refused(f"没有这个舵机：{n}")
            x = float(x)
            if not math.isfinite(x):
                raise Refused(f"{n} 的值不是有效数字")
            clean[n] = min(1.0, max(0.0, x))
        if ttl is not None:
            ttl = float(ttl)
            if not 0 < ttl <= MAX_TTL:
                raise Refused("ttl 超出范围")
        expires = None if ttl is None else now + ttl
        with self.lock:
            old = self.layers.get(source)
            if merge and old:
                clean = {**old.values, **clean}
            self.layers[source] = Layer(clean, expires)

    def clear(self, source):
        with self.lock:
            self.layers.pop(source, None)

    def compose(self, now):
        v = self.rest.copy()
        with self.lock:
            for src in [s for s, l in self.layers.items() if l.expires is not None and l.expires <= now]:
                del self.layers[src]
            order = sorted(self.layers, key=PRIORITY.get)
            for src in order:
                for n, x in self.layers[src].values.items():
                    v[NAMES.index(n)] = x
        return v, order


class Life:
    """待机动作：缓慢换视线、微扫视、眨眼，大幅转眼时顺带眨一下。思路来自 Will Cogley RobotHead 的 autonomy.py。"""
    CLOSE_S, HOLD_S, OPEN_S = 0.06, 0.03, 0.18

    def __init__(self, seed=None):
        self.rng = random.Random(seed)
        self.focus = (0.5, rest_vector()[NAMES.index("UD")])
        self.micro = (0.0, 0.0)
        self.next_focus = self.next_micro = 0.0
        self.next_blink = 2.0
        self.blink_at = None

    def _blink(self, now):
        self.blink_at = now
        self.next_blink = now + self.rng.uniform(2.0, 6.0)

    def update(self, now):
        r = self.rng
        if now >= self.next_focus:
            old = self.focus
            ud = rest_vector()[NAMES.index("UD")]   # 正前方带装配补偿，不一定是 0.5
            self.focus = (r.uniform(0.35, 0.65), ud + r.uniform(-0.08, 0.08))
            self.next_focus = now + r.uniform(2.0, 5.0)
            if abs(self.focus[0] - old[0]) + abs(self.focus[1] - old[1]) > 0.2 and self.blink_at is None:
                self._blink(now)
        if now >= self.next_micro:
            self.micro = (r.uniform(-0.015, 0.015), r.uniform(-0.015, 0.015))
            self.next_micro = now + r.uniform(0.6, 1.5)
        if now >= self.next_blink and self.blink_at is None:
            self._blink(now)
        gaze = {"LR": self.focus[0] + self.micro[0], "UD": self.focus[1] + self.micro[1]}
        return gaze, self._lids(now)

    def _lids(self, now):
        if self.blink_at is None:
            return None
        t = now - self.blink_at
        if t < self.CLOSE_S:
            k = 1 - t / self.CLOSE_S
        elif t < self.CLOSE_S + self.HOLD_S:
            k = 0.0
        elif t < self.CLOSE_S + self.HOLD_S + self.OPEN_S:
            k = (t - self.CLOSE_S - self.HOLD_S) / self.OPEN_S
        else:
            self.blink_at = None
            return None
        rest = rest_vector()
        return {n: k * rest[NAMES.index(n)] for n in LIDS}


class BoardWorker(threading.Thread):
    """一块板一个线程：只发最新目标，一块板卡住不影响控制循环。"""

    def __init__(self, board, link, hub):
        super().__init__(daemon=True, name=f"board-{board}")
        self.board, self.link, self.hub = board, link, hub
        self.lock = threading.Lock()
        self.halt = threading.Event()
        self.sent = {}
        self.last_beat = 0.0
        self.misses = 0
        self.speed_set = False

    def ask(self, line):
        with self.lock:
            self.link.write((line + "\n").encode())
            return self.link.readline().decode(errors="ignore").strip()

    def _checked(self, line):
        try:
            reply = self.ask(line)
        except Exception as e:  # noqa: BLE001
            self.hub.fault(f"{self.board} 板串口断开：{e}")
            return False
        if reply == "OK":
            self.misses = 0
            return True
        if reply:
            self.hub.fault(f"{self.board} 板回复异常：{reply}")
            return False
        self.misses += 1
        if self.misses >= MAX_MISSES:
            self.hub.fault(f"{self.board} 板没有回应")
            return False
        if hasattr(self.link, "reset_input_buffer"):
            self.link.reset_input_buffer()
        return True

    def cycle(self, now):
        # 控制循环卡住时不能继续喂看门狗，否则舵机会一直保持最后的姿态
        if self.hub.last is None or now - self.hub.last > LOOP_STALL_S:
            self.hub.fault("控制循环卡住")
            return
        if not self.speed_set and now - self.hub.armed_at >= RAMP_S:
            self.speed_set = self._checked(f"V {self.hub.speed:g}")
        if now - self.last_beat >= HEARTBEAT_S:
            self.last_beat = now
            if not self._checked(f"W {WATCHDOG_MS}"):
                return
        want = self.hub.board_angles(self.board)
        diff = {n: d for n, d in want.items() if n not in self.sent or abs(d - self.sent[n]) >= MIN_STEP_DEG}
        if diff and self._checked("S " + " ".join(f"{n}={d:.1f}" for n, d in diff.items())):
            self.sent.update(diff)

    def run(self):
        period = 1 / SEND_HZ
        while not self.halt.is_set():
            start = self.hub.clock()
            self.cycle(start)
            self.halt.wait(max(0.0, period - (self.hub.clock() - start)))

    def shutdown(self):
        """停线程、关保护、卸力、关串口。这里失败也要继续，别的板还得卸。"""
        self.halt.set()
        if self.is_alive() and threading.current_thread() is not self:
            self.join(1.0)
        for line in ("X", "W 0"):
            try:
                self.ask(line)
            except Exception:  # noqa: BLE001
                pass
        try:
            self.link.close()
        except Exception:  # noqa: BLE001
            pass


class Hub:
    def __init__(self, opener=open_links, limits=None, allow_unverified=False, speed=300, hz=50,
                 clock=time.monotonic, seed=None):
        self.opener, self.allow_unverified, self.speed, self.hz, self.clock = opener, allow_unverified, speed, hz, clock
        self.limits = load_verified() if limits is None else limits
        self.mixer = Mixer()
        self.life = Life(seed)
        self.life_on = True
        self.rest = rest_vector()
        self.v = self.rest.copy()
        self.angles = {}
        self.order = []
        self.lock = threading.Lock()
        self.hw_lock = threading.Lock()
        self.workers = {}
        self.armed_at = 0.0
        self.fault_msg = ""
        self.pending_fault = False
        self.last = None
        self.loop_hz = 0.0
        self.halt = threading.Event()

    # ---- 意图 ----
    def intent(self, source, values, ttl=1.0, merge=False):
        if source not in EXTERNAL_SOURCES:
            raise Refused(f"不接受这个来源：{source}")
        self.mixer.set(source, values, ttl, self.clock(), merge)

    def clear(self, source):
        if source not in EXTERNAL_SOURCES:
            raise Refused(f"不接受这个来源：{source}")
        self.mixer.clear(source)

    def set_life(self, on):
        self.life_on = bool(on)
        if not on:
            self.mixer.clear("idle")
            self.mixer.clear("reflex")

    # ---- 安全过滤 ----
    def commands(self, v):
        out = {}
        for a in ACTUATORS:
            if a.name in NEVER_DRIVE:
                continue
            lim = self.limits.get(a.name)
            if self.allow_unverified:   # 放开后以 config 为准，旧的实测范围比现在的行程窄
                lim = (min(a.a, a.b), max(a.a, a.b))
            elif lim is None:
                continue
            if a.name in HOLD:
                out[a.name] = HOLD[a.name]
                continue
            out[a.name] = min(lim[1], max(lim[0], a.angle(v[NAMES.index(a.name)])))
        if "JL" in out and "JR" in out:
            opening = max(0.0, min(90 - out["JL"], out["JR"] - 90))
            out["JL"], out["JR"] = 90 - opening, 90 + opening
        else:
            out.pop("JL", None)
            out.pop("JR", None)
        return out

    def drivable(self):
        return sorted(self.commands(self.rest))

    def board_angles(self, board):
        with self.lock:
            return {n: d for n, d in self.angles.items() if BY_NAME[n].board == board}

    # ---- 控制循环 ----
    def step(self, now=None):
        now = self.clock() if now is None else now
        dt = 0.0 if self.last is None else now - self.last
        self.last = now
        if self.life_on:
            gaze, lids = self.life.update(now)
            self.mixer.set("idle", gaze, None, now)
            if lids is None:
                self.mixer.clear("reflex")
            else:
                self.mixer.set("reflex", lids, None, now)
        target, order = self.mixer.compose(now)
        for i, n in enumerate(NAMES):
            limit = SLEW.get(n, SLEW_DEFAULT) * dt
            self.v[i] += min(limit, max(-limit, target[i] - self.v[i]))
        cmds = self.commands(self.v)
        with self.lock:
            self.angles, self.order = cmds, order
        if self.pending_fault:
            self.pending_fault = False
            self.release()
        return self.v

    def run(self):
        period = 1 / self.hz
        deadline = self.clock()
        while not self.halt.is_set():
            start = self.clock()
            self.step(start)
            deadline = max(deadline + period, self.clock())   # 按绝对时间排，等待误差不累积
            self.halt.wait(max(0.0, deadline - self.clock()))
            self.loop_hz = 0.9 * self.loop_hz + 0.1 / max(self.clock() - start, 1e-4)

    # ---- 真机 ----
    def arm(self, start_threads=True):
        with self.hw_lock:
            if self.workers:
                return
            names = self.drivable()
            if not names:
                raise Refused("还没有标定过的舵机。先在调试台记录实测范围，下巴要 JL、JR 都测完")
            links = self.opener()
            boards = {BY_NAME[n].board for n in names}
            missing = boards - set(links)
            workers = {}
            try:
                if missing:
                    raise Refused(f"没找到这些板：{sorted(missing)}")
                for board in links:
                    if board not in boards:
                        links[board].close()
                        continue
                    w = BoardWorker(board, links[board], self)
                    workers[board] = w
                    if w.ask(f"W {WATCHDOG_MS}") != "OK":
                        raise Refused(f"{board} 板固件没有失联保护，先重刷 firmware/main.py")
                    if w.ask(f"V {RAMP_SPEED}") != "OK":
                        raise Refused(f"{board} 板设置速度失败")
            except Exception as e:
                for w in workers.values():
                    w.shutdown()
                for board, link in links.items():
                    if board in boards and board not in workers:
                        link.close()
                if isinstance(e, Refused):
                    raise
                raise Refused(f"连接失败：{e}") from e
            self.fault_msg = ""
            self.armed_at = self.clock()
            self.workers = workers
            if start_threads:
                for w in workers.values():
                    w.start()

    def release(self, reason=None):
        with self.hw_lock:
            workers, self.workers = self.workers, {}
        for w in workers.values():
            w.shutdown()
        if reason:
            self.fault_msg = reason

    def fault(self, reason):
        """发送线程里调用：记下原因，下一拍由控制循环卸力，避免线程等自己。"""
        if not self.fault_msg:
            self.fault_msg = reason
        for w in list(self.workers.values()):
            w.halt.set()
        self.pending_fault = True

    def state(self):
        with self.lock:
            angles, order = dict(self.angles), list(self.order)
        return {
            "u": dict(zip(NAMES, (round(float(x), 4) for x in self.v))),
            "angles": {n: round(d, 1) for n, d in angles.items()},
            "layers": order,
            "armed": sorted(self.workers),
            "fault": self.fault_msg,
            "life": self.life_on,
            "hz": round(self.loop_hz, 1),
        }

    def stop(self):
        self.halt.set()
        self.release()
