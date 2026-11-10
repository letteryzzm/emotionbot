"""回声门控。

机器人说话时，自己的声音会被麦克风收进去，误判成用户情绪（06-实验报告 3.7 的
D3 要求：自言自语 5 分钟 0 次误触发）。最便宜可靠的办法是播放期间直接丢音频，
播放结束后再留 300ms 尾巴。
"""
from __future__ import annotations

import time
from contextlib import contextmanager


class EchoGate:
    def __init__(self, tail: float = 0.3):
        self.tail = tail
        self._until = 0.0

    def mute(self, seconds: float = 1.0):
        self._until = max(self._until, time.monotonic() + seconds)

    def unmute(self):
        self._until = 0.0

    def muted(self) -> bool:
        return time.monotonic() < self._until

    @contextmanager
    def speaking(self, seconds: float):
        self.mute(seconds + self.tail)
        try:
            yield
        finally:
            pass
