"""电脑端控制：自动找三块 Pico，按名字或 22 维向量下发。"""
import glob
import time

from .actuators import ACTUATORS, BY_NAME, NAMES, to_angles


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
    def _candidate_ports():
        from serial.tools import list_ports

        ports = list(list_ports.comports())
        # Raspberry Pi 的 VID 是 0x2E8A，先试这些，避免在虚拟串口上逐个等超时
        pico = [p.device for p in ports if p.vid == 0x2E8A]
        rest = [p.device for p in ports if p.vid != 0x2E8A]
        # Mac/Linux 的固定路径优先（Linux by-id 能避开机械臂/摄像头的 ttyACM）
        found = pico_ports()
        for p in pico + rest:
            if p not in found:
                found.append(p)
        return found

    @staticmethod
    def _discover(ports, baud):
        import serial

        links = {}
        wanted = {a.board for a in ACTUATORS}
        for p in ports if ports else HeadClient._candidate_ports():
            if set(links) >= wanted:  # 三块都找到了，不用再试后面的口
                break
            try:
                s = serial.Serial(p, baud, timeout=0.5)
            except serial.SerialException:
                continue  # 端口被别的程序占用 / 不是串口
            time.sleep(0.1)
            s.reset_input_buffer()
            # Pico 刚插上时可能还在启动；1.5s 内反复问，比只问一次稳
            role, deadline = None, time.monotonic() + 1.5
            while role is None and time.monotonic() < deadline:
                s.write(b"?\n")
                for _ in range(4):  # 跳过 MicroPython 启动时可能残留的输出
                    line = s.readline().decode(errors="ignore").strip()
                    if line.startswith("ROLE "):
                        role = line.split()[1]
                        break
                if role is None:
                    time.sleep(0.05)
            if role is None or role in links:  # 同角色重复出现时保留第一个
                s.close()
            else:
                links[role] = s
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
