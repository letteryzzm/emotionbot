"""T5 板子屏幕的本地网页：板子通过串口回传屏幕画面，这里解码后用浏览器显示。

    # 真板子（ROG 上跑，串口同一时间只能一个程序用，运行期间 t5_console 会提示串口正在使用）
    .venv/bin/python scripts/t5_screen_server.py --port /dev/serial/by-id/usb-1a86_USB_Dual_Serial_5AAE165026-if00
    # 然后在 Mac 上：ssh -L 8766:127.0.0.1:8766 rog，浏览器打开 http://127.0.0.1:8766
    # 没有硬件，用模拟板子看网页
    .venv/bin/python scripts/t5_screen_server.py --sim

网页只监听本机回环地址。现有固件不支持屏幕回传，网页会明确提示，不会显示假画面。
"""
import argparse
import os
import signal
import json
import os
import struct
import sys
import threading
import time
from collections import deque
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from head import t5_eb2 as eb  # noqa: E402


class Hub:
    def __init__(self, stream_factory, voice=None):
        self.lock = threading.Lock()
        self.buf = None
        self.png = b""
        self.frame = None
        self.ends = deque(maxlen=64)
        self.last_end = None
        self.packets = self.bad_rects = 0
        self.supported = None            # None 未知，True/False 看 SCREEN START 的回执
        self.note = "正在连接板子"
        self.rtt = None
        self.emotion = None
        self.log = deque(maxlen=8)
        self.stream = None
        self.voice = voice               # t5_voice.VoiceAgent，--voice 时设置
        self.factory = stream_factory
        threading.Thread(target=self._connect, daemon=True).start()
        threading.Thread(target=self._ping_loop, daemon=True).start()

    def on_packet(self, p):
        if self.voice:
            self.voice.on_packet(p)      # 麦克风包交给语音流水线（很快就返回）
        with self.lock:
            try:
                if p.type == eb.T_SCREEN_INFO:
                    w, h, fmt = struct.unpack("<HHB", p.payload)
                    if fmt != eb.FMT_RGB565:
                        self.note = f"板子用了不支持的像素格式 {fmt}"
                    elif not self.buf or (self.buf.w, self.buf.h) != (w, h):
                        self.buf = eb.ScreenBuffer(w, h)
                elif p.type == eb.T_SCREEN_RECT and self.buf:
                    _, x, y, w, h, enc = struct.unpack_from("<HHHHHB", p.payload)
                    self.buf.apply_rect(x, y, w, h, enc, p.payload[11:])
                elif p.type == eb.T_SCREEN_END and self.buf:
                    self.frame = struct.unpack("<H", p.payload[:2])[0]
                    self.png = self.buf.png()
                    self.last_end = time.time()
                    self.ends.append(self.last_end)
            except (ValueError, struct.error):
                self.bad_rects += 1

    def _connect(self):
        try:
            self.stream = self.factory(self.on_packet, lambda line: self.log.append(line))
            _, self.rtt = self.stream.command("PING")
            self.start_screen()
            if self.voice:
                self.voice.stream = self.stream
                self.stream.command("VOICE START")
        except Exception as e:           # noqa: BLE001  网页上要原样显示失败原因
            self.note = f"连接失败：{e}"

    def _ping_loop(self):
        while True:
            time.sleep(5)
            if self.stream and not self.stream.error and self.supported is not None:
                try:
                    self.rtt = self.stream.command("PING")[1]
                except Exception:        # noqa: BLE001
                    self.rtt = None

    def start_screen(self):
        try:
            reply, _ = self.stream.command("SCREEN START 5")
            _, w, h, fmt = reply.split()[1:5] if reply.startswith("OK SCREEN") else (0, 0, 0, 0)
            self.supported = True
            self.note = "已开始接收屏幕画面"
        except eb.CommandError:
            self.supported = False
            self.note = "这版固件不支持屏幕回传（板子对 SCREEN 命令回复 ERR command）。需要先改固件，见 docs/T5屏幕与语音协议-EB2.md"
        except TimeoutError:
            self.supported = False
            self.note = "板子没有回复 SCREEN 命令"

    def state(self):
        with self.lock:
            now = time.time()
            recent = [t for t in self.ends if now - t < 5]
            return {
                "connected": bool(self.stream) and not (self.stream and self.stream.error),
                "error": self.stream.error if self.stream else None,
                "note": self.note, "supported": self.supported, "frame": self.frame,
                "size": [self.buf.w, self.buf.h] if self.buf else None,
                "fps": round(len(recent) / 5, 1) if recent else 0,
                "age_ms": round((now - self.last_end) * 1000) if self.last_end else None,
                "rtt_ms": round(self.rtt, 1) if self.rtt else None, "emotion": self.emotion,
                "packets": self.stream.packets if self.stream else 0, "bad_crc": self.stream.parser.bad_crc if self.stream else 0,
                "bad_rects": self.bad_rects, "log": list(self.log),
                "voice": self.voice.snapshot() if self.voice else None,
            }

    def command(self, name):
        if not self.stream:
            raise RuntimeError("板子未连接")
        if name == "ping":
            reply, self.rtt = self.stream.command("PING")
            return reply
        if name.startswith("emotion:"):
            emo = {"surprised": "surprise"}.get(name[8:], name[8:])      # 舵机侧叫 surprised，T5 固件叫 surprise
            if emo not in eb.EMOTIONS:
                raise ValueError(f"未知表情 {name[8:]!r}，可用：{', '.join(eb.EMOTIONS)}")
            reply, _ = self.stream.command(f"EMOTION {emo}")
            self.emotion = emo
            return reply
        if name.startswith("say:"):
            if not self.voice:
                raise RuntimeError("没有开启语音（启动时加 --voice）")
            self.voice.say(name[4:])
            return "已发送，等回答"
        if name == "screen_start":
            self.start_screen()
            return self.note
        if name in ("screen_snap", "screen_stop"):
            return self.stream.command("SCREEN " + name[7:].upper())[0]
        raise ValueError("未知命令")


PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>T5 屏幕</title><style>
:root{--bg:#f4f6f8;--card:#fff;--ink:#1d2430;--mute:#667385;--line:#dde2e8;--acc:#0f8a84;--warn:#b4530c;--warnbg:#fff3e6}
@media (prefers-color-scheme:dark){:root{--bg:#10151d;--card:#171e29;--ink:#e6ebf1;--mute:#97a3b3;--line:#2a3441;--acc:#3cc9c1;--warn:#f0a35e;--warnbg:#2b2015}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"PingFang SC",sans-serif}
main{max-width:940px;margin:auto;padding:24px 16px 48px}h1{font-size:22px;margin:0 0 4px}.sub{color:var(--mute);margin:0 0 16px}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px}@media (max-width:720px){.grid{grid-template-columns:1fr}}
.card{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:16px}
.screen{background:#05080c;border-radius:10px;padding:10px;display:flex;align-items:center;justify-content:center;min-height:260px}
.screen img{max-width:100%;height:auto;image-rendering:pixelated;border-radius:4px;display:none}.screen span{color:#8a97a8;text-align:center;padding:0 12px}
.note{border-radius:8px;padding:9px 12px;margin-bottom:12px;background:var(--warnbg);color:var(--warn)}.note.ok{background:transparent;color:var(--mute);padding:0}
table{width:100%;border-collapse:collapse}td{padding:5px 0;border-bottom:1px solid var(--line)}td:last-child{text-align:right;font-variant-numeric:tabular-nums}
h2{font-size:15px;margin:0 0 10px}.btns{display:flex;flex-wrap:wrap;gap:6px;margin-top:8px}
button{font:inherit;color:var(--ink);background:var(--card);border:1px solid var(--line);border-radius:7px;padding:5px 11px;cursor:pointer}button:hover{border-color:var(--acc)}button.on{background:var(--acc);border-color:var(--acc);color:#fff}
pre{margin:8px 0 0;font:12px/1.5 ui-monospace,monospace;color:var(--mute);white-space:pre-wrap;max-height:110px;overflow:auto}
</style></head><body><main>
<h1>T5 开发板屏幕</h1><p class="sub">画面由板子通过串口回传，这里只做显示；没有收到回传时不会显示任何画面。</p>
<div class="grid"><section class="card"><div class="screen"><img id="shot" alt="T5 板子屏幕的当前画面"><span id="empty">等待板子回传画面</span></div></section>
<section class="card"><div id="note" class="note">连接中…</div>
<table><tr><td>连接</td><td id="c">—</td></tr><tr><td>屏幕尺寸</td><td id="sz">—</td></tr><tr><td>帧号</td><td id="fr">—</td></tr>
<tr><td>帧率（近 5 秒）</td><td id="fps">—</td></tr><tr><td>最近一帧</td><td id="age">—</td></tr><tr><td>命令往返</td><td id="rtt">—</td></tr>
<tr><td>数据包 / 校验错误</td><td id="pk">—</td></tr></table>
<h2 style="margin-top:14px">发给板子的命令</h2><div class="btns" id="b1"></div><div class="btns" id="b2"></div><form id="say" style="display:flex;gap:8px;margin:12px 0 4px"><input id="txt" placeholder="输入文字和小表对话（不用开口）" autocomplete="off" style="flex:1;padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--ink);font:inherit"><button type="submit">发送</button></form><pre id="msg"></pre></section></div></main>
<script>
const $=id=>document.getElementById(id),N={neutral:'平静',happy:'开心',sad:'难过',angry:'生气',surprise:'惊讶',fear:'恐惧',disgust:'厌恶'};
let last=null;
async function cmd(c){try{const r=await fetch('/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:c})});const j=await r.json();$('msg').textContent=(j.ok?'板子回复：':'失败：')+(j.reply||j.error)}catch(e){$('msg').textContent='失败：'+e}}
function btn(box,label,c){const b=document.createElement('button');b.textContent=label;b.onclick=()=>cmd(c);$(box).append(b)}
$('say').onsubmit=e=>{e.preventDefault();const t=$('txt').value.trim();if(t){cmd('say:'+t);$('txt').value=''}};
btn('b1','检查连接','ping');btn('b1','开始回传','screen_start');btn('b1','抓一帧','screen_snap');btn('b1','停止回传','screen_stop');
for(const k in N)btn('b2',N[k],'emotion:'+k);
async function tick(){try{const s=await (await fetch('/state')).json();
$('c').textContent=s.connected?'已连接':(s.error||'未连接');$('sz').textContent=s.size?s.size.join(' × '):'—';$('fr').textContent=s.frame??'—';
$('fps').textContent=s.supported?s.fps:'—';$('age').textContent=s.age_ms==null?'—':(s.age_ms/1000).toFixed(1)+' 秒前';$('rtt').textContent=s.rtt_ms?s.rtt_ms+' ms':'—';
$('pk').textContent=s.packets+' / '+s.bad_crc;const n=$('note');n.textContent=s.note;n.className='note'+(s.supported?' ok':'');
if(s.frame!=null&&s.frame!==last){last=s.frame;$('shot').src='/frame.png?f='+s.frame;$('shot').style.display='block';$('empty').style.display='none'}
var vt=s.voice?('语音：'+s.voice.status+(s.voice.error?'（'+s.voice.error+'）':'')+'　底噪'+s.voice.floor+' / 阈值'+s.voice.threshold+s.voice.turns.map(function(t){return '\\n你：'+t.text+'\\n小表：'+t.reply+' ['+t.emotion+']　识别'+t.asr_s+'s 对话'+t.llm_s+'s 合成'+t.tts_s+'s 首音'+t.first_audio_after_speech_end_s+'s'}).join('')):'';if(s.log.length||vt)$('msg').textContent=(vt+'\\n'+s.log.join('\\n')).trim()}catch(e){$('c').textContent='网页服务无响应'}setTimeout(tick,400)}
tick();
</script></body></html>"""


def make_handler(hub):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def reply(self, code, body, kind="application/json"):
            data = body if isinstance(body, bytes) else (body if isinstance(body, str) else json.dumps(body, ensure_ascii=False)).encode()
            self.send_response(code)
            self.send_header("Content-Type", kind + ("; charset=utf-8" if kind.startswith("text") or kind.endswith("json") else ""))
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = self.path.split("?")[0]
            if path == "/":
                self.reply(200, PAGE, "text/html")
            elif path == "/state":
                self.reply(200, hub.state())
            elif path == "/frame.png" and hub.png:
                self.reply(200, hub.png, "image/png")
            else:
                self.reply(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/cmd":
                return self.reply(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                name = json.loads(self.rfile.read(n))["cmd"] if 0 < n < 1500 else ""
                self.reply(200, {"ok": True, "reply": hub.command(name)})
            except Exception as e:       # noqa: BLE001  把原因原样返回给页面
                self.reply(200, {"ok": False, "error": f"{type(e).__name__}: {e}"})
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", help="T5 命令串口（by-id 路径）")
    ap.add_argument("--baud", type=int, default=115200)
    ap.add_argument("--sim", action="store_true", help="用模拟板子")
    ap.add_argument("--no-screen", action="store_true", help="模拟现有固件：不支持屏幕回传")
    ap.add_argument("--fast", type=int, default=0, help="连上后让板子提速到这个波特率（如 2000000）")
    ap.add_argument("--voice", action="store_true", help="开启语音交互（板子麦克风→识别→对话→板子喇叭）")
    ap.add_argument("--asr-model", default="/srv/robot-head/tools/voice_test/models/sv")
    ap.add_argument("--voice-id", default="Chinese (Mandarin)_Gentle_Youth")
    ap.add_argument("--listen", default="127.0.0.1:8766")
    a = ap.parse_args()
    if bool(a.port) == a.sim:
        ap.error("--port 和 --sim 二选一")
    if a.sim:
        from head import t5_sim
        path, _, _ = t5_sim.open_pty(screen=not a.no_screen)
    else:
        path = a.port
    host, port = a.listen.rsplit(":", 1)
    def make_stream(on_packet, on_line):
        st = eb.T5Stream(path, a.baud, on_packet, on_line)
        if a.fast:
            st.set_baud(a.fast)
        return st
    agent = None
    if a.voice:
        from head import t5_voice as tv
        key = tv._key()
        agent = tv.VoiceAgent(tv.sensevoice(a.asr_model), tv.minimax_chat(key), tv.minimax_tts(key, a.voice_id))
    hub = Hub(make_stream, voice=agent)

    def restore(*_):
        # 退出时把板子切回 115200，否则别的程序（t5_link / t5_console）用默认速度连不上
        try:
            st = hub.stream
            if st and not st.error and st.ser.baudrate > 115200:
                st.command("SCREEN STOP", timeout=1)       # 115200 带宽装不下屏幕流，不先停会把串口堵死
                st.command("VOICE STOP", timeout=1)
                st.command("BAUD 115200", timeout=1)
        except Exception:        # noqa: BLE001  退出路径上尽力而为
            pass
        os._exit(0)
    signal.signal(signal.SIGTERM, restore)
    signal.signal(signal.SIGINT, restore)
    print(f"http://{host}:{port}  串口 {path}", flush=True)
    ThreadingHTTPServer((host, int(port)), make_handler(hub)).serve_forever()


if __name__ == "__main__":
    main()
