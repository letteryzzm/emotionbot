"""模拟 T5 板子（只用于测试和演示网页，画面是画出来的假屏幕，不是真实板子的显示）。

在伪终端上说 EB1 文本命令和 EB2 屏幕回传，电脑端用 T5Stream 连伪终端的路径就行。
    PING / EMOTION <name> / SCREEN START [fps] [scale] / SCREEN SNAP / SCREEN STOP
screen=False 时对 SCREEN 命令回 ERR command，模拟现有固件。
"""
from __future__ import annotations

import os
import re
import select
import struct
import threading
import time
import tty

import numpy as np

from . import t5_eb2 as eb

W = H = 240
BG, SKIN, WHITE, IRIS, PUPIL, LIPS = (20, 24, 36), (36, 44, 66), (238, 246, 247), (20, 200, 200), (10, 14, 26), (255, 106, 61)

# (眼高, 上眼皮下压, 眉内端 y, 眉外端 y, 嘴的折线点)，坐标是 100x100 的比例
FACES = {
    "neutral": (8, 0, 25, 25, [(36, 74), (64, 74)]),
    "happy": (7, 2, 22, 24, "q 30,68 50,90 70,68"),
    "sad": (7, 3, 19, 28, "q 34,80 50,66 66,80"),
    "angry": (9, 2, 33, 20, [(36, 77), (64, 77)]),
    "surprise": (11, 0, 16, 16, "o"),
    "fear": (11, 0, 17, 22, [(30, 76), (40, 70), (50, 76), (60, 70), (70, 76)]),
    "disgust": (6, 3, 30, 24, [(34, 78), (44, 68), (54, 76), (62, 70), (68, 72)]),
}


def _disk(img, cx, cy, rx, ry, col):
    yy, xx = np.ogrid[:H, :W]
    img[((xx - cx) / rx) ** 2 + ((yy - cy) / ry) ** 2 <= 1] = col


def _seg(img, p, q, th, col):
    yy, xx = np.mgrid[:H, :W]
    dx, dy = q[0] - p[0], q[1] - p[1]
    t = np.clip(((xx - p[0]) * dx + (yy - p[1]) * dy) / (dx * dx + dy * dy + 1e-9), 0, 1)
    img[np.hypot(xx - (p[0] + t * dx), yy - (p[1] + t * dy)) <= th / 2] = col


def render(emotion, blink=False):
    """返回 (H, W) 的 RGB565 数组（uint16）"""
    eye, lid, bi, bo, mouth = FACES[emotion]
    k = W / 100
    img = np.empty((H, W, 3), np.uint8)
    img[:] = SKIN
    for s in (-1, 1):
        cx = (50 + s * 19) * k
        ry = max(eye * k * (0.12 if blink else 1), 2)
        _disk(img, cx, 42 * k, 11 * k, ry, WHITE)
        if not blink:
            _disk(img, cx, 42 * k, min(5.6, eye) * k, min(5.6, eye) * k, IRIS)
            _disk(img, cx, 42 * k, min(2.6, eye) * k, min(2.6, eye) * k, PUPIL)
            if lid:
                img[int((42 - eye - 1) * k):int((42 - eye + lid) * k), int(cx - 12 * k):int(cx + 12 * k)] = SKIN
        _seg(img, ((50 + s * 8) * k, bi * k), ((50 + s * 33) * k, bo * k), 4.4 * k, WHITE)
    if mouth == "o":
        _disk(img, 50 * k, 77 * k, 9 * k, 11 * k, LIPS)
        _disk(img, 50 * k, 77 * k, 5 * k, 7 * k, PUPIL)
    else:
        if isinstance(mouth, str):
            (x0, y0), (x1, y1), (x2, y2) = [tuple(map(float, p.split(","))) for p in mouth.split()[1:]]
            mouth = [((1 - t) ** 2 * x0 + 2 * t * (1 - t) * x1 + t * t * x2, (1 - t) ** 2 * y0 + 2 * t * (1 - t) * y1 + t * t * y2)
                     for t in np.linspace(0, 1, 14)]
        for a, b in zip(mouth, mouth[1:]):
            _seg(img, (a[0] * k, a[1] * k), (b[0] * k, b[1] * k), 4.6 * k, LIPS)
    r, g, b = (img[..., i].astype(np.uint16) for i in range(3))
    return ((r >> 3) << 11) | ((g >> 2) << 5) | (b >> 3)


class SimBoard:
    def __init__(self, fd, screen=True, fps=5, blink_every=2.5):
        self.fd, self.screen, self.fps, self.blink_every = fd, screen, fps, blink_every
        self.emotion, self.blink = "neutral", False
        self.fb = render("neutral")            # 板子当前"显示"的内容
        self.streaming = False
        self.frame = 0
        self._seq = 0
        self._dirty = threading.Event()
        self._lock = threading.Lock()
        self._stop = False
        self._threads = [threading.Thread(target=self._read, daemon=True), threading.Thread(target=self._stream, daemon=True)]

    def start(self):
        for t in self._threads:
            t.start()
        return self

    def stop(self):
        self._stop = True
        self._dirty.set()

    def _send(self, data):
        with self._lock:
            view = memoryview(data)
            while view and not self._stop:
                if select.select([], [self.fd], [], 0.2)[1]:
                    view = view[os.write(self.fd, view):]

    def _packet(self, ptype, payload):
        self._seq += 1
        self._send(eb.pack(ptype, self._seq, payload))

    def _reply(self, i, text):
        self._send(f"EB1 {i} {text}\n".encode())

    def _frame(self, y0=0, y1=H):
        self.frame += 1
        px = self.fb[y0:y1].astype("<u2").tobytes()
        for p in eb.rect_packets(self.frame, 0, y0, W, y1 - y0, px):
            self._packet(eb.T_SCREEN_RECT, p)
        self._packet(eb.T_SCREEN_END, struct.pack("<H", self.frame & 0xFFFF))

    def _handle(self, line):
        m = re.fullmatch(r"EB1 (\d+) (\w+)(?: (.*))?", line)
        if not m:
            return
        i, cmd, arg = int(m.group(1)), m.group(2), (m.group(3) or "").split()
        if cmd == "PING":
            self._reply(i, "OK PONG")
        elif cmd == "EMOTION" and arg and arg[0] in FACES:
            self.emotion = arg[0]
            self.fb = render(self.emotion)
            self._reply(i, f"OK EMOTION {self.emotion}")
            self._dirty.set()
        elif cmd == "BAUD" and arg and arg[0].isdigit():
            self._reply(i, f"OK BAUD {arg[0]}")
        elif cmd == "SCREEN" and self.screen and arg:
            if arg[0] == "START":
                if len(arg) > 1 and arg[1].isdigit():
                    self.fps = max(1, int(arg[1]))
                self._reply(i, f"OK SCREEN {W} {H} {eb.FMT_RGB565}")
                self._packet(eb.T_SCREEN_INFO, struct.pack("<HHB", W, H, eb.FMT_RGB565))
                self.streaming = True
                self._frame()
            elif arg[0] == "SNAP":
                self._reply(i, f"OK SCREEN {W} {H} {eb.FMT_RGB565}")
                self._frame()
            elif arg[0] == "STOP":
                self.streaming = False
                self._reply(i, "OK SCREEN STOP")
            else:
                self._reply(i, "ERR command")
        else:
            self._reply(i, "ERR command")

    def _read(self):
        buf = b""
        while not self._stop:
            if not select.select([self.fd], [], [], 0.1)[0]:
                continue
            try:
                buf += os.read(self.fd, 4096)
            except OSError:
                return
            while b"\n" in buf:
                line, buf = buf.split(b"\n", 1)
                self._handle(line.decode("ascii", "replace").strip())

    def _stream(self):
        last_blink = time.monotonic()
        while not self._stop:
            changed = self._dirty.wait(1 / self.fps)
            self._dirty.clear()
            if self._stop or not self.streaming:
                continue
            if changed:
                self._frame()
            elif self.blink_every and time.monotonic() - last_blink > self.blink_every:
                last_blink = time.monotonic()
                self.fb = render(self.emotion, blink=True)       # 眨眼：只更新眼睛那一条
                self._frame(30, 100)
                time.sleep(0.15)
                self.fb = render(self.emotion)
                self._frame(30, 100)


def open_pty(**kw):
    """返回 (串口路径, SimBoard, 清理函数)。slave 端保持打开，避免客户端重连时读到 EIO。"""
    master, slave = os.openpty()
    tty.setraw(slave)
    board = SimBoard(master, **kw).start()

    def close():
        board.stop()
        time.sleep(0.1)
        os.close(master)
        os.close(slave)
    return os.ttyname(slave), board, close
