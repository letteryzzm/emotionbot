"""语音 -> 脸：回复的情绪进 dialog 层，TTS 音量驱动下巴进 lips 层。

眼球不写进 dialog，说话时视觉层继续带着眼睛跟人。控制进程没开时只丢帧，不影响说话。
"""
import math
import struct
import threading
import time
from collections import deque

from .expressions import EXPRESSIONS

ALIAS = {"surprise": "surprised"}     # 语音模型和表情库的叫法不同
KEEP_GAZE = {"LR", "UD"}
EMOTION_TTL = 1.5     # 说完后表情再留这么久
LIPS_TTL = 0.3
SEND_S = 0.05
BYTES_PER_S = 32000    # 16 kHz s16le 单声道
PLAYER_LATENCY = 0.06  # paplay --latency-msec
JAW_MAX = 0.6         # 说话时下巴最多张到行程的这个比例
SILENCE_RMS = 300.0
PEAK_FLOOR = 2000.0
PEAK_DECAY = 0.999    # 每 20 ms 一包，约 20 秒忘掉一次大声
RELEASE = 0.7         # 张嘴跟得快，闭嘴慢一点，不然看着在抖


def emotion_pose(name):
    pose = EXPRESSIONS.get(ALIAS.get(name, name), {})
    return {n: float(x) for n, x in pose.items() if n not in KEEP_GAZE}


def rms(chunk):
    n = len(chunk) // 2
    if not n:
        return 0.0
    return math.sqrt(sum(x * x for x in struct.unpack(f"<{n}h", chunk[:n * 2])) / n)


class VoiceFace:
    """PCM 比实际出声提前写进播放器，所以每包先算好播放时刻，到点再动下巴。"""

    def __init__(self, hub, clock=time.monotonic, start=True):
        self.hub, self.clock = hub, clock
        self.pose = {}
        self.jaw = 0.0
        self.peak = PEAK_FLOOR
        self.play_at = 0.0
        self.lock = threading.Lock()
        self.timeline = deque()
        self.wake = threading.Event()
        if start:
            threading.Thread(target=self._run, daemon=True).start()

    def on_emotion(self, name):
        self.pose = emotion_pose(name)
        with self.lock:
            self.timeline.append((0.0, None))    # 表情不等声音，下一拍就发
        self.wake.set()

    def audio(self, chunk):
        """每包 PCM 调一次，和播放在同一个线程，这里不能等网络。"""
        level = rms(chunk)
        self.peak = max(PEAK_FLOOR, self.peak * PEAK_DECAY, level)
        want = 0.0 if level < SILENCE_RMS else JAW_MAX * (level / self.peak) ** 0.7
        self.jaw = want if want > self.jaw else max(want, self.jaw * RELEASE)
        self.play_at = max(self.clock() + PLAYER_LATENCY, self.play_at) + len(chunk) / BYTES_PER_S
        with self.lock:
            self.timeline.append((self.play_at, self.jaw))
        self.wake.set()

    def tick(self):
        """发出已经到点的帧，只发最新一帧。返回还有没有没到点的。"""
        now = self.clock()
        jaw, due = None, False
        with self.lock:
            while self.timeline and self.timeline[0][0] <= now:
                value = self.timeline.popleft()[1]
                due = True
                jaw = jaw if value is None else value
            left = bool(self.timeline)
        if not due:
            return left
        if self.pose:
            self.hub.intent("dialog", self.pose, ttl=EMOTION_TTL)
        else:
            self.hub.clear("dialog")     # neutral 没有姿态，交回视觉层
        if jaw is not None:
            self.hub.intent("lips", {"JL": jaw, "JR": jaw}, ttl=LIPS_TTL)
        return left

    def _run(self):
        while True:
            self.wake.wait()
            self.wake.clear()
            while self.tick():
                time.sleep(SEND_S)
