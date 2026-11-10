"""列出所有串口，并试探哪些是 Pico（发 '?' 看有没有 ROLE 应答）。

    python scripts/list_ports.py

接机器头之前先跑这个，确认三块板的串口号；然后可以：
    python -m app.run --ports COM5,COM6,COM7                 # Windows
    python -m app.run --ports /dev/ttyACM0,/dev/ttyACM1,/dev/ttyACM2   # Linux
"""
from __future__ import annotations

import sys
import time

from serial.tools import list_ports


def probe(device: str, baud: int = 115200, tries: int = 3) -> str | None:
    import serial

    try:
        s = serial.Serial(device, baud, timeout=0.3, write_timeout=0.5)
    except serial.SerialException as e:
        return f"打不开: {e}"
    try:
        s.reset_input_buffer()
        for _ in range(tries):
            s.write(b"?\n")
            time.sleep(0.05)
            line = s.readline().decode(errors="ignore").strip()
            if line.startswith("ROLE "):
                return f"ROLE {line.split()[1]}"
        return "无应答（不是 Pico，或固件没在跑）"
    finally:
        s.close()


def main() -> int:
    ports = list(list_ports.comports())
    if not ports:
        print("没有枚举到串口。检查 USB 线是否支持数据、驱动是否装好。")
        return 1
    for p in ports:
        print(f"{p.device:10s}  VID:PID={p.vid}:{p.pid}  {p.description}")
        print(f"           {p.hwid}")
        print(f"           -> {probe(p.device)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
