# 裸 Pico 回中工具：不用 PCB，舵机直接插面包板
#   .venv/bin/mpremote run firmware/center.py
# 启动后 PINS 上的舵机全部转到 90°（1500us），保持不动；Ctrl+C 退出（退出后舵机卸力，但会停在原位）
# 运行中在终端输入：
#   回车     -> 再回中一次
#   s 回车   -> 测试：90 → 60 → 120 → 90 慢慢扫一遍，看舵机好不好、有没有异响
import sys
import time
from machine import Pin, PWM

PINS = [0]  # 接了几个舵机就写几个 GPIO，例如 [0, 1, 2]；USB 供电时一次最多接 2 个


def us(p, t):
    p.duty_u16(int(t * 65535 / 20000))


def deg(p, d):
    us(p, 500 + 2000 * d / 180)  # 和 servo.py 一样：500~2500us 对应 0~180°


pwms = []
for g in PINS:
    p = PWM(Pin(g))
    p.freq(50)
    pwms.append(p)


def center():
    for p in pwms:
        deg(p, 90)
    print("CENTER 90deg on GP", PINS)


def sweep():
    for a, b in ((90, 60), (60, 120), (120, 90)):
        step = 1 if b > a else -1
        for d in range(a, b + step, step):
            for p in pwms:
                deg(p, d)
            time.sleep_ms(15)
    print("sweep done, back at 90")


center()
try:
    while True:
        line = sys.stdin.readline().strip()
        if line == "s":
            sweep()
        else:
            center()
except KeyboardInterrupt:
    for p in pwms:
        p.duty_u16(0)
