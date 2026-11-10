# T5 屏幕与语音协议（EB2）

状态：**已实现并在真板子上验证**（2026-11-07）。固件在 `firmware_t5/`，电脑端在 `head/t5_eb2.py`。

## 1. 实测结果（ROG + T5AI，直连 USB）

| 项目 | 结果 |
|---|---|
| 屏幕 | 320×480，RGB565；整帧 115200 下 1.9 s，2 Mbaud 下只发脏矩形 |
| 屏幕流 | 2 Mbaud，4.8–7.3 帧/秒（脸上下浮动），约 26 KB/s，CRC 错误 0 |
| 串口速度 | 115200、921600、2000000 通；**3000000 不通**（固件拒绝 >2M） |
| PING 往返 | 115200 下 5 ms，2 Mbaud 下 2 ms（旧固件中位 152 ms） |
| 语音上行 | 50 帧/秒（每帧 20 ms、640 字节），时间戳间隔 16–23 ms，丢帧 0 |
| 语音下行 | 20 ms 一包实时推送，丢包 0 |
| VAD 标志 | **一直是 0**：这版音频配置没有上报语音起止，端点检测由电脑端做 |

未验证：语音下行的音质（需要人在场听）、AEC 对喇叭回声的压制、长时间稳定性。

## 2. 包格式

EB1 文本命令照旧，以 `\n` 结尾。EB2 二进制包以 `0xEB 0x02` 开头，小端：

```
0xEB 0x02 | type u8 | flags u8 | seq u16 | len u16 | payload[len] | crc16 u16
```

`crc16` 是 CRC-16/CCITT-FALSE（多项式 0x1021，初值 0xFFFF），范围是 `type` 到 `payload` 末尾；`len` ≤ 4096；坏包逐字节重新找包头。

| type | 方向 | 载荷 |
|---|---|---|
| 0x01 SCREEN_INFO | 板→电脑 | `w u16, h u16, fmt u8`（0 = RGB565） |
| 0x02 SCREEN_RECT | 板→电脑 | `frame u16, x u16, y u16, w u16, h u16, enc u8` + 数据；enc 1 = 每行 RLE `(次数 u8, 像素 2 字节)` |
| 0x03 SCREEN_END | 板→电脑 | `frame u16`，这一帧的更新发完 |
| 0x10 PCM_UP | 板→电脑 | `ts_ms u32, vad u8` + PCM（16 kHz s16le 单声道，640 字节） |
| 0x11 PCM_DOWN | 电脑→板 | PCM（同上），板子放进 1 秒的环形缓冲 |
| 0x12 PCM_STAT | 板→电脑 | 每 250 ms 一次：`queue_ms u16, underrun u16, play_drop u16, up_drop u16, flush u16`（underrun 是空闲轮询次数，参考价值低） |

## 3. 命令（EB1 文本）

| 命令 | 回复 |
|---|---|
| `SCREEN START [fps 1..20]` | `OK SCREEN <w> <h> 0`，随后先发 SCREEN_INFO 和整帧，之后只发变化的区域 |
| `SCREEN SNAP` / `SCREEN STOP` | 一帧 / 停止 |
| `VOICE START` / `VOICE STOP` | 打开 / 关闭麦克风上行和喇叭下行；开启期间 `AUDIO`、`MUSIC` 回 `ERR busy` |
| `VOICE VOL <0..100>` | 喇叭音量 |
| `BAUD <n>` | 先用旧速度回 `OK BAUD <n>`，再切换；n 最大 2000000。切换后 4 秒内没收到有效的 `EB1 ` 命令，板子自动回到 115200 |
| `STAT` | `OK STAT baud=.. voice=.. scr=.. flush=..` |
| `PING`、`EMOTION`、`AUDIO`、`MUSIC` | 和之前一样 |

## 4. 电脑端

| 文件 | 作用 |
|---|---|
| `head/t5_eb2.py` | 编解码、解析器、RLE、屏幕副本和 PNG、`T5Stream`（含 `set_baud`） |
| `head/t5_sim.py` | 模拟板子（假屏幕，只用于测试，画的不是板子真实的线条表情） |
| `scripts/t5_screen_server.py` | 本地网页；`--fast 2000000` 让板子连上后提速 |
| `tests/test_t5_eb2.py` | 11 项测试 |

```bash
# 在 ROG 上（串口同一时间只能一个程序用）
.venv/bin/python scripts/t5_screen_server.py --port /dev/serial/by-id/usb-1a86_USB_Dual_Serial_5AAE165026-if00 --fast 2000000
# 在 Mac 上
ssh -L 8766:127.0.0.1:8766 rog      # 然后打开 http://127.0.0.1:8766
```

## 5. 固件实现要点

- flush 钩子（读 `disp->flush_cb` 再包一层）把每个刷新区域拷进 PSRAM 的影子帧缓冲，并合并成一个脏矩形；LVGL 任务里只持锁拷贝。
- 三个线程：`eb2_rx`（读 UART，分出 EB1 行和 PCM_DOWN 包）、`eb2_tx`（按帧率发屏幕、把麦克风环里的帧发成 PCM_UP）、`eb2_play`（环形缓冲 → `tdl_audio_play`）。
- `EMOTION` 来自 `eb2_rx` 线程，改 LVGL 对象时必须持 `lv_vendor_disp_lock()`。
- 提速踩过的坑：3M 下收到的乱码里有换行，被当成命令，取消了回退倒计时，板子失联，只能重新刷写。现在只有以 `EB1 ` 开头的行才取消回退，且上限 2M。

## 6. 未决

- 语音端点检测（VAD 在板上没有上报）和 AEC 效果要有人在场实测。
- 语音识别和合成放在哪里：ROG 上已下好 SenseVoice（`/srv/robot-head/tools/voice_test/models/sv`），合成模型还没下。
