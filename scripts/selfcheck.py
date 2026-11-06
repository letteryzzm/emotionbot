"""现场排障第一条命令：把环境一次打印清楚。

    python scripts/selfcheck.py

检查项：Python / torch / CUDA / 显存 / 依赖包 / 模型文件 / 串口 / 摄像头 / 麦克风 / 磁盘。
任何一项失败都只打印，不中断，最后给一个汇总。退出码 = 失败项数量（上限 99）。
"""
from __future__ import annotations

import importlib
import os
import shutil
import socket
import sys
import traceback
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FAILS: list[str] = []


def ok(msg):
    print(f"  [ OK ] {msg}")


def warn(msg):
    print(f"  [WARN] {msg}")


def bad(msg):
    FAILS.append(msg)
    print(f"  [FAIL] {msg}")


def section(title):
    print(f"\n=== {title} ===")


def check_python():
    section("Python")
    ok(f"{sys.version.split()[0]} @ {sys.executable}")
    if sys.version_info[:2] not in ((3, 11), (3, 12)):
        warn("项目要求 >=3.11,<3.13，当前版本可能导致 funasr/onnx 安装失败")


def check_torch():
    section("Torch / CUDA")
    try:
        import torch
    except Exception as e:
        bad(f"torch 未安装: {e}")
        return
    ok(f"torch {torch.__version__}")
    if not torch.cuda.is_available():
        warn("CUDA 不可用，将退回 CPU（延迟会明显变高）")
        return
    try:
        i = torch.cuda.current_device()
        name = torch.cuda.get_device_name(i)
        total = torch.cuda.get_device_properties(i).total_memory / 2**30
        ok(f"GPU {name}，显存 {total:.1f} GB")
        if total < 5.5:
            warn("显存偏小：建议关掉本地 LLM，TER 走 API")
    except Exception as e:
        bad(f"读取 GPU 信息失败: {e}")


def check_packages():
    section("依赖")
    # 修一下 Windows 坏证书导致的 ssl 报错，否则 edge_tts/aiohttp 导入会误报
    try:
        sys.path.insert(0, str(ROOT))
        from agent.tts import ensure_ssl_context

        if not ensure_ssl_context():
            warn("SSL 上下文不可用，在线 TTS/HTTPS 可能失败")
    except Exception:
        pass
    required = {"numpy", "serial"}
    mods = {
        "cv2": "摄像头", "torch": "模型",
        "funasr": "SenseVoice/emotion2vec", "emotiefflib": "人脸情绪",
        "sounddevice": "麦克风", "miniaudio": "TTS 解码",
        "edge_tts": "在线 TTS", "pyttsx3": "离线 TTS",
    }
    for mod in list(required) + list(mods):
        try:
            m = importlib.import_module(mod)
            ok(f"{mod} {getattr(m, '__version__', '')}".strip())
        except Exception as e:
            why = mods.get(mod, "必需")
            (bad if mod in required else warn)(f"{mod} 未安装（{why}）: {e}")


def default_model_dir() -> Path:
    # 开发机习惯放 D 盘；Linux 演示机没有 D 盘，默认放用户目录
    if sys.platform == "win32":
        return Path("D:/emo_models")
    return Path.home() / "emo_models"


def model_root() -> Path:
    env = os.environ.get("EMOBOT_MODEL_DIR")
    if env:
        return Path(env)
    for cand in (default_model_dir(), ROOT / "models", Path.home() / "emo_models"):
        if cand.exists():
            return cand
    return default_model_dir()


def check_models():
    section("模型文件")
    root = model_root()
    print(f"  模型根目录: {root}")
    wanted = {
        "SenseVoiceSmall": "ASR + 语音情感标签",
        "emotion2vec_plus_large": "语音情感概率（EMOBOT_E2V 可换 base）",
    }
    for name, why in wanted.items():
        p = root / name
        if p.exists():
            size = sum(f.stat().st_size for f in p.rglob("*") if f.is_file()) / 2**20
            ok(f"{name} ({size:.0f} MB) — {why}")
        else:
            warn(f"{name} 不存在 — {why}；有网时可留空让 FunASR 自动下载")
    # EmotiEffNet 权重由 emotiefflib 自己管理
    try:
        from emotiefflib.facial_analysis import EmotiEffLibRecognizer  # noqa: F401
        ok("emotiefflib 可导入（权重首次使用自动下载）")
    except Exception as e:
        warn(f"emotiefflib 不可用: {e}")


def check_serial():
    section("串口（Pico）")
    try:
        from serial.tools import list_ports
    except Exception as e:
        bad(f"pyserial 不可用: {e}")
        return
    ports = list(list_ports.comports())
    if not ports:
        warn("没有枚举到任何串口，检查 USB 线和驱动")
        return
    for p in ports:
        print(f"  {p.device:12s} {p.description}  VID:PID={p.vid}:{p.pid}")
    try:
        import serial
    except Exception:
        return
    for p in ports:
        if p.vid is None:
            # 蓝牙串口之类，不可能是 Pico，试探只会白等超时
            print(f"           -> 跳过（无 USB VID，不是 Pico）")
            continue
        try:
            s = serial.Serial(p.device, 115200, timeout=0.3, write_timeout=0.5)
            s.reset_input_buffer()
            role = None
            for _ in range(3):
                s.write(b"?\n")
                line = s.readline().decode(errors="ignore").strip()
                if line.startswith("ROLE "):
                    role = line.split()[1]
                    break
            s.close()
            if role:
                ok(f"{p.device} -> ROLE {role}")
            else:
                warn(f"{p.device} 无 ROLE 应答（不是 Pico 或固件没跑）")
        except Exception as e:
            warn(f"{p.device} 打不开: {e}")
            if sys.platform != "win32" and "denied" in str(e).lower():
                warn("当前用户不在 dialout 组：sudo usermod -aG dialout $USER 后重新登录")


def check_camera():
    section("摄像头")
    try:
        import cv2
    except Exception as e:
        bad(f"opencv 不可用: {e}")
        return
    cap = cv2.VideoCapture(0)
    try:
        if not cap.isOpened():
            bad("打不开摄像头 0（被其他程序占用？）")
            return
        okret, frame = cap.read()
        if okret:
            h, w = frame.shape[:2]
            ok(f"摄像头 0: {w}x{h}")
        else:
            warn("摄像头打开了但读不到帧")
    finally:
        cap.release()


def check_mic():
    section("麦克风")
    try:
        import sounddevice as sd
    except Exception as e:
        bad(f"sounddevice 不可用: {e}")
        return
    try:
        devices = sd.query_devices()
        ins = [d for d in devices if d.get("max_input_channels", 0) > 0]
        if not ins:
            bad("没有输入设备")
        for i, d in enumerate(ins[:6]):
            ok(f"{d['name'][:40]} ({d['default_samplerate']:.0f} Hz)")
        try:
            sd.check_input_settings(samplerate=16000, channels=1, dtype="float32")
            ok("16kHz 单声道 float32 可用")
        except Exception as e:
            warn(f"16kHz 单声道不可直接使用: {e}")
        outs = [d for d in devices if d.get("max_output_channels", 0) > 0]
        try:
            default_out = sd.query_devices(kind="output")["name"]
            ok(f"默认输出: {default_out[:40]}（可用 EMOBOT_AUDIO_OUT 指定）")
        except Exception:
            warn("没有默认输出设备，TTS 会没声音")
        if outs:
            ok(f"输出设备 {len(outs)} 个")
    except Exception as e:
        bad(f"枚举麦克风失败: {e}")


def check_network():
    section("外网 / 镜像")
    for host, port in [("modelscope.cn", 443), ("hf-mirror.com", 443),
                       ("dashscope.aliyuncs.com", 443)]:
        try:
            with socket.create_connection((host, port), timeout=3):
                ok(f"{host}:{port} 可达")
        except Exception as e:
            warn(f"{host}:{port} 不可达（{e}）— 需要提前下好模型/走离线路径")


def check_disk():
    section("磁盘")
    if sys.platform == "win32":
        paths = [Path("C:/"), Path("D:/")]
    else:
        paths = [Path("/"), Path(ROOT.anchor)]
    seen = set()
    for p in paths:
        if not p.exists() or str(p) in seen:
            continue
        seen.add(str(p))
        try:
            total, used, free = shutil.disk_usage(p)
            ok(f"{p} 剩余 {free / 2**30:.1f} GB")
        except OSError as e:
            warn(f"{p} 读取失败: {e}")


def main() -> int:
    # 麦克风设备名里常有 ® / ™ 之类的字符，GBK 控制台会直接抛异常
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass
    print("EmotionBot 环境自检")
    for fn in (check_python, check_torch, check_packages, check_models, check_serial,
               check_camera, check_mic, check_network, check_disk):
        try:
            fn()
        except Exception:
            bad(f"{fn.__name__} 异常:\n{traceback.format_exc(limit=2)}")
    print("\n=== 汇总 ===")
    if FAILS:
        print(f"{len(FAILS)} 项失败：")
        for f in FAILS:
            print(f" - {f}")
        return min(len(FAILS), 99)
    print("全部通过，可以开跑。")
    return 0


if __name__ == "__main__":
    sys.exit(main())
