"""ROG 本地语音交互：本机麦克风 → 端点检测 → SenseVoice → MiniMax 对话 → MiniMax TTS → 本机扬声器。

不用 T5 板子。网页只监听本机：http://127.0.0.1:8767 ，别的电脑用 ssh -L 8767:127.0.0.1:8767 rog。
    python scripts/rog_voice.py                  # 一直听，说完一句就回答
    python scripts/rog_voice.py --wake 小表      # 必须先叫"小表"，之后 25 秒内可连续说话
麦克风/喇叭走 PipeWire 的 PulseAudio 接口（parecord / paplay）。
"""
from __future__ import annotations

import argparse
import json
import os
import signal
import subprocess
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from head import t5_voice as tv
from head.hub_client import HubClient
from head.voice_face import VoiceFace

FRAME = 640                      # 20 ms，16 kHz s16le 单声道
ENV = dict(os.environ, XDG_RUNTIME_DIR=os.environ.get("XDG_RUNTIME_DIR", f"/run/user/{os.getuid()}"))


class LocalMic:
    def __init__(self, agent, device=None):
        self.agent, self.paused, self.error = agent, False, None
        cmd = ["parecord", "--format=s16le", "--rate=16000", "--channels=1", "--raw", "--latency-msec=20"]
        if device:
            cmd.append(f"--device={device}")
        self.proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=ENV)
        threading.Thread(target=self._run, daemon=True).start()

    def _run(self):
        while True:
            data = self.proc.stdout.read(FRAME)
            if len(data) < FRAME:
                self.error = "麦克风停止：" + (self.proc.stderr.read(300).decode("utf-8", "replace") or "parecord 退出")
                return
            if not self.paused:
                self.agent.feed(data)
            else:
                self.agent.ep.reset()


class LocalSpeaker:
    def __init__(self, device=None):
        cmd = ["paplay", "--raw", "--format=s16le", "--rate=16000", "--channels=1", "--latency-msec=60"]
        if device:
            cmd.append(f"--device={device}")
        self.proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stderr=subprocess.DEVNULL, env=ENV)

    def __call__(self, chunk):
        self.proc.stdin.write(chunk)
        self.proc.stdin.flush()


PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>小表语音</title><style>
:root{--bg:#f4f6f8;--card:#fff;--ink:#1d2430;--mute:#667385;--line:#dde2e8;--acc:#0f8a84;--me:#e8f1ff;--bot:#e6f6f1}
@media (prefers-color-scheme:dark){:root{--bg:#10151d;--card:#171e29;--ink:#e6ebf1;--mute:#97a3b3;--line:#2a3441;--acc:#3cc9c1;--me:#1d2a40;--bot:#17302c}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.6 -apple-system,"PingFang SC","Noto Sans CJK SC",sans-serif}
main{max-width:760px;margin:0 auto;padding:20px 16px}h1{font-size:22px;margin:0 0 4px}
.top{display:flex;align-items:center;gap:16px;background:var(--card);border:1px solid var(--line);border-radius:14px;padding:14px 18px;margin:12px 0}
#face{font-size:56px;line-height:1}#st{font-size:20px;font-weight:600}#sub{color:var(--mute);font-size:14px}
.bar{height:8px;background:var(--line);border-radius:4px;position:relative;margin-top:8px;overflow:hidden}
#lv{position:absolute;left:0;top:0;bottom:0;background:var(--acc);width:0;transition:width .15s}#th{position:absolute;top:-2px;bottom:-2px;width:2px;background:#e5484d}
#log{display:flex;flex-direction:column;gap:10px;margin:14px 0}.m{padding:10px 14px;border-radius:12px;max-width:88%}.me{background:var(--me);align-self:flex-end}.bot{background:var(--bot)}
.t{color:var(--mute);font-size:12px;margin-top:2px}form{display:flex;gap:8px;position:sticky;bottom:10px}
input{flex:1;padding:12px 14px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font:inherit}
button{padding:10px 16px;border:1px solid var(--line);border-radius:10px;background:var(--card);color:var(--ink);font:inherit;cursor:pointer}
button.on{background:var(--acc);color:#fff;border-color:var(--acc)}#err{color:#c2410c;font-size:14px;min-height:20px}
</style></head><body><main>
<h1>小表语音</h1><div style="color:var(--mute);font-size:14px">用这台电脑的麦克风和扬声器。直接说话，或者在下面打字。</div>
<div class="top"><div id="face">😐</div><div style="flex:1"><div id="st">连接中…</div><div id="sub"></div><div class="bar"><div id="lv"></div><div id="th"></div></div></div>
<button id="mute">暂停听</button></div>
<div id="err"></div><div id="log"></div>
<form id="f"><input id="t" placeholder="打字和小表说话（不用开口）" autocomplete="off"><button>发送</button></form>
</main><script>
const $=i=>document.getElementById(i),E={neutral:'😐',happy:'😊',sad:'😢',angry:'😠',surprise:'😲',fear:'😨',disgust:'🤢'};
let paused=false,shown=0;
async function cmd(c){const r=await fetch('/cmd',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({cmd:c})});return r.json()}
$('f').onsubmit=e=>{e.preventDefault();const v=$('t').value.trim();if(v){cmd('say:'+v);$('t').value=''}};
$('mute').onclick=async()=>{const j=await cmd(paused?'listen':'pause');paused=j.paused;};
function add(cls,txt,sub){const d=document.createElement('div');d.className='m '+cls;d.textContent=txt;if(sub){const s=document.createElement('div');s.className='t';s.textContent=sub;d.append(s)}$('log').append(d);scrollTo(0,document.body.scrollHeight)}
async function tick(){try{const s=await (await fetch('/state')).json();const v=s.voice;
$('face').textContent=E[v.emotion]||'😐';paused=s.paused;$('mute').textContent=paused?'继续听':'暂停听';$('mute').className=paused?'on':'';
$('st').textContent=paused?'已暂停听':({'idle':'在听','listening…':'听到你在说话…'}[v.status]||v.status);
$('sub').textContent=(v.awake?'':'（需要先叫唤醒词）')+'音量 '+v.rms+'　底噪 '+v.floor+'　触发阈值 '+v.threshold;
const m=Math.max(v.threshold*2,1500);$('lv').style.width=Math.min(100,v.rms/m*100)+'%';$('th').style.left=Math.min(100,v.threshold/m*100)+'%';
$('err').textContent=s.error||v.error||'';
const T=v.all;while(shown<T.length){const t=T[shown++];if(t.text)add('me',t.text,t.ignored?'没有唤醒词，已忽略':('识别 '+t.asr_s+'s'));
if(t.reply)add('bot',t.reply,'['+t.emotion+']　对话 '+t.llm_s+'s　合成首句 '+t.tts_s+'s　从说完到出声 '+t.first_audio_after_speech_end_s+'s')}
}catch(e){$('st').textContent='网页服务无响应'}setTimeout(tick,500)}
tick();
</script></body></html>"""


def make_handler(agent, mic):
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a):
            pass

        def send(self, code, body, ctype="application/json"):
            if not isinstance(body, bytes):
                body = json.dumps(body, ensure_ascii=False).encode()
            self.send_response(code)
            self.send_header("Content-Type", ctype + "; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_GET(self):
            if self.path == "/":
                return self.send(200, PAGE.encode(), "text/html")
            if self.path == "/state":
                snap = agent.snapshot()
                snap["all"] = agent.turns
                return self.send(200, {"voice": snap, "paused": mic.paused, "error": mic.error})
            self.send(404, {"error": "not found"})

        def do_POST(self):
            if self.path != "/cmd":
                return self.send(404, {"error": "not found"})
            try:
                n = int(self.headers.get("Content-Length", "0"))
                c = json.loads(self.rfile.read(n))["cmd"] if 0 < n < 2000 else ""
                if c.startswith("say:"):
                    agent.say(c[4:])
                elif c in ("pause", "listen"):
                    mic.paused = c == "pause"
                else:
                    raise ValueError("未知命令")
                self.send(200, {"ok": True, "paused": mic.paused})
            except Exception as e:       # noqa: BLE001  原因原样返回给页面
                self.send(200, {"ok": False, "error": f"{type(e).__name__}: {e}"})
    return H


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--asr-model", default="/srv/robot-head/tools/voice_test/models/sv")
    ap.add_argument("--voice-id", default="Chinese (Mandarin)_Gentle_Youth")
    ap.add_argument("--wake", default=None, help="唤醒词，如 小表；默认不需要")
    ap.add_argument("--mic", default=None, help="PulseAudio 输入设备名，默认系统默认")
    ap.add_argument("--sink", default=None, help="PulseAudio 输出设备名，默认系统默认")
    ap.add_argument("--tail", type=float, default=0.6, help="放完后继续不听的秒数（防止喇叭声被当成人声）")
    ap.add_argument("--listen", default="127.0.0.1:8767")
    ap.add_argument("--hub-port", type=int, default=8780, help="统一控制进程端口，表情和下巴发到这里")
    a = ap.parse_args()
    key = tv._key()
    speaker = LocalSpeaker(a.sink)
    face = VoiceFace(HubClient(port=a.hub_port))

    def play(chunk):
        speaker(chunk)
        face.audio(chunk)

    agent = tv.VoiceAgent(tv.sensevoice(a.asr_model), tv.minimax_chat(key), tv.minimax_tts(key, a.voice_id),
                          sink=play, on_emotion=face.on_emotion, tail_mute=a.tail, wake=a.wake)
    mic = LocalMic(agent, a.mic)
    host, port = a.listen.rsplit(":", 1)
    print(f"http://{host}:{port}  麦克风 {a.mic or '默认'}  扬声器 {a.sink or '默认'}  唤醒词 {a.wake or '无'}", flush=True)
    signal.signal(signal.SIGTERM, lambda *_: os._exit(0))
    ThreadingHTTPServer((host, int(port)), make_handler(agent, mic)).serve_forever()


if __name__ == "__main__":
    main()
