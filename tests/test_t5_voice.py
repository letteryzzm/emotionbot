import time

import numpy as np

from head import t5_eb2 as eb
from head import t5_voice as v


def frame(amp, n=320, seed=0):
    rng = np.random.default_rng(seed)
    return (rng.standard_normal(n) * amp).astype("<i2").tobytes()


def run(ep, frames):
    out = []
    for f in frames:
        r = ep.feed(f)
        if r is not None:
            out.append(r)
    return out


def test_endpointer_finds_one_utterance_with_preroll():
    ep = v.Endpointer()
    frames = [frame(30, seed=i) for i in range(50)] + [frame(3000, seed=100 + i) for i in range(40)] \
        + [frame(30, seed=200 + i) for i in range(50)]
    out = run(ep, frames)
    assert len(out) == 1
    # 预录 15 帧（含触发的 3 帧）+ 其余说话 37 帧 + 静音 30 帧 = 82 帧
    assert len(out[0]) == 82 * 320


def test_endpointer_ignores_short_click_and_quiet():
    ep = v.Endpointer()
    frames = [frame(30, seed=i) for i in range(30)] + [frame(4000)] * 4 + [frame(30, seed=9)] * 60
    assert run(ep, frames) == []


def test_endpointer_adapts_to_noisy_room():
    ep = v.Endpointer()
    run(ep, [frame(200, seed=i) for i in range(400)])          # 持续的中等底噪
    assert ep.threshold() > 500                                 # 阈值跟着抬高
    assert run(ep, [frame(250, seed=i) for i in range(100)]) == []


def test_parse_reply():
    assert v.parse_reply('好的 {"emotion":"happy","reply":"你好呀"}') == ("happy", "你好呀")
    assert v.parse_reply('{"emotion":"???","reply":"嗯"}') == ("neutral", "嗯")
    assert v.parse_reply("直接说话") == ("neutral", "直接说话")


class FakeStream:
    def __init__(self):
        self.written, self.cmds = [], []

    def write(self, d):
        self.written.append(d)

    def command(self, t, timeout=2.0):
        self.cmds.append(t)
        return "OK", 1.0


def test_full_turn_with_fakes(monkeypatch):
    monkeypatch.setattr(v, "LEAD_S", 5.0)            # 测试里不用等真实时间
    monkeypatch.setattr(v, "TAIL_MUTE_S", 0.0)
    st = FakeStream()
    a = v.VoiceAgent(lambda s: "你好" if len(s) > 1000 else "", lambda h: '{"emotion":"happy","reply":"你好呀"}',
                     lambda t: b"\x01\x00" * 1600, stream=st)
    for f in [frame(30, seed=i) for i in range(40)] + [frame(3000, seed=50 + i) for i in range(40)] \
            + [frame(30, seed=90 + i) for i in range(40)]:
        a.on_packet(eb.Packet(eb.T_PCM_UP, 0, 1, eb.pack_pcm_up(1, 0, 0, f)[8:-2]))
    end = time.time() + 5
    while time.time() < end and not a.turns:
        time.sleep(0.02)
    assert a.turns and a.turns[0]["text"] == "你好" and a.turns[0]["emotion"] == "happy"
    assert st.cmds == ["EMOTION happy"]
    assert len(st.written) == 5                       # 3200 字节 = 5 个 640 字节包
    p, = eb.Parser().feed(st.written[0])[:1]
    assert p[1].type == eb.T_PCM_DOWN and len(p[1].payload) == 640
    assert a.history[-1] == {"role": "assistant", "content": "你好呀"}
    a.close()


def test_agent_drops_audio_while_speaking():
    a = v.VoiceAgent(lambda s: "x", lambda h: "", lambda t: b"")
    a.mute_until = time.time() + 10
    for i in range(80):
        a.on_packet(eb.Packet(eb.T_PCM_UP, 0, 1, eb.pack_pcm_up(1, 0, 0, frame(3000, seed=i))[8:-2]))
    assert not a._q and a.frames_in == 80
    a.close()


def test_say_skips_asr(monkeypatch):
    monkeypatch.setattr(v, "LEAD_S", 5.0)
    monkeypatch.setattr(v, "TAIL_MUTE_S", 0.0)
    st = FakeStream()
    def boom(_):
        raise AssertionError("ASR 不该被调用")
    a = v.VoiceAgent(boom, lambda h: '{"emotion":"sad","reply":"抱抱"}', lambda t: b"\x01\x00" * 640, stream=st)
    a.say("我今天有点难过")
    end = time.time() + 5
    while time.time() < end and not a.turns:
        time.sleep(0.02)
    assert a.turns[0]["text"] == "我今天有点难过" and st.cmds == ["EMOTION sad"] and len(st.written) == 2
    a.close()


def test_split_sentences():
    assert v.split_sentences("好的。") == ["好的。"]
    assert v.split_sentences("嗯，位置很重要。你想怎么调整呢？") == ["嗯，位置很重要。", "你想怎么调整呢？"]
    assert "".join(v.split_sentences("哇，这么多人！那现在是什么情况呢？")) == "哇，这么多人！那现在是什么情况呢？"


def _speak(a):
    for f in [frame(30, seed=i) for i in range(40)] + [frame(3000, seed=50 + i) for i in range(40)] \
            + [frame(30, seed=90 + i) for i in range(40)]:
        a.feed(f)


def _wait_turn(a, n=1):
    end = time.time() + 5
    while time.time() < end and len(a.turns) < n:
        time.sleep(0.02)


def test_local_sink_and_emotion_callback(monkeypatch):
    monkeypatch.setattr(v, "LEAD_S", 5.0)
    got, emo = [], []
    a = v.VoiceAgent(lambda s: "你好", lambda h: '{"emotion":"happy","reply":"你好呀"}', lambda t: b"\x01\x00" * 1600,
                     sink=got.append, on_emotion=emo.append, tail_mute=0.0)
    _speak(a)
    _wait_turn(a)
    assert emo == ["happy"] and len(got) == 5 and all(len(c) == 640 for c in got)
    a.close()


def test_wake_word_gates_speech_but_not_text(monkeypatch):
    monkeypatch.setattr(v, "LEAD_S", 5.0)
    heard = ["今天天气不错", "小表你好", "再说一句"]
    a = v.VoiceAgent(lambda s: heard.pop(0), lambda h: '{"emotion":"neutral","reply":"嗯"}', lambda t: b"\x01\x00" * 640,
                     sink=lambda c: None, tail_mute=0.0, wake="小表")
    _speak(a); _wait_turn(a, 1)
    assert a.turns[0].get("ignored") and "reply" not in a.turns[0]      # 没叫唤醒词，忽略
    time.sleep(0.1)
    _speak(a); _wait_turn(a, 2)
    assert a.turns[1]["reply"] == "嗯"                                   # 叫了唤醒词
    time.sleep(0.1)
    _speak(a); _wait_turn(a, 3)
    assert a.turns[2]["reply"] == "嗯"                                   # 25 秒内不用再叫
    a.close()
