"""舵机验证和回中：每块 Pico 刷好固件、接上电源和 USB 后运行。
  .venv/bin/python scripts/servo_check.py                 # 所有板逐个舵机测试，结果存 outputs/servo_check.json
  .venv/bin/python scripts/servo_check.py --board eyes    # 只测一块板
  .venv/bin/python scripts/servo_check.py --name UD       # 只测一个舵机
  .venv/bin/python scripts/servo_check.py --center        # 全部转到 90° 并保持，装舵盘时用

测试时舵机离 90° 最多 ±SWING 度，且固件会按 config 的范围截断，所以装好连杆后也能用。
退出后舵机继续保持 90°（Pico 没断电）。眼部板的校准开关要拨到运行档，否则 S 命令不起作用。
"""
import argparse
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from head import HeadClient  # noqa: E402

SWING = 25
SPEED = 60  # deg/s，慢速才听得出异响


def names_of(client, board):
    reply = client._send(board, "?") or ""
    return reply.split()[2].split(",") if reply.startswith("ROLE") else []


def sweep(client, board, name):
    for deg in (90, 90 + SWING, 90 - SWING, 90):
        # 下巴两个舵机硬连在一起，只能镜像同时转，单独转一个会对顶
        extra = f" JR={180 - deg}" if name == "JL" else ""
        client._send(board, f"S {name}={deg}{extra}")
        time.sleep(SWING / SPEED + 0.3)


def check(client, boards, only=None, ask=input):
    result = {}
    for board in boards:
        client._send(board, f"V {SPEED}")
        client._send(board, "C")
        for name in names_of(client, board):
            if only and name != only:
                continue
            if name == "JR":
                print("JR 和 JL 一起测，跳过")
                continue
            while True:
                ask(f"[{board}] {name}：看着这个舵机，回车开始转动 ")
                sweep(client, board, name)
                a = ask("  正常 y / 不动或异响 n / 再转一遍 r：").strip().lower()
                if a != "r":
                    result[name] = "ok" if a == "y" else "bad"
                    break
        client._send(board, "C")
    return result


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--board", choices=["eyes", "brows", "mouth"])
    ap.add_argument("--name")
    ap.add_argument("--center", action="store_true")
    a = ap.parse_args()
    c = HeadClient()
    boards = [a.board] if a.board else sorted(c.links)
    boards = [b for b in boards if b in c.links]
    if not boards:
        sys.exit("没找到 Pico：检查 USB、是否已运行 firmware/flash.sh，以及 Thonny 等程序有没有占用串口")
    print("找到的板:", boards)
    if a.center:
        for b in boards:
            print(b, c._send(b, "C"), "全部 90°：", ",".join(names_of(c, b)))
        return
    res = check(c, boards, a.name)
    out = ROOT / "outputs/servo_check.json"
    old = json.loads(out.read_text()) if out.exists() else {}
    old.update(res)
    out.write_text(json.dumps(old, ensure_ascii=False, indent=1))
    bad = [k for k, v in res.items() if v != "ok"]
    print("测试", len(res), "个，有问题:", bad or "无", "；已回到 90°，结果在", out)


if __name__ == "__main__":
    main()
