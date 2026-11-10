# camera：视觉模块

摄像头 -> 人脸位置/距离 -> 眼球跟随 + 按距离换表情，输出交给 `head.HeadClient`。

| 文件 | 作用 |
|---|---|
| `vision.py` | MediaPipe FaceLandmarker，虹膜间距估距离 |
| `behavior.py` | 纯逻辑：视线映射、距离分区表情、受惊、眨眼、眼皮联动 |
| `track.py` | 本地窗口预览：`python -m camera.track [--viz] [--hfov 65] [--calibrate]` |
| `web.py` + `web.html` | Web 调试界面：`python -m camera.web --camera 2`，ROG 上用 `run_web.sh` |
| `hub_source.py` | 把视线和距离情绪提交给统一控制进程：`python -m camera.hub_source --camera 2`，不开串口 |
| `test_camera.py` | 不需要摄像头和硬件的单测 |

模型 `models/face_landmarker.task` 不在仓库里，下载命令见 `scripts/mimic.py`。
