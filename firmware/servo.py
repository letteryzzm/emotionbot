# 舵机驱动：原项目缺这个文件（Cogley 用的自带库），这里按标准 50Hz PWM 重写
# MG90S / SG90 一般是 500~2500us 对应 0~180°，装配时用 C 命令回中检查
from machine import Pin, PWM


class Servo:
    def __init__(self, pin_id, min_us=500, max_us=2500, freq=50):
        self.pwm = PWM(Pin(pin_id))
        self.pwm.freq(freq)
        self.min_us = min_us
        self.max_us = max_us
        self.period_us = 1_000_000 // freq

    def write(self, deg):
        deg = max(0, min(180, deg))
        us = self.min_us + (self.max_us - self.min_us) * deg / 180
        self.pwm.duty_u16(int(us * 65535 / self.period_us))

    def off(self):
        # 占空比 0 = 不出脉冲，舵机卸力
        self.pwm.duty_u16(0)
