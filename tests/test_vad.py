import numpy as np

from perception.vad import VADSegmenter

SR = 16000


def tone(sec, amp=0.2, f=440.0):
    t = np.arange(int(SR * sec)) / SR
    return (amp * np.sin(2 * np.pi * f * t)).astype(np.float32)


def silence(sec):
    return np.full(int(SR * sec), 1e-4, dtype=np.float32)


def feed(vad, x, step=480):
    out = []
    for i in range(0, len(x), step):
        out.extend(vad.push(x[i:i + step]))
    return out


def test_single_utterance_is_segmented():
    vad = VADSegmenter(sr=SR)
    x = np.concatenate([silence(0.3), tone(1.0), silence(0.8)])
    segs = feed(vad, x)
    assert len(segs) == 1
    assert 0.9 <= len(segs[0]) / SR <= 1.2


def test_two_utterances_are_separated():
    vad = VADSegmenter(sr=SR)
    x = np.concatenate([silence(0.3), tone(0.8), silence(0.8), tone(0.8), silence(0.8)])
    segs = feed(vad, x)
    assert len(segs) == 2


def test_pure_silence_yields_nothing():
    vad = VADSegmenter(sr=SR)
    assert feed(vad, silence(2.0)) == []


def test_flush_returns_pending_speech():
    vad = VADSegmenter(sr=SR)
    vad.push(tone(1.0))
    seg = vad.flush()
    assert seg is not None and len(seg) / SR >= 0.9


def test_max_length_forces_a_cut():
    vad = VADSegmenter(sr=SR, max_ms=1000, silence_ms=500)
    segs = feed(vad, tone(2.5))
    assert sum(len(s) for s in segs) / SR >= 1.9
