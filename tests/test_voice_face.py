"""语音接到脸上：表情层不带眼球，下巴跟音量，视觉观测转换。不碰硬件。"""
import struct

from camera.hub_source import obs_from_state
from head.voice_face import JAW_MAX, VoiceFace, emotion_pose


class Hub:
    def __init__(self):
        self.sent = []

    def intent(self, source, values, ttl):
        self.sent.append((source, values, ttl))
        return True

    def clear(self, source):
        self.sent.append((source, None, None))
        return True


def rig():
    now = [10.0]
    hub = Hub()
    return VoiceFace(hub, clock=lambda: now[0], start=False), hub, now


def tone(level):
    return struct.pack("<320h", *([level, -level] * 160))


def test_every_voice_emotion_has_a_pose_without_gaze():
    for name in ("happy", "sad", "angry", "surprise", "fear", "disgust"):
        pose = emotion_pose(name)
        assert pose and not {"LR", "UD"} & set(pose), name
    assert emotion_pose("neutral") == {} and emotion_pose("不存在") == {}


def test_jaw_waits_for_the_sound_not_the_write():
    f, hub, now = rig()
    for _ in range(25):                 # 0.5 秒的音频一下子写进播放器
        f.audio(tone(6000))
    f.tick()
    assert not hub.sent
    now[0] += 0.3
    f.tick()
    lips = [v for s, v, _ in hub.sent if s == "lips"]
    assert len(lips) == 1 and 0 < lips[0]["JL"] <= JAW_MAX and lips[0]["JL"] == lips[0]["JR"]
    assert f.timeline, "后半段还没到播放时刻"


def test_jaw_closes_on_silence():
    f, _, _ = rig()
    f.audio(tone(6000))
    for _ in range(40):
        f.audio(tone(0))
    assert f.jaw < 0.01


def test_emotion_goes_out_before_speech_and_neutral_hands_back_to_vision():
    f, hub, now = rig()
    f.on_emotion("angry")
    f.tick()
    assert hub.sent[0][0] == "dialog" and hub.sent[0][1]
    hub.sent.clear()
    f.on_emotion("neutral")
    f.tick()
    assert hub.sent == [("dialog", None, None)]


def test_camera_web_state_becomes_observation():
    assert obs_from_state({"face": False, "x": None}, 1.0) is None
    o = obs_from_state({"face": True, "x": 0.2, "y": -0.1, "dist": 0.8, "ipd": 50}, 1.0)
    assert (o.x, o.y, o.dist_m, o.t) == (0.2, -0.1, 0.8, 1.0)
