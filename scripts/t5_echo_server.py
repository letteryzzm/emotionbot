"""T5 板音频联调用的接收端：证明板子到笔记本的链路是通的。

    python scripts/t5_echo_server.py --port 8770 --save t5_capture.wav

约定（和 perception/audio_source.py 的 UdpPcmSource 一致）：
  16 kHz / 单声道 / signed 16-bit little-endian，每个 UDP 包长度任意，建议 20–40ms。

界面每秒打印一次 RMS 和累计时长，Ctrl+C 停止并把收到的数据存成 wav。
如果 T5 只能发 24k 或 Opus，先在板端重采样成 16k PCM；实在不行再改这里，
但笔记本端要同步改 UdpPcmSource 的 sr。
"""
from __future__ import annotations

import argparse
import socket
import time
import wave

import numpy as np


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default="0.0.0.0")
    ap.add_argument("--port", type=int, default=8770)
    ap.add_argument("--sr", type=int, default=16000)
    ap.add_argument("--save", default="t5_capture.wav")
    args = ap.parse_args(argv)

    sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    sock.bind((args.host, args.port))
    sock.settimeout(0.5)
    print(f"监听 UDP {args.host}:{args.port}，期望 {args.sr} Hz mono s16le")
    print("按 Ctrl+C 结束并保存。")

    frames: list[np.ndarray] = []
    total = 0.0
    last_print = time.monotonic()
    peak = 0.0
    try:
        while True:
            try:
                data, addr = sock.recvfrom(65536)
            except socket.timeout:
                if time.monotonic() - last_print > 1.0:
                    print(f"  等待数据…（已收 {total:.1f}s）")
                    last_print = time.monotonic()
                continue
            if len(data) % 2:
                data = data[:-1]
            if not data:
                continue
            pcm = np.frombuffer(data, dtype="<i2")
            frames.append(pcm.copy())
            total += len(pcm) / args.sr
            rms = float(np.sqrt(np.mean(pcm.astype(np.float64) ** 2)) / 32768.0)
            peak = max(peak, float(np.max(np.abs(pcm)) / 32768.0))
            now = time.monotonic()
            if now - last_print >= 1.0:
                bar = "#" * int(min(1.0, rms * 20) * 40)
                print(f"  {addr[0]:15s} rms={rms:.4f} peak={peak:.2f} 共 {total:.1f}s |{bar}")
                last_print, peak = now, 0.0
    except KeyboardInterrupt:
        print("\n停止。")
    finally:
        sock.close()

    if frames:
        x = np.concatenate(frames)
        with wave.open(args.save, "wb") as w:
            w.setnchannels(1)
            w.setsampwidth(2)
            w.setframerate(args.sr)
            w.writeframes(x.tobytes())
        print(f"已保存 {args.save}（{len(x)/args.sr:.1f}s）")
        print("用它离线验证： python -m app.run --source file --wav " + args.save)
    else:
        print("没收到任何数据，检查板子的目标 IP/端口和防火墙。")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
