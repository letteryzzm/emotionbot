# 舵机好坏测试：不用刷 main.py，也不用在终端输入。PINS 上的舵机逐个转，全部测完停在 90°。
#   .venv/bin/mpremote run firmware/sweep_test.py
# 裸 Pico：信号接 GP0，红线接 VBUS（40 脚），棕线接 GND（38 脚），一次只接 1 个 MG90S。
# 插在 PCB 上：把 PINS 改成板子的通道，眼部板是 [8, 9, 10, 11, 12, 13]，舵机电源走板子的 5 V。
# 没有连杆时才用：这里不受固件范围限制，连杆装好后用 scripts/servo_check.py。
import time
from machine import Pin, PWM

PINS = [0]
ROUNDS = 3


def deg(p, d):
    p.duty_u16(int((500 + 2000 * d / 180) * 65535 / 20000))


def move(p, a, b):
    step = 1 if b > a else -1
    for d in range(a, b + step, step):
        deg(p, d)
        time.sleep_ms(15)


pwms = []
for g in PINS:
    p = PWM(Pin(g))
    p.freq(50)
    deg(p, 90)
    pwms.append(p)
time.sleep_ms(500)
for g, p in zip(PINS, pwms):
    print("GP%d: 开始转" % g)
    for i in range(ROUNDS):
        move(p, 90, 60)
        move(p, 60, 120)
        move(p, 120, 90)
    print("GP%d: 完成，停在 90" % g)
    time.sleep_ms(500)
print("全部完成，舵机保持 90 度。拔掉换下一个，再运行一次")
