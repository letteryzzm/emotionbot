import numpy as np

from perception.pipeline import PerceptionPipeline
from perception.types import LABEL7, ModalityResult


def probs(label, peak=0.8):
    p = {k: (1 - peak) / 6 for k in LABEL7}
    p[label] = peak
    return p


class FakeASR:
    def __init__(self, text="今天特别开心", label="happy"):
        self.text, self.label = text, label

    def transcribe(self, wav):
        return self.text, probs(self.label)


class FakeSER:
    def __init__(self, label="happy"):
        self.label = label

    def infer(self, wav):
        return probs(self.label)


class FakeText:
    def __init__(self, label="happy"):
        self.label = label

    def infer(self, text):
        return probs(self.label), "fake"


class ListSource:
    sr = 16000

    def __init__(self, x):
        self.x = x

    def chunks(self):
        for i in range(0, len(self.x), 480):
            yield self.x[i:i + 480]


def signal():
    sr = 16000
    t = np.arange(int(sr * 1.0)) / sr
    tone = (0.2 * np.sin(2 * np.pi * 440 * t)).astype(np.float32)
    return np.concatenate([np.full(int(sr * 0.2), 1e-4, np.float32), tone,
                           np.full(int(sr * 0.8), 1e-4, np.float32)])


def make(asr=True, ser=True, text=True, gate=None):
    return PerceptionPipeline(
        ListSource(signal()),
        asr=FakeASR() if asr else None,
        ser=FakeSER() if ser else None,
        text=FakeText() if text else None,
        echo_gate=gate,
    )


def test_end_to_end_happy():
    p = make().start()
    ev = p.wait(timeout=5)
    p.stop()
    assert ev is not None
    assert ev.asr_text == "今天特别开心"
    assert ev.fusion.label == "happy"
    assert ev.estimate.confidence > 0.5
    assert ev.latency_ms >= 0


def test_conflict_is_flagged():
    p = PerceptionPipeline(ListSource(signal()), asr=FakeASR(label="angry"),
                           ser=FakeSER(label="angry"), text=FakeText(label="happy")).start()
    ev = p.wait(timeout=5)
    p.stop()
    assert ev.fusion.conflict
    assert ev.fusion.label == "angry"


def test_missing_models_still_produce_a_result():
    p = make(asr=False, ser=False, text=False).start()
    ev = p.wait(timeout=5)
    p.stop()
    assert ev is not None
    assert ev.fusion.label == "neutral"
    assert len(ev.fusion.missing) == 3


def test_echo_gate_drops_audio():
    from agent.echo import EchoGate

    gate = EchoGate()
    gate.mute(30)
    p = make(gate=gate).start()
    ev = p.wait(timeout=1.5)
    p.stop()
    assert ev is None
