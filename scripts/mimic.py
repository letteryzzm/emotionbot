"""摄像头表情模仿：MediaPipe blendshape -> 舵机。
  --viz   不接硬件，在窗口里显示 2D 预览
  --record outputs/xxx.npz  同时记录 (blendshape, u) 对，作为表情学习的数据
模型文件: models/face_landmarker.task
  curl -L -o models/face_landmarker.task https://storage.googleapis.com/mediapipe-models/face_landmarker/face_landmarker/float16/1/face_landmarker.task
"""
import argparse
import sys
import time
from pathlib import Path

import cv2
import mediapipe as mp
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from head import HeadClient  # noqa: E402
from head.blendshape_map import Smoother, blendshapes_to_u  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--camera", type=int, default=0)
ap.add_argument("--viz", action="store_true")
ap.add_argument("--record")
args = ap.parse_args()

opts = mp.tasks.vision.FaceLandmarkerOptions(
    base_options=mp.tasks.BaseOptions(model_asset_path=str(ROOT / "models/face_landmarker.task")),
    running_mode=mp.tasks.vision.RunningMode.VIDEO,
    output_face_blendshapes=True,
    num_faces=1,
)
landmarker = mp.tasks.vision.FaceLandmarker.create_from_options(opts)
head = None if args.viz else HeadClient()
smooth = Smoother(0.4)
log_bs, log_u = [], []

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
        img = mp.Image(image_format=mp.ImageFormat.SRGB, data=cv2.cvtColor(frame, cv2.COLOR_BGR2RGB))
        res = landmarker.detect_for_video(img, int((time.time() - t0) * 1000))
        if res.face_blendshapes:
            bs = {c.category_name: c.score for c in res.face_blendshapes[0]}
            u = smooth(blendshapes_to_u(bs))
            if head:
                head.set(u)
            else:
                draw(u, ax)
                plt.pause(0.001)
            if args.record:
                log_bs.append([bs[k] for k in sorted(bs)])
                log_u.append(u)
        cv2.imshow("camera", frame)
        if cv2.waitKey(1) & 0xFF == 27:  # Esc 退出
            break
finally:
    cap.release()
    cv2.destroyAllWindows()
    if head:
        head.rest()
        head.close()
    if args.record and log_u:
        np.savez(args.record, blendshapes=np.array(log_bs), u=np.array(log_u))
        print("saved", args.record, len(log_u))
