"""T5 语音交互：板子麦克风 → 端点检测 → ASR → 大模型 → 表情 + TTS → 板子喇叭。

板上 VAD 不上报（vad 恒为 0），所以说话起止在这里用能量判断。喇叭放音时板子 AEC 压不干净，
所以放音期间和放完后的 0.4 秒丢弃上行（半双工），不支持打断。

三个环节都是普通函数，方便测试时替换：
    asr(samples: float32[-1..1] 16 kHz) -> str
    chat(history: list[{"role","content"}]) -> str          # 返回 {"emotion":..,"reply":..} 的 JSON 文本
    tts(text: str) -> bytes                                  # 16 kHz s16le 单声道 PCM
"""
from __future__ import annotations

import json
import os
import queue
import re
import threading
import time
import urllib.request
from collections import deque

import numpy as np

from . import t5_eb2 as eb

FRAME_MS = 20
PRE_ROLL_FRAMES = 15            # 说话开始前保留 300 ms
END_SILENCE_FRAMES = 30         # 静音 600 ms 判定说完
MIN_SPEECH_FRAMES = 12          # 太短的当噪声（240 ms）
MAX_SPEECH_FRAMES = 750         # 最长 15 s
START_FRAMES = 3                # 连续 60 ms 超阈值才算开始
TAIL_MUTE_S = 0.4
LEAD_S = 0.5                    # 下发 PCM 时比实时提前的量，板子环形缓冲是 1 s

PERSONA = (
    "你是桌面表情机器人“小表”，通过喇叭和用户语音聊天。回答要口语化、温和、简短，最多两句话、总共不超过 25 个字，不用表情符号、"
    "列表和 markdown。只输出一个 JSON：{\"emotion\":\"<neutral|happy|sad|angry|surprise|fear|disgust 之一>\","
    "\"reply\":\"<要说的话>\"}，emotion 是你说这句话时应该摆出的表情。"
)


# ---------- 端点检测 ----------
class Endpointer:
    """逐帧喂 20 ms PCM，说完一句返回 float32 样本，否则返回 None。"""

    def __init__(self, min_rms=250.0, ratio=3.0):
        self.min_rms, self.ratio = min_rms, ratio
        self.floor = 80.0
        self.pre = deque(maxlen=PRE_ROLL_FRAMES)
        self.frames: list[bytes] = []
        self.talking = False
        self.hot = 0
        self.quiet = 0
        self.pre_len = 0
        self.rms = 0.0

    def threshold(self):
        return max(self.min_rms, self.floor * self.ratio)

    def reset(self):
        self.pre.clear(); self.frames = []; self.talking = False; self.hot = self.quiet = 0

    def feed(self, pcm: bytes):
        a = np.frombuffer(pcm, "<i2").astype(np.float32)
        rms = float(np.sqrt((a * a).mean())) if len(a) else 0.0
        self.rms = rms
        loud = rms > self.threshold()
        if not self.talking:
            if not loud:                       # 只在安静时更新底噪，慢速跟随
                self.floor += 0.05 * (rms - self.floor)
            self.pre.append(pcm)
            self.hot = self.hot + 1 if loud else 0
            if self.hot >= START_FRAMES:
                self.talking = True
                self.frames = list(self.pre)
                self.pre_len = len(self.frames)
                self.quiet = 0
            return None
        self.frames.append(pcm)
        self.quiet = 0 if loud else self.quiet + 1
        if self.quiet >= END_SILENCE_FRAMES or len(self.frames) >= MAX_SPEECH_FRAMES:
            speech = len(self.frames) - self.pre_len - self.quiet + START_FRAMES   # 真正说话的帧数
            frames, self.frames, self.talking, self.hot, self.quiet = self.frames, [], False, 0, 0
            self.pre.clear()
            if speech < MIN_SPEECH_FRAMES:
                return None
            return np.frombuffer(b"".join(frames), "<i2").astype(np.float32) / 32768.0
        return None


# ---------- 云端接口 ----------
def _key(path="~/.config/minimax/api_key"):
    return open(os.path.expanduser(path)).read().strip()


def minimax_chat(key, model="MiniMax-Text-01", base="https://api.minimaxi.com/v1"):
    def chat(history):
        body = {"model": model, "max_tokens": 200, "temperature": 0.8,
                "messages": [{"role": "system", "content": PERSONA}] + history}
        r = urllib.request.Request(base + "/chat/completions", json.dumps(body).encode(),
                                   {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(r, timeout=30))
        return d["choices"][0]["message"]["content"]
    return chat


def minimax_tts(key, voice="Chinese (Mandarin)_Gentle_Youth", model="speech-2.6-turbo",
                base="https://api.minimaxi.com/v1", speed=1.1):
    def tts(text):
        body = {"model": model, "text": text, "stream": False,
                "voice_setting": {"voice_id": voice, "speed": speed, "vol": 1.0, "pitch": 0},
                "audio_setting": {"sample_rate": 16000, "format": "pcm", "channel": 1}}
        r = urllib.request.Request(base + "/t2a_v2", json.dumps(body).encode(),
                                   {"Authorization": "Bearer " + key, "Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(r, timeout=30))
        if d["base_resp"]["status_code"] != 0:
            raise RuntimeError(f"tts: {d['base_resp']}")
        return bytes.fromhex(d["data"]["audio"])
    return tts


def sensevoice(model_dir, threads=4):
    import sherpa_onnx
    rec = sherpa_onnx.OfflineRecognizer.from_sense_voice(
        model=os.path.join(model_dir, "model.int8.onnx"), tokens=os.path.join(model_dir, "tokens.txt"),
        num_threads=threads, use_itn=True, language="zh")

    def asr(samples):
        s = rec.create_stream()
        s.accept_waveform(16000, samples)
        rec.decode_stream(s)
        return re.sub(r"<\|[^|]*\|>", "", s.result.text).strip()
    return asr


def split_sentences(text, min_len=8, max_len=40):
    """按标点切成几段：太短的并到下一段，太长的在逗号处再切。第一段越短，首音越快。"""
    parts = [p for p in re.findall(r"[^。！？!?；;，,、…\n]+[。！？!?；;，,、…]*", text) if p.strip()]
    out, cur = [], ""
    for p in parts:
        cur += p
        if len(cur) >= min_len:
            out.append(cur); cur = ""
    if cur:
        if out and len(cur) < min_len:
            out[-1] += cur
        else:
            out.append(cur)
    return out or [text]


def parse_reply(text):
    """从大模型输出里取 (emotion, reply)；模型没按 JSON 回时，整段当回复、表情用 neutral。"""
    m = re.search(r"\{.*\}", text, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            emo = d.get("emotion", "neutral")
            return (emo if emo in eb.EMOTIONS else "neutral"), str(d.get("reply", "")).strip()
        except (ValueError, AttributeError):
            pass
    return "neutral", re.sub(r"\s+", " ", text).strip()


# ---------- 主体 ----------
class VoiceAgent:
    def __init__(self, asr, chat, tts, stream=None, max_history=8, sink=None, on_emotion=None,
                 tail_mute=None, wake=None):
        """stream：T5 串口（下发 PCM_DOWN、发 EMOTION）。
        本地麦克风/喇叭模式不给 stream，改给 sink(640 字节 PCM) 播放、on_emotion(名字) 显示表情，
        输入用 feed(640 字节 PCM)。wake：唤醒词，None 表示不需要。"""
        self.asr, self.chat, self.tts = asr, chat, tts
        self.stream = stream
        self.sink, self.on_emotion = sink, on_emotion
        self.tail_mute = tail_mute
        self.wake, self.awake_until = wake, 0.0
        self.emotion = "neutral"
        self.ep = Endpointer()
        self.history: list[dict] = []
        self.max_history = max_history
        self.mute_until = 0.0
        self.busy = False
        self.turns: list[dict] = []          # 每轮的文字和各环节耗时
        self.status = "idle"
        self.error = None
        self.frames_in = 0
        self._q: deque = deque()
        self._cv = threading.Condition()
        self._seq = 0
        self._stop = False
        threading.Thread(target=self._worker, daemon=True).start()

    # 串口线程里调用，必须很快
    def on_packet(self, p):
        if p.type == eb.T_PCM_UP:
            self.feed(eb.parse_pcm_up(p.payload)[2])

    def feed(self, pcm):
        self.frames_in += 1
        if time.time() < self.mute_until or self.busy:
            self.ep.reset()
            return
        speech = self.ep.feed(pcm)
        self.status = "listening…" if self.ep.talking else "idle"
        if speech is not None:
            with self._cv:
                self._q.append((speech, time.time()))
                self._cv.notify()

    def say(self, text):
        """网页输入框用：把一段文字当成用户说的话，跳过识别，走对话 → 表情 → 合成 → 喇叭。"""
        text = text.strip()
        if not text:
            return
        with self._cv:
            self._q.append((text, time.time() + END_SILENCE_FRAMES * FRAME_MS / 1000))
            self._cv.notify()

    def close(self):
        self._stop = True
        with self._cv:
            self._cv.notify()

    def _worker(self):
        while not self._stop:
            with self._cv:
                while not self._q and not self._stop:
                    self._cv.wait()
                if self._stop:
                    return
                speech, t_end = self._q.popleft()
            try:
                self.busy = True
                self._turn(speech, t_end)
                self.error = None        # 上一轮的错误别一直挂在网页上
            except Exception as e:       # noqa: BLE001  一轮失败不能让整个线程死掉，原因放进状态给网页看
                self.error = f"{type(e).__name__}: {e}"
                self.status = "error"
            finally:
                self.busy = False
                self.ep.reset()
                self.mute_until = max(self.mute_until, time.time() + self._tail())

    def _turn(self, speech, t_end):
        if isinstance(speech, str):          # 文字输入，不经过识别
            text, turn = speech, {"audio_s": 0, "asr_s": 0}
            turn["text"] = text
        else:
            turn = {"audio_s": round(len(speech) / 16000, 2)}
            self.status = "识别中"
            t = time.time()
            text = self.asr(speech)
            turn["text"] = text
            turn["asr_s"] = round(time.time() - t, 2)
        if not text:
            return
        if self.wake and not isinstance(speech, str):
            now = time.time()
            if self.wake not in text and now > self.awake_until:
                turn["ignored"] = "没有唤醒词"
                self.turns.append(turn)
                self.status = "idle"
                return
            self.awake_until = now + 25         # 唤醒后 25 秒内可以连续说话
        self.history.append({"role": "user", "content": text})
        self.history = self.history[-self.max_history:]
        self.status = "思考中"
        t = time.time()
        raw = self.chat(self.history)
        emotion, reply = parse_reply(raw)
        turn["emotion"], turn["reply"] = emotion, reply
        turn["llm_s"] = round(time.time() - t, 2)
        if not reply:
            return
        self.history.append({"role": "assistant", "content": reply})
        self.emotion = emotion
        try:
            if self.on_emotion:
                self.on_emotion(emotion)
            elif self.stream:
                self.stream.command(f"EMOTION {emotion}")
        except Exception as e:           # noqa: BLE001  表情失败不影响说话
            turn["emotion_error"] = str(e)
        self.status = "合成中"
        # 生产者线程按句合成，主线程边收边播：第一句好了就开口，后面的句子在播放期间合成
        sentences = split_sentences(reply)
        ready: "queue.Queue" = queue.Queue()
        t = time.time()

        def produce():
            for sent in sentences:
                try:
                    ready.put(self.tts(sent))
                except Exception as e:   # noqa: BLE001  合成失败要让主线程知道，不能悄悄少说一句
                    ready.put(e)
                    return
            ready.put(None)
        threading.Thread(target=produce, daemon=True).start()
        t_first, total, first = None, 0, True
        while True:
            item = ready.get()
            if item is None:
                break
            if isinstance(item, Exception):
                raise item
            if first:
                turn["tts_s"] = round(time.time() - t, 2)      # 第一句合成好的耗时
                self.status = "说话中"
                first = False
            total += len(item)
            tf = self._play(item)
            t_first = t_first or tf
        pcm = b"\0" * total
        # 用户说完（静音判定那一刻往前 600 ms 才是真正说完）到喇叭收到第一包
        turn["first_audio_after_speech_end_s"] = round(t_first - t_end + END_SILENCE_FRAMES * FRAME_MS / 1000, 2)
        turn["reply_audio_s"] = round(len(pcm) / 32000, 2)
        self.turns.append(turn)
        self.turns = self.turns[-20:]
        self.status = "idle"

    def _play(self, pcm):
        """按实时节奏下发 PCM_DOWN，返回第一包发出的时刻。"""
        size = 640
        t0 = time.time()
        first = None
        n = 0
        for i in range(0, len(pcm), size):
            chunk = pcm[i:i + size]
            if len(chunk) < size:
                chunk += b"\0" * (size - len(chunk))
            self._seq += 1
            if self.sink:
                self.sink(chunk)
            else:
                self.stream.write(eb.pack(eb.T_PCM_DOWN, self._seq, chunk))
            if first is None:
                first = time.time()
            n += 1
            wait = t0 + n * FRAME_MS / 1000 - LEAD_S - time.time()
            if wait > 0:
                time.sleep(wait)
        self.mute_until = t0 + n * FRAME_MS / 1000 + self._tail()
        # 等喇叭放完，期间上行会被丢弃
        time.sleep(max(0, self.mute_until - time.time()))
        return first or time.time()

    def _tail(self):
        return TAIL_MUTE_S if self.tail_mute is None else self.tail_mute

    def snapshot(self):
        return {"status": self.status, "error": self.error, "frames_in": self.frames_in,
                "floor": round(self.ep.floor), "threshold": round(self.ep.threshold()), "rms": round(self.ep.rms),
                "emotion": self.emotion, "awake": self.wake is None or time.time() < self.awake_until,
                "turns": self.turns[-5:]}
