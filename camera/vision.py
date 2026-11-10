"""摄像头 -> 人脸位置 + 距离（MediaPipe FaceLandmarker）。

距离：用两眼虹膜中心的像素间距，按针孔模型  d = f * IPD / pixels 估算。
  IPD 取成年人平均 63mm；f = (w/2) / tan(hfov/2)。hfov 默认 65°（多数笔记本/USB 摄像头），
  不准时用 scripts/track.py --calibrate 站在 50cm 处标定，或直接 --hfov 调。
这是单目粗估，误差没有实测过，只用来分「远/适中/太近」。
"""
import math
from pathlib import Path

import numpy as np

from camera.behavior import FaceObs

MODEL = Path(__file__).resolve().parent.parent / "models" / "face_landmarker.task"
IPD_M = 0.063
L_IRIS, R_IRIS = 468, 473


def focal_px(width, hfov_deg=65.0):
    return (width / 2) / math.tan(math.radians(hfov_deg) / 2)


def estimate_distance(ipd_px, width, hfov_deg=65.0, ipd_m=IPD_M):
    return focal_px(width, hfov_deg) * ipd_m / max(ipd_px, 1e-6)


class FaceTracker:
    def __init__(self, hfov_deg=65.0, model=MODEL):
        import mediapipe as mp

        self.mp = mp
        self.hfov = hfov_deg
        self.lm = mp.tasks.vision.FaceLandmarker.create_from_options(
            mp.tasks.vision.FaceLandmarkerOptions(
                base_options=mp.tasks.BaseOptions(model_asset_path=str(model)),
                running_mode=mp.tasks.vision.RunningMode.VIDEO,
                output_face_blendshapes=True,
                num_faces=1,
            )
        )
        self._last_ms = -1

    def process(self, frame_bgr, t):
        """返回 (FaceObs|None, landmarks|None, blendshapes dict)。t 为秒。"""
        import cv2

        h, w = frame_bgr.shape[:2]
        img = self.mp.Image(image_format=self.mp.ImageFormat.SRGB, data=cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2RGB))
        ms = max(int(t * 1000), self._last_ms + 1)
        self._last_ms = ms
        res = self.lm.detect_for_video(img, ms)
        if not res.face_landmarks:
            return None, None, {}
        lm = res.face_landmarks[0]
        a, b = lm[L_IRIS], lm[R_IRIS]
        ipd_px = math.hypot((a.x - b.x) * w, (a.y - b.y) * h)
        cx, cy = (a.x + b.x) / 2, (a.y + b.y) / 2
        obs = FaceObs(x=2 * cx - 1, y=2 * cy - 1, dist_m=estimate_distance(ipd_px, w, self.hfov), t=t, ipd_px=ipd_px)
        bs = {c.category_name: c.score for c in res.face_blendshapes[0]} if res.face_blendshapes else {}
        return obs, lm, bs
