# 眉毛板：同一块 Eyes_Brow_Neck PCB，原 Brows.py 的引脚
# 原版 Brows.py 的 mode 开关含义和眼部板相反（0 时乱扫），这里不接开关
ROLE = "brows"
SPEED_DEG_S = 600
CAL_PIN = None
CAL_LEVEL = 1
SERVOS = {
    "LO": (8, 80, 120, 100),   # 左眉外侧 80=下 120=上
    "LI": (9, 100, 60, 80),    # 左眉内侧 100=下 60=上
    "RI": (13, 80, 120, 100),  # 右眉内侧
    "RO": (12, 100, 60, 80),   # 右眉外侧
}
