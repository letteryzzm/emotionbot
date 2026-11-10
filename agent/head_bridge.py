"""电脑端 -> 3 块 Pico 的驱动线程。

- 25Hz 下发，EMA 平滑一层；固件本身还有限速插值，两层叠加避免抖动。
- sim=True 或找不到串口时进入仿真：照常更新 current，供仪表盘/2D 预览使用。
- 退出时 rest()，避免舵机保持一个夸张的表情。
"""
from __future__ import annotations

import threading
import time

import numpy as np

from head.actuators import rest_vector, to_vector
from head.client import HeadClient


class HeadBridge:
    def __init__(self, sim: bool = False, ports=None, hz: float = 25.0,
                 alpha: float = 0.25, client: HeadClient | None = None):
        self.hz = hz
        self.alpha = alpha
        self.target = rest_vector()
        self.current = rest_vector()
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        self.client = None if sim else (client or self._try_connect(ports))
        self.sim = self.client is None
        if self.sim:
            print("[head] 仿真模式：表情只更新到仪表盘，不驱动舵机")

    @staticmethod
    def _try_connect(ports):
        try:
            c = HeadClient(ports=ports)
        except Exception as e:  # 没有 pyserial / 串口打不开
            print(f"[head] 连接失败: {e}")
            return None
        return c if c.links else None

    def set_target(self, vec):
        with self._lock:
            self.target = to_vector(vec) if isinstance(vec, dict) else np.clip(
                np.asarray(vec, dtype=np.float64), 0.0, 1.0)

    def start(self):
        if self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._loop, name="head-bridge", daemon=True)
        self._thread.start()
        return self

    def _loop(self):
        dt = 1.0 / self.hz
        while not self._stop.is_set():
            with self._lock:
                self.current = self.alpha * self.target + (1 - self.alpha) * self.current
                cur = self.current.copy()
            if self.client is not None:
                try:
                    self.client.set(cur)
                except Exception as e:
                    print(f"[head] 下发失败，转仿真: {e}")
                    self.client = None
                    self.sim = True
            self._stop.wait(dt)

    def rest(self):
        self.set_target(rest_vector())
        if self.client is not None:
            try:
                self.client.rest()
            except Exception:
                pass

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self.client is not None:
            try:
                self.client.rest()
                self.client.close()
            except Exception:
                pass
