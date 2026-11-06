# 统一固件：眼 / 眉 / 嘴三块 Pico 刷同一份 main.py，只有 config.py 不同
#
# 和原版的区别：原版只有嘴部 Pico 接电脑，再用 2 根 GPIO 给眼、眉板发 4 种离散状态，
# 电脑没法连续控制眼和眉。这里每块 Pico 各接一根 USB，都能收连续角度。
#
# 串口协议（115200，每行一条，\n 结尾）：
#   ?                 -> ROLE <role> <name1>,<name2>,...
#   O CUR             -> 只让 CUR 通电并转到 90°，其他全部卸力；O JL JR 可以选几个
#   S LR=90 UD=100    -> 设目标角度（会被 config 里的范围截断），只给这几个舵机通电，回 OK
#   G                 -> A LR=90.0 UD=100.0 ...  当前角度
#   V 600             -> 最大转速 deg/s
#   R                 -> 全部通电，回 rest 姿态
#   C                 -> 全部通电，90°（装舵盘时用）
#   X                 -> 全部卸力
#
# 开机时所有舵机都不发信号，接上 5V 也不会动，收到命令才通电。
# 校准开关只在拨过去的那一下发一次 C，开机时停在哪一档都不起作用。
import sys
import time

import config
from servo import Servo

TICK_MS = 10

servos = {}
limits = {}
rest = {}
cur = {}
tgt = {}
speed = config.SPEED_DEG_S
active = set()   # 正在发信号的舵机
last_cal = False


def setup():
    for name, (pin, a, b, r) in config.SERVOS.items():
        servos[name] = Servo(pin)
        servos[name].off()
        limits[name] = (min(a, b), max(a, b))
        rest[name] = r
        cur[name] = 90.0
        tgt[name] = 90.0


def activate(name):
    if name not in active:
        active.add(name)
        servos[name].write(cur[name])


def release(name):
    active.discard(name)
    servos[name].off()


def clamp(name, deg):
    lo, hi = limits[name]
    return max(lo, min(hi, deg))


def handle(line):
    global speed
    parts = line.strip().split()
    if not parts:
        return None
    cmd = parts[0]
    if cmd == "?":
        return "ROLE %s %s" % (config.ROLE, ",".join(config.SERVOS))
    if cmd == "S":
        for kv in parts[1:]:
            name, _, val = kv.partition("=")
            if name not in servos:
                return "ERR unknown %s" % name
            tgt[name] = clamp(name, float(val))
            activate(name)
        return "OK"
    if cmd == "O":
        names = parts[1:]
        for n in names:
            if n not in servos:
                return "ERR unknown %s" % n
        for n in list(active):
            if n not in names:
                release(n)
        for n in names:
            tgt[n] = cur[n] = 90.0
            active.add(n)
            servos[n].write(90)
        return "OK"
    if cmd == "G":
        return "A " + " ".join("%s=%.1f" % (n, cur[n]) for n in servos)
    if cmd == "V":
        speed = max(10.0, float(parts[1]))
        return "OK"
    if cmd == "R":
        for n in servos:
            tgt[n] = float(rest[n])
            activate(n)
        return "OK"
    if cmd == "C":
        # 装配校准不受范围限制，直接写 90°
        for n in servos:
            tgt[n] = cur[n] = 90.0
            active.add(n)
            servos[n].write(90)
        return "OK"
    if cmd == "X":
        for n in servos:
            release(n)
        return "OK"
    return "ERR unknown command"


def tick(dt_s):
    # 限速插值：每个 tick 最多转 speed*dt，避免舵机猛打、也让表情过渡更自然
    step = speed * dt_s
    for n in active:
        s = servos[n]
        d = tgt[n] - cur[n]
        if d == 0:
            continue
        if abs(d) <= step:
            cur[n] = tgt[n]
        else:
            cur[n] += step if d > 0 else -step
        s.write(cur[n])


def cal_switch_on():
    if config.CAL_PIN is None:
        return False
    return cal_pin.value() == config.CAL_LEVEL


def poll_cal():
    # 只在拨到校准档的那一下触发，不然开机停在校准档会让全部舵机通电
    global last_cal
    on = cal_switch_on()
    if on and not last_cal:
        handle("C")
    last_cal = on


def main():
    import select
    from machine import Pin

    global cal_pin, last_cal
    if config.CAL_PIN is not None:
        cal_pin = Pin(config.CAL_PIN, Pin.IN, Pin.PULL_UP)
    led = Pin(25, Pin.OUT)
    setup()
    last_cal = cal_switch_on()
    poll = select.poll()
    poll.register(sys.stdin, select.POLLIN)
    buf = ""
    last = time.ticks_ms()
    while True:
        while poll.poll(0):
            ch = sys.stdin.read(1)
            if ch == "\n":
                reply = handle(buf)
                if reply:
                    print(reply)
                buf = ""
                led.toggle()
            elif ch != "\r":
                buf += ch
        now = time.ticks_ms()
        poll_cal()
        tick(time.ticks_diff(now, last) / 1000)
        last = now
        time.sleep_ms(TICK_MS)


if __name__ == "__main__":
    main()
