"""USB 摄像头人脸情绪识别。

流程：OpenCV 抓帧 -> Haar 人脸检测（取最大脸）-> EmotiEffNet-B0 分类。
用 Haar 而不是 MediaPipe 是为了少一个模型文件，单人正脸场景够用。

已知局限（06-实验报告 2.2）：多人画面里"最大脸"经常不是说话人。
demo 场景是一个用户坐在机器人前面，这个问题不出现；多人场景要加主动说话人检测。
"""
from __future__ import annotations

import threading
import time

import numpy as np

from .types import LABEL7, ModalityResult, normalize_probs

EFF_CLASSES = ["Anger", "Contempt", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise"]
EFF_MAP = {"Anger": "angry", "Disgust": "disgust", "Fear": "fear", "Happiness": "happy",
           "Neutral": "neutral", "Sadness": "sad", "Surprise": "surprise"}  # Contempt 丢弃


def _auto_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


class CameraFER:
    def __init__(self, camera: int = 0, fps: float = 8.0, device: str | None = None,
                 face_min: int = 60):
        self.fps = fps
        self.face_min = face_min
        self.ok = False
        self._result: ModalityResult | None = None
        self._ts = 0.0
        self._jpeg: bytes | None = None
        self._jpeg_ts = 0.0
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

        try:
            import cv2

            self.cv2 = cv2
            self.cap = cv2.VideoCapture(camera)
            if not self.cap.isOpened():
                raise RuntimeError(f"打不开摄像头 {camera}")
            self.cascade = cv2.CascadeClassifier(
                cv2.data.haarcascades + "haarcascade_frontalface_default.xml")
            import torch
            import torch.nn.functional as F
            from emotiefflib.facial_analysis import EmotiEffLibRecognizer

            self.torch, self.F = torch, F
            self.dev = device or _auto_device()
            self.rec = EmotiEffLibRecognizer(engine="torch", model_name="enet_b0_8_va_mtl",
                                             device=self.dev)
            self.rec.model.half()
            self.size = self.rec.img_size
            self.mean = torch.tensor(self.rec.mean, device=self.dev).view(1, 3, 1, 1)
            self.std = torch.tensor(self.rec.std, device=self.dev).view(1, 3, 1, 1)
            self.ok = True
        except Exception as e:
            print(f"[fer] 不可用: {e}")

    def start(self):
        if not self.ok or self._thread is not None:
            return self
        self._thread = threading.Thread(target=self._loop, name="fer", daemon=True)
        self._thread.start()
        return self

    def _largest_face(self, frame):
        gray = self.cv2.cvtColor(frame, self.cv2.COLOR_BGR2GRAY)
        faces = self.cascade.detectMultiScale(gray, scaleFactor=1.15, minNeighbors=5,
                                             minSize=(self.face_min, self.face_min))
        if len(faces) == 0:
            return None
        x, y, w, h = max(faces, key=lambda f: f[2] * f[3])
        return frame[y:y + h, x:x + w]

    def _infer(self, face_bgr) -> dict[str, float]:
        rgb = self.cv2.cvtColor(face_bgr, self.cv2.COLOR_BGR2RGB)
        x = self.torch.from_numpy(rgb).to(self.dev).permute(2, 0, 1).float() / 255
        x = self.F.interpolate(x[None], size=(self.size, self.size), mode="bilinear",
                               align_corners=False)
        with self.torch.no_grad():
            feats = self.rec.model(((x - self.mean) / self.std).half()).float()
            _, scores = self.rec.classify_emotions(feats, logits=False)
        sc = np.asarray(scores).reshape(-1)[:8]
        probs = {k: 0.0 for k in LABEL7}
        for name, v in zip(EFF_CLASSES, sc):
            if name in EFF_MAP:
                probs[EFF_MAP[name]] += float(v)
        return normalize_probs(probs)

    def _loop(self):
        dt = 1.0 / self.fps
        while not self._stop.is_set():
            ok, frame = self.cap.read()
            if not ok:
                self._stop.wait(dt)
                continue
            try:
                face = self._largest_face(frame)
                if face is not None:
                    p = self._infer(face)
                    now = time.monotonic()
                    r = ModalityResult("face", p, now, now, extra={"face_frac": face.shape[0] / frame.shape[0]})
                    with self._lock:
                        self._result, self._ts = r, now
                else:
                    with self._lock:
                        self._result, self._ts = None, time.monotonic()
            except Exception as e:
                print(f"[fer] 推理失败: {e}")
            self._maybe_jpeg(frame)
            self._stop.wait(dt)

    def _maybe_jpeg(self, frame):
        """5fps 缩略图给仪表盘，编码成本很低，不影响识别的帧率。"""
        now = time.monotonic()
        if now - self._jpeg_ts < 0.2:
            return
        try:
            small = self.cv2.resize(frame, None, fx=0.5, fy=0.5)
            ok, buf = self.cv2.imencode(".jpg", small, [self.cv2.IMWRITE_JPEG_QUALITY, 70])
            if ok:
                with self._lock:
                    self._jpeg, self._jpeg_ts = buf.tobytes(), now
        except Exception:
            pass

    def latest_jpeg(self) -> bytes | None:
        with self._lock:
            return self._jpeg

    def get(self, max_age: float = 0.8) -> ModalityResult | None:
        with self._lock:
            if self._result is None or time.monotonic() - self._ts > max_age:
                return None
            return self._result

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        if self.ok:
            self.cap.release()
