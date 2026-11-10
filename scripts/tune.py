"""逐个舵机调试：发一条命令，读回角度，写进 outputs/tune_log.jsonl。

  tune.py cmd O TON              只让 TON 通电到 90°（同板其他舵机卸力）
  tune.py cmd S TON=95           小步转动，一步超过 MAX_STEP 度会被拒绝
  tune.py cmd X --board mouth    这块板全部卸力
  tune.py note TON ok "舌头往下" 记录现场观察（状态 ok / bad / info）
  tune.py range TON 60 125       记录实测可用范围
  tune.py recipe happy "说明" "S CUL=85 CUR=95" ...   记录一个已验证的表情步骤

R、C 会让全部舵机通电，这里不提供。速度每次都设成 SPEED，板子重启后默认是 600。
"""
import argparse
import glob
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from head.actuators import BY_NAME  # noqa: E402

LOG = ROOT / "outputs" / "tune_log.jsonl"
MAX_STEP = 5
SPEED = 30


def append(entry):
    LOG.parent.mkdir(exist_ok=True)
    entry = {"t": time.strftime("%Y-%m-%d %H:%M:%S"), **entry}
    with LOG.open("a") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


def open_board(board):
    import serial

    for p in glob.glob("/dev/serial/by-id/*MicroPython*"):
        s = serial.Serial(p, 115200, timeout=0.5)
        time.sleep(0.1)
        s.reset_input_buffer()
        s.write(b"?\n")
        line = s.readline().decode(errors="ignore").strip()
        if line.startswith(f"ROLE {board} "):
            return s
        s.close()
    sys.exit(f"没找到 {board} 板")


def ask(s, line):
    s.write((line + "\n").encode())
    return s.readline().decode(errors="ignore").strip()


def angles(s):
    return {k: float(v) for k, v in (kv.split("=") for kv in ask(s, "G").split()[1:])}


def targets(words):
    return dict((n, float(v)) for n, v in (w.split("=") for w in words))


def run_cmd(words, board, force):
    op = words[0].upper()
    if op not in ("O", "S", "X"):
        sys.exit("只接受 O、S、X")
    names = [w.split("=")[0] for w in words[1:]]
    unknown = [n for n in names if n not in BY_NAME]
    if unknown:
        sys.exit(f"没有这些舵机: {unknown}")
    boards = {BY_NAME[n].board for n in names} | ({board} if board else set())
    if len(boards) != 1:
        sys.exit("一条命令只能对一块板，X 要写 --board")
    board = boards.pop()

    s = open_board(board)
    try:
        before = angles(s)
        if op == "S" and not force:
            for n, v in targets(words[1:]).items():
                if abs(v - before[n]) > MAX_STEP:
                    sys.exit(f"{n} 从 {before[n]} 到 {v} 超过 {MAX_STEP}°，已拒绝")
        ask(s, f"V {SPEED}")
        line = " ".join(words)
        reply = ask(s, line)
        time.sleep(0.6)
        after = angles(s)
    finally:
        s.close()
    append({"type": "cmd", "board": board, "cmd": line, "reply": reply, "angles": after})
    print(line, "->", reply)
    print({n: after[n] for n in names} if names else after)


ap = argparse.ArgumentParser()
sub = ap.add_subparsers(dest="action", required=True)
c = sub.add_parser("cmd")
c.add_argument("words", nargs="+")
c.add_argument("--board")
c.add_argument("--force", action="store_true")
n = sub.add_parser("note")
n.add_argument("servo")
n.add_argument("status", choices=["ok", "bad", "info"])
n.add_argument("text")
r = sub.add_parser("range")
r.add_argument("servo")
r.add_argument("lo", type=float)
r.add_argument("hi", type=float)
e = sub.add_parser("recipe")
e.add_argument("name")
e.add_argument("text")
e.add_argument("steps", nargs="+")
args = ap.parse_args()

if args.action == "cmd":
    run_cmd(args.words, args.board, args.force)
elif args.action == "note":
    append({"type": "note", "servo": args.servo, "status": args.status, "text": args.text})
elif args.action == "range":
    append({"type": "range", "servo": args.servo, "lo": args.lo, "hi": args.hi})
else:
    append({"type": "recipe", "name": args.name, "text": args.text, "steps": args.steps})
