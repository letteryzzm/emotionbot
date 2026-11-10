"""EB2：T5AI 板子和电脑之间的二进制数据包（屏幕回传、语音），和 EB1 文本命令共用一根串口。

协议见 docs/T5屏幕与语音协议-EB2.md。现有固件还没有实现这些包；这里是电脑端的编解码、
流解析器和串口读写线程，配 head/t5_sim.py 的模拟板子，不接硬件也能先测。
"""
from __future__ import annotations

import re
import struct
import threading
import time
import zlib
from collections import namedtuple

import numpy as np

EMOTIONS = ("neutral", "happy", "sad", "angry", "surprise", "fear", "disgust")

MAGIC = b"\xeb\x02"          # 0xEB 不是 ASCII，不会和 EB1 文本行混淆
HEADER = 8                   # magic(2) type(1) flags(1) seq(2) len(2)
MAX_PAYLOAD = 4096
T_SCREEN_INFO, T_SCREEN_RECT, T_SCREEN_END = 0x01, 0x02, 0x03
T_PCM_UP, T_PCM_DOWN, T_PCM_STAT = 0x10, 0x11, 0x12
ENC_RAW, ENC_RLE = 0, 1
FMT_RGB565 = 0

Packet = namedtuple("Packet", "type flags seq payload")


def _crc_table():
    t = []
    for i in range(256):
        c = i << 8
        for _ in range(8):
            c = ((c << 1) ^ 0x1021) & 0xFFFF if c & 0x8000 else (c << 1) & 0xFFFF
        t.append(c)
    return t


_CRC = _crc_table()


def crc16(data, crc=0xFFFF):
    """CRC-16/CCITT-FALSE，crc16(b'123456789') == 0x29B1"""
    for b in data:
        crc = ((crc << 8) & 0xFFFF) ^ _CRC[(crc >> 8) ^ b]
    return crc


def pack(ptype, seq, payload=b"", flags=0):
    if len(payload) > MAX_PAYLOAD:
        raise ValueError("payload too large")
    body = struct.pack("<BBHH", ptype, flags, seq & 0xFFFF, len(payload)) + bytes(payload)
    return MAGIC + body + struct.pack("<H", crc16(body))


class Parser:
    """把串口字节流拆成 ('line', 文本) 和 ('packet', Packet)。校验失败或夹杂垃圾时逐字节重新同步。"""

    def __init__(self):
        self.buf = bytearray()
        self.bad_crc = 0
        self.skipped = 0

    def feed(self, data):
        buf = self.buf
        buf.extend(data)
        out = []
        while buf:
            if buf[0] == 0xEB:
                if len(buf) < 2:
                    break
                if buf[1] != 0x02:
                    del buf[0]; self.skipped += 1
                    continue
                if len(buf) < HEADER:
                    break
                ptype, flags, seq, ln = struct.unpack_from("<BBHH", buf, 2)
                if ln > MAX_PAYLOAD:
                    del buf[0]; self.skipped += 1
                    continue
                total = HEADER + ln + 2
                if len(buf) < total:
                    break
                if crc16(bytes(buf[2:HEADER + ln])) == struct.unpack_from("<H", buf, HEADER + ln)[0]:
                    out.append(("packet", Packet(ptype, flags, seq, bytes(buf[HEADER:HEADER + ln]))))
                    del buf[:total]
                else:
                    self.bad_crc += 1
                    del buf[0]
                continue
            nl, eb = buf.find(b"\n"), buf.find(b"\xeb")
            if eb >= 0 and (nl < 0 or eb < nl):      # 包头前面的杂音（日志碎片）丢掉
                self.skipped += eb
                del buf[:eb]
                continue
            if nl < 0:
                if len(buf) > 1024:
                    self.skipped += len(buf)
                    del buf[:]
                break
            line = bytes(buf[:nl]).decode("ascii", "replace").strip()
            del buf[:nl + 1]
            if line:
                out.append(("line", line))
        return out


# ---------- RGB565 + RLE ----------
def rle16_encode(px):
    """px: RGB565 小端字节。输出 (次数 1..255, 像素 2 字节) 的重复序列，界面这类大色块压缩率很高。"""
    a = np.frombuffer(px, "<u2")
    out = bytearray()
    i, n = 0, len(a)
    while i < n:
        v = a[i]
        j = i + 1
        while j < n and j - i < 255 and a[j] == v:
            j += 1
        out += bytes((j - i,)) + int(v).to_bytes(2, "little")
        i = j
    return bytes(out)


def rle16_decode(data, npix):
    if len(data) % 3:
        raise ValueError("bad rle length")
    out = bytearray()
    for i in range(0, len(data), 3):
        out += data[i + 1:i + 3] * data[i]
    if len(out) != npix * 2:
        raise ValueError("rle pixel count mismatch")
    return bytes(out)


def rect_packets(frame, x, y, w, h, pixels, enc=ENC_RLE):
    """把一块 RGB565 区域按行切成若干个 SCREEN_RECT 载荷（每个不超过 MAX_PAYLOAD）。"""
    rows = [pixels[r * w * 2:(r + 1) * w * 2] for r in range(h)]
    if enc == ENC_RLE:
        rows = [rle16_encode(r) for r in rows]
    limit = MAX_PAYLOAD - 11
    out, cur, cur_rows, y0 = [], b"", 0, y
    for k, r in enumerate(rows):
        if len(r) > limit:
            raise ValueError("one row exceeds packet size")
        if cur_rows and len(cur) + len(r) > limit:
            out.append(struct.pack("<HHHHHB", frame, x, y0, w, cur_rows, enc) + cur)
            cur, cur_rows, y0 = b"", 0, y + k
        cur += r
        cur_rows += 1
    if cur_rows:
        out.append(struct.pack("<HHHHHB", frame, x, y0, w, cur_rows, enc) + cur)
    return out


def _chunk(t, d):
    return struct.pack(">I", len(d)) + t + d + struct.pack(">I", zlib.crc32(t + d) & 0xFFFFFFFF)


class ScreenBuffer:
    """电脑端的屏幕副本：按板子发来的区域更新，随时可以导出 PNG。"""

    def __init__(self, w, h):
        self.w, self.h = w, h
        self.px = bytearray(w * h * 2)

    def apply_rect(self, x, y, w, h, enc, data):
        if w == 0 or h == 0 or x + w > self.w or y + h > self.h:
            raise ValueError("rect out of range")
        raw = bytes(data) if enc == ENC_RAW else rle16_decode(data, w * h) if enc == ENC_RLE else None
        if raw is None or len(raw) != w * h * 2:
            raise ValueError("bad rect data")
        for r in range(h):
            o = ((y + r) * self.w + x) * 2
            self.px[o:o + w * 2] = raw[r * w * 2:(r + 1) * w * 2]

    def png(self):
        a = np.frombuffer(bytes(self.px), "<u2").reshape(self.h, self.w)
        rows = np.zeros((self.h, 1 + 3 * self.w), np.uint8)
        rows[:, 1::3] = (((a >> 11) & 31) * 255 + 15) // 31
        rows[:, 2::3] = (((a >> 5) & 63) * 255 + 31) // 63
        rows[:, 3::3] = ((a & 31) * 255 + 15) // 31
        return (b"\x89PNG\r\n\x1a\n" + _chunk(b"IHDR", struct.pack(">IIBBBBB", self.w, self.h, 8, 2, 0, 0, 0))
                + _chunk(b"IDAT", zlib.compress(rows.tobytes(), 1)) + _chunk(b"IEND", b""))


# ---------- 语音包（固件实现后用） ----------
def pack_pcm_up(seq, ts_ms, vad, pcm):
    return pack(T_PCM_UP, seq, struct.pack("<IB", ts_ms & 0xFFFFFFFF, vad) + pcm)


def parse_pcm_up(payload):
    ts, vad = struct.unpack_from("<IB", payload)
    return ts, vad, payload[5:]


# ---------- 串口 ----------
class CommandError(RuntimeError):
    pass


class T5Stream:
    """独占打开 T5 命令串口：后台线程读，文本行里的 EB1 回执交给 command()，二进制包交给 on_packet。"""

    def __init__(self, port, baud=115200, on_packet=None, on_line=None):
        import serial
        self._serial = serial
        s = serial.Serial()
        s.port, s.baudrate, s.timeout, s.write_timeout = port, baud, 0.05, 1
        s.exclusive, s.dtr, s.rts = True, False, False
        s.open()
        self.ser = s
        self.parser = Parser()
        self.on_packet, self.on_line = on_packet, on_line
        self.error = None
        self.packets = 0
        self._id = 0
        self._waiters = {}
        self._wlock = threading.Lock()
        self._stop = False
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self):
        while not self._stop:
            try:
                d = self.ser.read(self.ser.in_waiting or 1)
            except (OSError, self._serial.SerialException) as e:
                self.error = str(e)
                return
            if not d:
                continue
            for kind, item in self.parser.feed(d):
                if kind == "packet":
                    self.packets += 1
                    if self.on_packet:
                        self.on_packet(item)
                    continue
                m = re.fullmatch(r"EB1 (\d+) (.*)", item)
                w = self._waiters.get(int(m.group(1))) if m else None
                if w:
                    w[1] = m.group(2)
                    w[0].set()
                elif self.on_line:
                    self.on_line(item)

    def command(self, text, timeout=2.0):
        """发一条 EB1 命令，返回 (回执文本, 往返毫秒)。ERR 回执抛 CommandError，没回执抛 TimeoutError。"""
        if self.error:
            raise OSError(self.error)
        with self._wlock:
            self._id += 1
            i = self._id
            w = self._waiters[i] = [threading.Event(), None]
            t0 = time.perf_counter()
            self.ser.write(f"EB1 {i} {text}\n".encode("ascii"))
        try:
            if not w[0].wait(timeout):
                raise TimeoutError(f"no reply to {text!r}")
            rtt = (time.perf_counter() - t0) * 1000
        finally:
            self._waiters.pop(i, None)
        if w[1].startswith("ERR"):
            raise CommandError(w[1])
        return w[1], rtt

    def write(self, data):
        """写原始字节（语音下行包），和 command() 共用一把锁，避免两个线程的写入穿插。"""
        with self._wlock:
            self.ser.write(data)

    def set_baud(self, baud):
        """让板子和主机一起切到 baud（板子上限 2000000，更高会被拒绝）。切完用 PING 验证，失败抛 TimeoutError。
        板子提速后 4 秒内没收到有效命令会自己回到 115200，所以失败后把主机也调回去即可。"""
        old = self.ser.baudrate
        self.command(f"BAUD {baud}")
        time.sleep(0.12)
        self.ser.baudrate = baud
        self.ser.reset_input_buffer()
        try:
            self.command("PING", timeout=1.0)
        except TimeoutError:
            self.ser.baudrate = old
            raise

    def close(self):
        self._stop = True
        self._thread.join(1)
        self.ser.close()
