# 眼部板：Eyes_Brow_Neck PCB，原 eyes.py 的引脚和范围
# name: (GPIO, 角度a, 角度b, rest)。a/b 只用来限幅，语义在 head/actuators.py
ROLE = "eyes"
SPEED_DEG_S = 600
CAL_PIN = 1      # 原版 mode 开关，=1 时校准
CAL_LEVEL = 1
SERVOS = {
    "LR": (8, 40, 140, 90),    # 眼球左右
    "UD": (9, 60, 140, 90),    # 眼球上下
    "TL": (13, 90, 160, 160),  # 左上眼皮 90=闭 160=睁
    "BL": (12, 90, 30, 30),    # 左下眼皮 90=闭 30=睁
    "TR": (11, 90, 30, 30),    # 右上眼皮
    "BR": (10, 90, 140, 140),  # 右下眼皮
}
