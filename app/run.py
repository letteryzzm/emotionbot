"""主入口：装配感知 -> 决策 -> 表情/TTS 的闭环。

常用：
    python -m app.run                         # 笔记本麦克风 + 摄像头 + 本机扬声器
    python -m app.run --source udp            # T5 板推 16k PCM 过来
    python -m app.run --source file --wav demo.wav --loop
    python -m app.run --stub --sim            # 不加载任何模型，只调界面

任何一个硬件/模型缺失都会降级而不是崩溃：模型加载失败 -> 该模态记为缺失；
找不到 Pico -> 仿真模式；摄像头打不开 -> 只跑音频 + 文本。
"""
from __future__ import annotations

import argparse
import os
import signal
import sys
import threading
import time
from dataclasses import replace

from agent.composite import expression_vector
from agent.dialogue import reply
from agent.echo import EchoGate
from agent.head_bridge import HeadBridge
from agent.idle import IdleAnimator, mouth_pose
from agent.policy import ExpressionCommand, decide
from agent.state import EmotionStateTracker
from head.actuators import NAMES, rest_vector
from perception.audio_source import FileSource, MicSource, UdpPcmSource
from perception.pipeline import PerceptionEvent, PerceptionPipeline
from perception.types import LABEL7, normalize_probs

from .server import DashboardServer, StateStore


# ---------------------------------------------------------------- director
class Director:
    """25Hz 把「当前表情 + 眨眼 + 嘴形」合成 22 维向量，交给 head_bridge。"""

    def __init__(self, bridge: HeadBridge, store: StateStore, hz: float = 25.0):
        self.bridge = bridge
        self.store = store
        self.hz = hz
        self.vec = rest_vector()
        self.base = rest_vector()
        self.until = 0.0
        self.level = 0.0
        self.expression = {"name": "neutral", "intensity": 0.0, "reason": "待机"}
        self.idle = IdleAnimator()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def command(self, cmd: ExpressionCommand):
        self.base = cmd.vector
        self.until = time.monotonic() + cmd.duration
        self.expression = {"name": cmd.name, "intensity": cmd.intensity,
                           "reason": cmd.reason}

    def manual(self, name: str, intensity: float = 1.0):
        try:
            vec = expression_vector(name, intensity)
        except KeyError as e:
            print(f"[director] {e}")
            return
        self.command(ExpressionCommand(name, intensity, 4.0, vec, "手动指定"))

    def set_level(self, x: float):
        # TTS 播放线程按 30ms 块回调，块之间保留一点，避免嘴抖
        self.level = max(float(x), self.level * 0.6)

    def start(self):
        self.bridge.start()
        self._thread = threading.Thread(target=self._loop, name="director", daemon=True)
        self._thread.start()
        return self

    def _loop(self):
        dt = 1.0 / self.hz
        while not self._stop.is_set():
            now = time.monotonic()
            base = self.base if now < self.until else rest_vector()
            if now >= self.until and self.expression["name"] != "neutral":
                self.expression = {"name": "neutral", "intensity": 0.0, "reason": "回到待机"}
            v = self.idle.apply(base, now)
            if self.level > 0.02:
                v = mouth_pose(v, self.level)
                self.level *= 0.55
            else:
                self.level = 0.0
            self.vec = v
            self.bridge.set_target(v)
            self.store.update(head=[round(float(x), 4) for x in v],
                              expression=self.expression)
            self._stop.wait(dt)

    def rest(self):
        self.until = 0.0
        self.base = rest_vector()
        self.expression = {"name": "neutral", "intensity": 0.0, "reason": "已复位"}
        self.bridge.rest()

    def close(self):
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=1.0)
            self._thread = None
        self.bridge.close()


# ---------------------------------------------------------------- speaker
class Speaker:
    """单线程 TTS：只认最新一句话，避免排队把嘴型拖到几秒之后。"""

    def __init__(self, store: StateStore, gate: EchoGate, director: Director,
                 enabled: bool = True):
        self.store = store
        self.gate = gate
        self.director = director
        self.enabled = enabled
        self.player = None
        self.backend = "off"
        if enabled:
            try:
                from agent.tts import TTSPlayer, available_backend

                name = available_backend()
                if name == "none":
                    print("[tts] 没装 edge-tts / pyttsx3，机器人不会说话")
                    self.enabled = False
                else:
                    self.player = TTSPlayer()
                    self.backend = {"edge": "edge-tts", "espeak": "espeak-ng",
                                    "sapi": "SAPI"}.get(name, name)
            except Exception as e:
                print(f"[tts] 不可用: {e}")
                self.enabled = False
        self.q: "list[str]" = []
        self._failures = 0
        self._cv = threading.Condition()
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._loop, name="tts", daemon=True)

    def start(self):
        self._thread.start()
        return self

    def say(self, text: str):
        if not self.enabled or not text.strip():
            return
        with self._cv:
            self.q[:] = [text]  # 新回复覆盖旧回复
            self._cv.notify()

    def _loop(self):
        while not self._stop.is_set():
            with self._cv:
                while not self.q and not self._stop.is_set():
                    self._cv.wait(0.5)
                if self._stop.is_set():
                    return
                text = self.q.pop()
            self.store.update(speaking=True)
            self.gate.mute(1.0)  # 合成期间也先收音，避免半句话被切成一句
            try:
                self.player.speak(text, gate=self.gate, on_level=self.director.set_level)
                failures = 0
            except Exception as e:
                failures = getattr(self, "_failures", 0) + 1
                self._failures = failures
                print(f"[tts] 播放失败({failures}/3): {e}")
                if failures >= 3:  # 没声卡/没后端时别每句都刷屏
                    print("[tts] 连续失败，关闭语音输出（表情照常）")
                    self.enabled = False
            finally:
                self.store.update(speaking=False)

    def close(self):
        self._stop.set()
        with self._cv:
            self._cv.notify_all()


# ---------------------------------------------------------------- stubs
class _StubASR:
    """--stub：按脚本轮播句子，用来单独调界面和策略，不需要显卡和模型。"""

    SCRIPT = [("今天特别开心", "happy"), ("太好了，又要加班", "neutral"),
              ("烦死了，真的受不了", "angry"), ("我有点担心明天的面试", "fear")]

    def __init__(self):
        self.i = 0

    def transcribe(self, wav):
        text, _ = self.SCRIPT[self.i % len(self.SCRIPT)]
        self.i += 1
        return text, None


class _StubSER:
    def __init__(self):
        self.i = 0

    def infer(self, wav):
        labels = ["happy", "sad", "angry", "fear"]
        p = {k: 0.05 for k in LABEL7}
        p[labels[self.i % len(labels)]] = 0.7
        self.i += 1
        return normalize_probs(p)


class _StubText:
    def infer(self, text):
        from perception.text_emotion import keyword_probs

        return keyword_probs(text), "keyword"


class LoopSource:
    """把 FileSource 无限循环，演示时可以一直放着。"""

    def __init__(self, inner, gap: float = 0.6):
        self.inner, self.gap = inner, gap
        self.sr = inner.sr

    def chunks(self):
        while True:
            yield from self.inner.chunks()
            time.sleep(self.gap)


# ---------------------------------------------------------------- helpers
def _try(label: str, fn):
    try:
        return fn()
    except Exception as e:
        print(f"[{label}] 加载失败，按缺失模态处理: {e}")
        return None


def _device_name() -> str:
    try:
        import torch

        if torch.cuda.is_available():
            return torch.cuda.get_device_name(0)
    except Exception:
        pass
    return "CPU"


def _source(args):
    if args.source == "mic":
        return MicSource(sr=16000, device=args.mic_device)
    if args.source == "udp":
        return UdpPcmSource(port=args.udp_port)
    if args.source == "file":
        if not args.wav:
            raise SystemExit("--source file 需要 --wav 路径")
        src = FileSource(args.wav, realtime=args.realtime)
        return LoopSource(src) if args.loop else src
    if args.source == "none":
        return None
    raise SystemExit(f"未知音源 {args.source}")


def _models(args):
    if args.stub:
        print("[models] stub 模式：不加载任何模型")
        return _StubASR(), _StubSER(), _StubText()
    from perception.asr_ser import SenseVoice
    from perception.ser import Emotion2Vec
    from perception.text_emotion import TextEmotion

    dev = None if args.device == "auto" else args.device
    asr = None if args.no_asr else _try("asr", lambda: SenseVoice(device=dev, model_dir=args.sv_dir))
    ser = None if args.no_ser else _try("ser", lambda: Emotion2Vec(device=dev, model_dir=args.e2v_dir))
    text = None if args.no_text else _try(
        "text", lambda: TextEmotion(api_key=args.ter_key or os.environ.get("DASHSCOPE_API_KEY", "")))
    return asr, ser, text


def _camera(args):
    if args.no_face:
        return None
    from perception.fer import CameraFER

    cam = CameraFER(camera=args.camera, fps=args.fer_fps, device=args.fer_device)
    if not cam.ok:
        return None
    return cam


def build_record(ev: PerceptionEvent, cmd: ExpressionCommand) -> dict:
    per = {}
    for m, d in (ev.fusion.per_modality or {}).items():
        probs = d.get("probs", d) if isinstance(d, dict) else d
        per[m] = {"probs": probs,
                  "label": max(probs, key=probs.get),
                  "confidence": float(d.get("confidence", max(probs.values()))
                                      if isinstance(d, dict) else max(probs.values()))}
    return {
        "t": time.time(),
        "asr_text": ev.asr_text,
        "fusion": {"label": ev.fusion.label, "confidence": ev.fusion.confidence,
                   "conflict": ev.fusion.conflict, "missing": ev.fusion.missing,
                   "probs": ev.fusion.probs,
                   "valence": ev.estimate.valence, "arousal": ev.estimate.arousal},
        "per_modality": per,
        "expression": {"name": cmd.name, "intensity": cmd.intensity,
                       "reason": cmd.reason},
        "latency_ms": round(ev.latency_ms, 1),
        "sources": ev.sources,
    }


# ---------------------------------------------------------------- main
def parse_args(argv=None):
    p = argparse.ArgumentParser(description="EmotionBot 实时闭环")
    p.add_argument("--source", choices=["mic", "udp", "file", "none"], default="mic")
    p.add_argument("--wav", help="--source file 的 wav 路径")
    p.add_argument("--realtime", action="store_true", help="按真实时间播放 wav")
    p.add_argument("--loop", action="store_true", help="循环播放 wav")
    p.add_argument("--udp-port", type=int, default=8770)
    p.add_argument("--mic-device", default=None)
    p.add_argument("--camera", type=int, default=0)
    p.add_argument("--no-face", action="store_true")
    p.add_argument("--no-head", action="store_true", help="不连 Pico（等同 --sim）")
    p.add_argument("--sim", action="store_true")
    p.add_argument("--no-tts", action="store_true")
    p.add_argument("--no-asr", action="store_true")
    p.add_argument("--no-ser", action="store_true")
    p.add_argument("--no-text", action="store_true")
    p.add_argument("--stub", action="store_true", help="不加载模型，用假数据调界面")
    p.add_argument("--device", default="auto", help="auto|cuda|cpu")
    p.add_argument("--fer-device", default=None)
    p.add_argument("--fer-fps", type=float, default=8.0)
    p.add_argument("--sv-dir", default=None, help="SenseVoiceSmall 本地目录")
    p.add_argument("--e2v-dir", default=None, help="emotion2vec 本地目录")
    p.add_argument("--ter-key", default=None, help="DashScope API key（可留空用关键词）")
    p.add_argument("--ports", default=None, help="Pico 串口，如 COM5,COM6,COM7")
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=int, default=8000)
    p.add_argument("--no-dashboard", action="store_true")
    return p.parse_args(argv)


def main(argv=None) -> int:
    # Windows 控制台默认 GBK，遇到特殊字符会直接抛 UnicodeEncodeError
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    args = parse_args(argv)
    store = StateStore()
    gate = EchoGate()
    ports = [s.strip() for s in args.ports.split(",")] if args.ports else None

    bridge = HeadBridge(sim=args.sim or args.no_head, ports=ports)
    director = Director(bridge, store).start()
    speaker = Speaker(store, gate, director, enabled=not args.no_tts).start()

    asr, ser, text = _models(args)
    face = _camera(args)
    tracker = EmotionStateTracker()

    store.update(status={
        "device": _device_name(),
        "head": "sim" if bridge.sim else "Pico",
        "head_names": NAMES,
        "tts": speaker.backend,
        "camera": bool(face),
        "asr": bool(asr), "ser": bool(ser), "text": bool(text),
    })

    def on_result(ev: PerceptionEvent):
        # 时序平滑：单句抖动不立刻换表情；矛盾句透传，保持 demo 的即时反应
        ev = replace(ev, fusion=tracker.update(ev.fusion))
        cmd = decide(ev.fusion)
        director.command(cmd)
        record = build_record(ev, cmd)
        store.add_event(record)
        flag = " [矛盾]" if ev.fusion.conflict else ""
        print(f"[event] {ev.asr_text or '(无文本)'} | {ev.fusion.label} "
              f"{ev.fusion.confidence:.2f}{flag} | {cmd.name} | {ev.latency_ms:.0f}ms")
        if cmd.is_active:
            speaker.say(reply(ev.fusion))

    def say(text: str):
        print(f"[say] {text}")
        speaker.say(text)

    server = None
    if not args.no_dashboard:
        server = DashboardServer(
            store, host=args.host, port=args.port,
            jpeg_provider=(face.latest_jpeg if face is not None else None),
            on_rest=director.rest,
            on_expression=lambda n, i: director.manual(n, i),
            on_say=say,
        ).start()

    pipeline = None
    source = _source(args)
    if source is not None:
        pipeline = PerceptionPipeline(source, asr=asr, ser=ser, text=text, face=face,
                                      echo_gate=gate, on_result=on_result).start()

    print("[run] 就绪，Ctrl+C 退出")
    try:
        while True:
            time.sleep(0.5)
    except KeyboardInterrupt:
        print("\n[run] 退出中…")

    # 退出：先停感知，再复位机器头，最后关界面
    if pipeline is not None:
        pipeline.stop()
    speaker.close()
    if server is not None:
        server.stop()
    director.rest()
    time.sleep(0.4)
    director.close()
    return 0


if __name__ == "__main__":
    signal.signal(signal.SIGINT, signal.default_int_handler)
    sys.exit(main())
