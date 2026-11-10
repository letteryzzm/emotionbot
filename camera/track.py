"""眼睛跟随 + 距离表情。摄像头看人脸，眼球跟着转，按远近换表情。
  --viz        不接硬件，用 2D 卡通脸 + 摄像头叠加预览
  --hfov 65    摄像头水平视场角，距离不准就调它
  --calibrate  站在 50cm 处运行，按 c 键自动求出 hfov
  --camera N   摄像头编号
Esc 退出。
"""
import argparse
import math
import sys
import time
from pathlib import Path

import cv2

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from head import HeadClient  # noqa: E402
from camera.behavior import CLOSE, FAR, NEAR, Behavior  # noqa: E402
from camera.vision import IPD_M, FaceTracker  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--camera", type=int, default=0)
ap.add_argument("--viz", action="store_true")
ap.add_argument("--hfov", type=float, default=65.0)
ap.add_argument("--calibrate", action="store_true")
args = ap.parse_args()

tracker = FaceTracker(args.hfov)
beh = Behavior()
head = None if args.viz else HeadClient()
if args.viz:
    import matplotlib.pyplot as plt

    from head.viz import draw

    plt.ion()
    fig, ax = plt.subplots(figsize=(4, 4))

cap = cv2.VideoCapture(args.camera)
t0 = time.time()
try:
    while cap.isOpened():
        ok, frame = cap.read()
        if not ok:
            break
        t = time.time() - t0
        obs, lm, _ = tracker.process(frame, t)
        u = beh.step(obs, t)
        if head:
            head.set(u)
        else:
            draw(u, ax, title=beh.state)
            plt.pause(0.001)

        h, w = frame.shape[:2]
        if obs:
            cv2.circle(frame, (int((obs.x + 1) / 2 * w), int((obs.y + 1) / 2 * h)), 8, (0, 255, 0), 2)
        txt = f"{beh.state}  {obs.dist_m:.2f}m" if obs else f"{beh.state}  no face"
        cv2.putText(frame, txt, (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 255, 255), 2)
        cv2.imshow("track", frame)
        k = cv2.waitKey(1) & 0xFF
        if k == 27:
            break
        if k == ord("c") and args.calibrate and lm:
            a, b = lm[468], lm[473]
            ipd_px = math.hypot((a.x - b.x) * w, (a.y - b.y) * h)
            # d = (w/2)/tan(hfov/2) * IPD / ipd_px，d = 0.5m
            f = 0.5 * ipd_px / IPD_M
            print(f"--hfov {math.degrees(2 * math.atan((w / 2) / f)):.1f}")
finally:
    cap.release()
    cv2.destroyAllWindows()
    if head:
        head.rest()
        head.close()
