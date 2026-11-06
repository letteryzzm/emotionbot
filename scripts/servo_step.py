"""第一次接线时手动小步试舵机。Pico 刷好固件、接上 5V 和 USB 后运行：
  .venv/bin/python scripts/servo_step.py

开机时所有舵机都不通电，这里选谁才通电谁：
  CUR         只让 CUR 通电并转到 90°，其他全部卸力
  JL JR       只让这几个通电到 90°
  walk        逐个来：每个舵机单独通电到 90°，回车换下一个
  CUR=95      转到 95°，只给 CUR 通电，已经通电的不变
  JL=85 JR=95 同一块板的几个舵机一起转
  X 全部卸力；G 看角度；!C 全部通电到 90°；q 退出

一步超过 MAX_STEP 度会被拒绝，确实要转就在前面加 !，比如 !TL=160。
没有发 R，所以不会自己转到 rest 姿态。
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from head import HeadClient  # noqa: E402
from head.actuators import ACTUATORS, BY_NAME  # noqa: E402

MAX_STEP = 15
SPEED = 30


def run(client, lines, out=print):
    last = {}
    walk = []
    for b in client.links:
        client._send(b, f"V {SPEED}")

    def only(names):
        board = BY_NAME[names[0]].board
        out(" ".join(names), "通电到 90°，其他卸力", client._send(board, "O " + " ".join(names)))
        last.update({n: 90.0 for n in names})

    for line in lines:
        s = line.strip()
        if s == "q":
            return
        if s == "" and walk:
            only([walk.pop(0)])
            out("回车换下一个" if walk else "这是最后一个。输入 X 卸力")
            continue
        if s == "":
            continue
        if s.lower() == "walk":
            walk = [a.name for a in ACTUATORS if a.board in client.links and a.name != "EXA"]
            only([walk.pop(0)])
            out("回车换下一个")
            continue
        if s.upper() in ("X", "G"):
            walk = []
            for b in client.links:
                out(b, client._send(b, s.upper()))
            continue
        if s.upper() == "!C":
            for b in client.links:
                out(b, client._send(b, "C"))
            last = {n: 90.0 for n in BY_NAME}
            continue
        names = s.upper().split()
        if all(n in BY_NAME for n in names):
            boards = {BY_NAME[n].board for n in names}
            if len(boards) == 1 and boards <= set(client.links):
                only(names)
            else:
                out("这些舵机不在同一块已连接的板上")
            continue
        force = s.startswith("!")
        try:
            items = [(n.upper(), float(v)) for n, v in (t.split("=") for t in s.lstrip("!").split())]
        except ValueError:
            items = []
        boards = {BY_NAME[n].board for n, _ in items if n in BY_NAME}
        if not items or len(boards) != 1 or any(n not in BY_NAME for n, _ in items):
            out("格式：CUR、walk、CUR=95、JL=85 JR=95、X、G、!C、q")
            continue
        board = boards.pop()
        if board not in client.links:
            out(f"{board} 板没连上")
            continue
        over = [n for n, d in items if abs(d - last.get(n, 90.0)) > MAX_STEP]
        if over and not force:
            out(f"{','.join(over)} 一步超过 {MAX_STEP}°，已拒绝。确认方向没错再在前面加 !")
            continue
        last.update(items)
        cmd = " ".join(f"{n}={d:g}" for n, d in items)
        out(cmd, client._send(board, f"S {cmd}"))


def main():
    c = HeadClient()
    if not c.links:
        sys.exit("没找到 Pico：检查 USB、是否已运行 firmware/flash.sh，以及 Thonny 等程序有没有占用串口")
    print("找到的板:", sorted(c.links), f"速度 {SPEED}°/s。输入 CUR 只动一个，walk 逐个看，X 全部卸力，q 退出")

    def lines():
        while True:
            try:
                yield input("> ")
            except EOFError:
                return

    run(c, lines())


if __name__ == "__main__":
    main()
