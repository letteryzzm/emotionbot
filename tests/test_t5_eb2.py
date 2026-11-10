import struct
import time
import zlib

import numpy as np
import pytest

from head import t5_eb2 as eb
from head import t5_sim


def test_crc16_check_value():
    assert eb.crc16(b"123456789") == 0x29B1


def test_pack_parse_with_text_and_garbage_byte_by_byte():
    pk = eb.pack(eb.T_SCREEN_END, 7, struct.pack("<H", 3))
    stream = b"log noise\r\nEB1 5 OK PONG\n" + pk + b"\xeb\xff junk" + pk + b"EB1 6 OK PONG\n"
    p = eb.Parser()
    out = []
    for b in stream:
        out += p.feed(bytes([b]))
    assert [k for k, _ in out].count("packet") == 2
    assert [v for k, v in out if k == "line"] == ["log noise", "EB1 5 OK PONG", "EB1 6 OK PONG"]
    assert out[2][1] == eb.Packet(eb.T_SCREEN_END, 0, 7, struct.pack("<H", 3))


def test_bad_crc_skipped_and_resyncs():
    good = eb.pack(eb.T_PCM_STAT, 1, b"abc")
    bad = bytearray(eb.pack(eb.T_PCM_STAT, 2, b"xyz"))
    bad[9] ^= 0xFF
    p = eb.Parser()
    out = p.feed(bytes(bad) + good)
    assert [v.seq for k, v in out if k == "packet"] == [1]
    assert p.bad_crc >= 1


def test_rle_roundtrip_and_long_runs():
    a = np.concatenate([np.full(700, 0x1234, "<u2"), np.arange(50, dtype="<u2"), np.full(3, 0xFFFF, "<u2")])
    raw = a.tobytes()
    enc = eb.rle16_encode(raw)
    assert len(enc) < len(raw)
    assert eb.rle16_decode(enc, len(a)) == raw
    with pytest.raises(ValueError):
        eb.rle16_decode(enc, len(a) + 1)


def test_rect_packets_rebuild_screen():
    rng = np.random.default_rng(1)
    img = rng.integers(0, 4, (40, 90), dtype=np.uint16) * 9000          # 噪声多、压缩差，逼出分包
    packets = eb.rect_packets(1, 0, 0, 90, 40, img.astype("<u2").tobytes())
    assert len(packets) > 1 and all(len(p) <= eb.MAX_PAYLOAD for p in packets)
    buf = eb.ScreenBuffer(90, 40)
    for pl in packets:
        _, x, y, w, h, enc = struct.unpack_from("<HHHHHB", pl)
        buf.apply_rect(x, y, w, h, enc, pl[11:])
    assert bytes(buf.px) == img.astype("<u2").tobytes()
    with pytest.raises(ValueError):
        buf.apply_rect(80, 0, 20, 1, eb.ENC_RAW, b"\0" * 40)


def test_png_is_valid():
    buf = eb.ScreenBuffer(30, 20)
    buf.apply_rect(0, 0, 30, 20, eb.ENC_RAW, np.full(600, 0xF800, "<u2").tobytes())        # 纯红
    png = buf.png()
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    w, h = struct.unpack(">II", png[16:24])
    assert (w, h) == (30, 20)
    i = png.index(b"IDAT")
    raw = zlib.decompress(png[i + 4:i + 4 + struct.unpack(">I", png[i - 4:i])[0]])
    assert len(raw) == 20 * (1 + 30 * 3) and raw[1:4] == b"\xff\x00\x00"


def test_pcm_up_roundtrip():
    pk = eb.pack_pcm_up(9, 123456, 1, b"\x01\x00" * 320)
    (kind, p), = eb.Parser().feed(pk)
    assert eb.parse_pcm_up(p.payload) == (123456, 1, b"\x01\x00" * 320)


@pytest.fixture
def board():
    made = []

    def make(**kw):
        path, b, close = t5_sim.open_pty(blink_every=None, **kw)
        s = eb.T5Stream(path)
        made.append((s, close))
        return s, b
    yield make
    for s, close in made:
        s.close()
        close()


def _wait(cond, t=3.0):
    end = time.time() + t
    while time.time() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


def test_sim_streams_screen_and_follows_emotion(board):
    ends, buf = [], []

    def on_packet(p):
        if p.type == eb.T_SCREEN_INFO:
            w, h, _ = struct.unpack("<HHB", p.payload)
            buf.append(eb.ScreenBuffer(w, h))
        elif p.type == eb.T_SCREEN_RECT:
            _, x, y, w, h, enc = struct.unpack_from("<HHHHHB", p.payload)
            buf[0].apply_rect(x, y, w, h, enc, p.payload[11:])
        elif p.type == eb.T_SCREEN_END:
            ends.append(struct.unpack("<H", p.payload)[0])

    s, b = board()
    s.on_packet = on_packet
    assert s.command("PING")[0] == "OK PONG"
    reply, _ = s.command("SCREEN START 10")
    assert reply == f"OK SCREEN {t5_sim.W} {t5_sim.H} 0"
    assert _wait(lambda: ends)
    assert bytes(buf[0].px) == t5_sim.render("neutral").astype("<u2").tobytes()
    n = len(ends)
    s.command("EMOTION happy")
    assert _wait(lambda: len(ends) > n)
    assert bytes(buf[0].px) == t5_sim.render("happy").astype("<u2").tobytes()
    assert bytes(buf[0].px) != t5_sim.render("neutral").astype("<u2").tobytes()


def test_sim_without_screen_support_replies_err(board):
    s, _ = board(screen=False)
    assert s.command("PING")[0] == "OK PONG"
    with pytest.raises(eb.CommandError):
        s.command("SCREEN START 5")


def test_command_timeout(board):
    s, b = board()
    b.stop()
    with pytest.raises(TimeoutError):
        s.command("PING", timeout=0.3)


def test_set_baud_on_sim(board):
    from unittest import mock
    s, _ = board()
    with mock.patch.object(type(s.ser), "baudrate", new_callable=mock.PropertyMock, return_value=115200) as bd:
        s.set_baud(2000000)
        assert bd.call_args_list[-1] == mock.call(2000000)          # 主机侧确实切了
    assert s.command("PING")[0] == "OK PONG"
