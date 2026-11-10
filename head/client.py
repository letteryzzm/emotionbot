"""电脑端控制：自动找三块 Pico，按名字或 22 维向量下发。"""
import glob
import time

from .actuators import ACTUATORS, BY_NAME, CENTERS, NAMES, to_angles


def pico_ports():
    """Mac 用 usbmodem；Linux 只认 MicroPython 的 by-id，不碰机械臂和摄像头的 ttyACM"""
    return sorted(glob.glob("/dev/cu.usbmodem*")) + sorted(glob.glob("/dev/serial/by-id/*MicroPython*"))


class HeadClient:
    def __init__(self, ports=None, baud=115200, links=None):
        # links: {board: 有 write/readline 的对象}，测试时传假串口
        self.links = links if links is not None else self._discover(ports, baud)
        missing = {a.board for a in ACTUATORS} - set(self.links)
        if missing:
            print(f"[head] 没找到这些板: {sorted(missing)}，对应舵机的命令会被忽略")

    @staticmethod
    def _discover(ports, baud):
        import serial

        links = {}
        for p in ports or pico_ports():
            s = serial.Serial(p, baud, timeout=0.5)
            time.sleep(0.1)
            s.reset_input_buffer()
            s.write(b"?\n")
            for _ in range(5):  # 跳过 MicroPython 启动时可能残留的输出
                line = s.readline().decode(errors="ignore").strip()
                if line.startswith("ROLE "):
                    links[line.split()[1]] = s
                    break
            else:
                s.close()
        return links

    def _send(self, board, line):
        link = self.links.get(board)
        if link is None:
            return None
        link.write((line + "\n").encode())
        return link.readline().decode(errors="ignore").strip()

    def set(self, u):
        """u: {name: 0~1} 或 22 维向量"""
        by_board = {}
        for name, deg in to_angles(u).items():
            by_board.setdefault(BY_NAME[name].board, []).append(f"{name}={deg:.1f}")
        for board, kvs in by_board.items():
            self._send(board, "S " + " ".join(kvs))

    def angles(self):
        out = {}
        for board in self.links:
            reply = self._send(board, "G") or ""
            for kv in reply.split()[1:]:
                n, _, v = kv.partition("=")
                out[n] = float(v)
        return out

    def speed(self, deg_s):
        for board in self.links:
            self._send(board, f"V {deg_s}")

    def rest(self):
        for board in self.links:
            self._send(board, "R")
        # 固件的 R 不知道补偿，有实测中心的舵机再转一次
        if CENTERS:
            self.set({n: BY_NAME[n].u(BY_NAME[n].rest) for n in CENTERS})

    def center(self):
        for board in self.links:
            self._send(board, "C")

    def relax(self):
        for board in self.links:
            self._send(board, "X")

    def close(self):
        for link in self.links.values():
            if hasattr(link, "close"):
                link.close()

    @property
    def names(self):
        return NAMES
