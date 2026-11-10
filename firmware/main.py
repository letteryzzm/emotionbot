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
#   V 600             -> 最大转速 deg/s（10~1000）
#   W 1000            -> 打开失联保护：这么多毫秒收不到任何命令，就回 rest，再过 2 秒卸力，然后自动关闭保护
#   W 0               -> 关闭失联保护（默认关闭，手动校准时舵机可以一直保持）
#   W                 -> W <毫秒>，查询当前设置
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
MAX_SPEED = 1000.0
MAX_LINE = 1024
WD_RELEASE_MS = 2000

servos = {}
limits = {}
rest = {}
cur = {}
tgt = {}
speed = config.SPEED_DEG_S
active = set()   # 正在发信号的舵机
last_cal = False
wd_ms = 0        # 失联保护时长，0 = 关闭
wd_left = 0      # 还剩多少毫秒没收到命令就触发
release_left = None   # 触发后还剩多少毫秒卸力


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
    global speed, wd_ms, wd_left
    parts = line.strip().split()
    if not parts:
        return None
    cmd = parts[0]
    if cmd == "?":
        return "ROLE %s %s" % (config.ROLE, ",".join(config.SERVOS))
    if cmd == "S":
        # 整行先检查，避免一半舵机动、一半报错。nan 不满足这个比较，不会被截断成上限
        goals = []
        for kv in parts[1:]:
            name, _, val = kv.partition("=")
            if name not in servos:
                return "ERR unknown %s" % name
            deg = float(val)
            if not -1000 < deg < 1000:
                return "ERR bad %s" % name
            goals.append((name, deg))
        for name, deg in goals:
            tgt[name] = clamp(name, deg)
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
        val = float(parts[1])
        if not 0 < val < 1000000:
            return "ERR bad speed"
        speed = min(MAX_SPEED, max(10.0, val))
        return "OK"
    if cmd == "W":
        if len(parts) == 1:
            return "W %d" % wd_ms
        val = int(parts[1])
        if val != 0 and not 100 <= val <= 10000:
            return "ERR bad timeout"
        wd_ms = wd_left = val
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


def safe_handle(line):
    # 一条坏命令不能让主循环退出，否则舵机会停在原地一直出力，失联保护也不再运行
    global wd_left, release_left
    wd_left = wd_ms
    release_left = None
    try:
        return handle(line)
    except Exception:
        return "ERR bad command"


def watchdog(dt_ms):
    global wd_ms, wd_left, release_left
    if wd_ms:
        wd_left -= dt_ms
        if wd_left <= 0:
            wd_ms = 0
            release_left = WD_RELEASE_MS
            for n in active:   # 只动本来通电的舵机，不给别的舵机通电
                tgt[n] = clamp(n, float(rest[n]))
    if release_left is not None:
        release_left -= dt_ms
        if release_left <= 0:
            release_left = None
            for n in list(active):
                release(n)


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
                reply = safe_handle(buf)
                if reply:
                    print(reply)
                buf = ""
                led.toggle()
            elif ch != "\r" and len(buf) < MAX_LINE:
                buf += ch
        now = time.ticks_ms()
        poll_cal()
        dt_ms = time.ticks_diff(now, last)
        watchdog(dt_ms)
        tick(dt_ms / 1000)
        last = now
        time.sleep_ms(TICK_MS)


if __name__ == "__main__":
    main()
