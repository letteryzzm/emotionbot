# T5 表情同步：发舵机命令时同时给 T5 发对应表情

写给负责联合调试的 session。日期：2026-11-07。

## 要做的事

每次你让头部做某个表情（发舵机命令）时，**同时**让 T5 屏幕显示同一个表情。T5 发送失败不能阻塞舵机命令，只需要在汇报里说明"屏幕没同步"。

不要碰 Pico 串口，除非用户另行明确下命令（沿用 `T5上位机联调交接-2026-11-07.md` 里的约定）。

## 表情名对应

T5 固件只认下面 7 个英文名。**舵机侧叫 `surprised`，T5 叫 `surprise`**，其余相同。

| 舵机侧（`head/expressions.py`） | 发给 T5 |
|---|---|
| neutral | neutral |
| happy | happy |
| sad | sad |
| angry | angry |
| **surprised** | **surprise** |
| fear | fear |
| disgust | disgust |

下面的 HTTP 接口已经自动把 `surprised` 转成 `surprise`；用 `t5_link` 直接发时要自己转。

## 方式 A（推荐）：调用 ROG 上的屏幕/语音服务

T5 的串口同一时间只能一个程序打开。`scripts/t5_screen_server.py` 开着时它占着串口，别的程序不要直接开串口，改调它的 HTTP 接口：

```python
import json, urllib.request

def t5_emotion(name, base="http://127.0.0.1:8766"):
    """返回 (成功?, 说明)。失败不抛异常，不影响舵机命令。"""
    try:
        req = urllib.request.Request(base + "/cmd", json.dumps({"cmd": "emotion:" + name}).encode(),
                                     {"Content-Type": "application/json"})
        d = json.load(urllib.request.urlopen(req, timeout=2))
        return d.get("ok", False), d.get("reply") or d.get("error")
    except Exception as e:           # noqa: BLE001
        return False, f"T5 屏幕未同步：{e}"
```

- 成功时回执是 `OK EMOTION <name>`（约 5 ms）。
- 表情名不对会得到 `ok: false` 和可用名单。
- 服务只监听 ROG 本机的 `127.0.0.1:8766`；在别的电脑上用 `ssh -L 8766:127.0.0.1:8766 rog`。
- 用法：在发舵机命令的同一处调用一次 `t5_emotion(name)`，先发舵机还是先发屏幕都可以，建议并行。

先确认服务在运行：

```bash
curl -s 127.0.0.1:8766/state | head -c 200       # 有 "connected": true 就是在运行
```

## 方式 B：服务没开时直接用 `head/t5_link.py`

```python
from head.t5_eb2 import T5Stream            # 或用你们原来的 T5Link
s = T5Stream("/dev/serial/by-id/usb-1a86_USB_Dual_Serial_5AAE165026-if00", baud=115200)
s.command("EMOTION surprise")
s.close()
```

**用之前先确认没有别的程序占串口**（`fuser /dev/serial/by-id/usb-1a86_USB_Dual_Serial_5AAE165026-if00`），并且要先停掉方式 A 的服务（见下）。

## 启停服务

```bash
# 启动（在 ROG 上；--baud 2000000 是因为板子之前被提速过，见下面"波特率"）
cd /srv/robot-head && setsid nohup tools/voice_test/.venv/bin/python scripts/t5_screen_server.py \
  --port /dev/serial/by-id/usb-1a86_USB_Dual_Serial_5AAE165026-if00 --fast 2000000 --voice \
  --listen 127.0.0.1:8766 > /tmp/t5_voice_server.log 2>&1 < /dev/null &

# 停止（发 SIGTERM，不要 kill -9）：服务会先停屏幕回传和语音、再把板子切回 115200
kill $(pgrep -f "scripts/[t]5_screen_server.py")
```

- 启动命令从 ssh 里执行时，ssh 会因为后台进程挂住不返回，服务本身是正常的；可以另开一个终端检查 `/state`。
- 不要用 `pgrep -f` 的模式去匹配自己所在的 ssh 命令行（会把自己杀掉）。上面的 `[t]5` 写法是为了避免这一点。
- 不想要语音交互只要屏幕：去掉 `--voice`。

## 波特率（容易踩坑）

- 板子默认 115200。服务用 `--fast 2000000` 连上后会提速到 2 Mbaud，服务**正常停止**（SIGTERM）时会切回 115200。
- 如果服务是被 `kill -9` 或崩溃停掉的，板子会停在 2 Mbaud，`t5_link` 用 115200 会收不到回复。这时用 `T5Stream(..., baud=2000000)` 连上，发 `BAUD 115200`；或者拔插一次 USB。
- 115200 带宽装不下屏幕回传，所以别在 115200 下开 `SCREEN START`。如果发现命令没回执，先试 `SCREEN STOP`，多重试几次、超时放宽到 6 秒。

## 和语音交互的关系

服务带 `--voice` 时，T5 板子的麦克风在听、喇叭在说话；每轮对话它会根据回复内容**自己**发一次 `EMOTION`。所以对话期间你发的表情可能被它改掉。联合调试做动作演示时，建议不带 `--voice` 启动，或者在演示期间不要对着板子说话。

## 验证同步成功

- 接口回执 `OK EMOTION <name>`。
- 取画面确认：`curl -s 127.0.0.1:8766/frame.png -o /tmp/t5.png`，屏幕中间卡片左下角会显示对应的中文名（平静/开心/难过/生气/惊讶/害怕/厌恶）。

## 相关文件

- `docs/T5屏幕与语音协议-EB2.md`：协议和命令全表
- `firmware_t5/`：固件源码（基于协作者的线条表情版）
- 回退固件：`/srv/robot-head/t5_screen/firmware/emotionbot_screen_QIO_line_faces.bin`
