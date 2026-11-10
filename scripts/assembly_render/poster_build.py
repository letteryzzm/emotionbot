"""宣传海报排版：裁剪渲染图 → 生成 outputs/poster/poster.html（800×2000 mm），再用 Chrome 打印成 PDF。"""
import os, subprocess
from PIL import Image
ROOT = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
O = os.path.join(ROOT, 'outputs/poster')
for n in ('hero', 'eyes', 'brows', 'mouth'):
    im = Image.open(f'{O}/{n}.png'); im.crop(im.getchannel('A').point(lambda v: 255 if v > 8 else 0).getbbox()).save(f'{O}/c_{n}.png')


def face(eye, lid, brow_in, brow_out, mouth):
    """简笔表情：eye 眼高，lid 上眼皮下压，brow 内/外端高度，mouth 路径"""
    s = ''
    for sx in (-1, 1):
        cx = 50 + sx * 19
        s += f'<ellipse cx="{cx}" cy="42" rx="11" ry="{eye}" fill="#eef6f7"/><circle cx="{cx}" cy="42" r="{min(5.6, eye)}" fill="#14c8c8"/><circle cx="{cx}" cy="42" r="{min(2.6, eye)}" fill="#0a0e1a"/>'
        if lid:
            s += f'<rect x="{cx-12}" y="{42-eye-1}" width="24" height="{lid+1}" fill="#141a2c"/>'
        s += f'<path d="M{50+sx*8} {brow_in} L{50+sx*33} {brow_out}" stroke="#eef6f7" stroke-width="4.4" stroke-linecap="round"/>'
    return f'<svg viewBox="0 0 100 100"><path d="{mouth}" fill="none" stroke="#ff6a3d" stroke-width="4.6" stroke-linecap="round" stroke-linejoin="round"/>{s}</svg>'


FACES = [('平静', face(8, 0, 25, 25, 'M36 74 L64 74')),
         ('开心', face(7, 2, 22, 24, 'M30 68 Q50 90 70 68')),
         ('难过', face(7, 3, 19, 28, 'M34 80 Q50 66 66 80')),
         ('生气', face(9, 2, 33, 20, 'M36 77 L64 77')),
         ('惊讶', face(11, 0, 16, 16, 'M50 66 m-9 11 a9 11 0 1 0 18 0 a9 11 0 1 0 -18 0')),
         ('恐惧', face(11, 0, 17, 22, 'M30 76 Q40 70 50 76 T70 76')),
         ('厌恶', face(6, 3, 30, 24, 'M34 78 Q44 68 54 76 T68 72'))]
faces = ''.join(f'<div class="f">{s}<b>{n}</b></div>' for n, s in FACES)

MODS = [('eyes', '眼', '6', '眼球左右、上下，四片眼皮独立运动。凝视、眨眼、眯眼，都由机构完成。'),
        ('brows', '眉', '4', '内外两端分别驱动柔性 TPU 眉毛，抬、压、皱，表情的第一信号。'),
        ('mouth', '嘴', '11', '双 MG996R 驱动下颌，八路嘴唇嘴角，加上舌头，张合和微笑都有层次。')]
mods = ''.join(f'<div class="m"><div class="mi"><img src="c_{k}.png"></div><div class="mt"><i>{n}</i><span>{c}<small>个舵机</small></span></div><p>{t}</p></div>' for k, n, c, t in MODS)

HTML = f'''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>EmotionBot 海报</title><style>
@page{{size:800mm 2000mm;margin:0}}
:root{{--bg:#0a0e1a;--ink:#eef3f7;--mute:#9aa8ba;--cy:#22d6d0;--or:#ff6a3d;--line:#2a3550;--card:#111828}}
*{{box-sizing:border-box;margin:0;padding:0;-webkit-print-color-adjust:exact;print-color-adjust:exact}}
html,body{{width:800mm;height:2000mm;background:var(--bg)}}
body{{position:relative;overflow:hidden;color:var(--ink);font-family:"PingFang SC","Hiragino Sans GB",sans-serif}}
.glow{{position:absolute;left:50mm;top:230mm;width:700mm;height:800mm;background:radial-gradient(closest-side,rgba(34,214,208,.20),rgba(255,106,61,.07) 62%,transparent)}}
.pad{{position:absolute;left:50mm;right:50mm}}
.kick{{top:48mm;font-size:15mm;letter-spacing:2.2mm;color:var(--cy);font-weight:600}}
h1{{top:70mm;font-size:121mm;line-height:1;font-weight:800;letter-spacing:-2mm;font-family:"Helvetica Neue","PingFang SC",sans-serif}}
h1 em{{font-style:normal;color:var(--cy)}}
.slogan{{top:205mm;font-size:48mm;line-height:1.2;font-weight:600}}
.hero{{position:absolute;left:112mm;top:285mm;width:575mm}}
.tag{{position:absolute;font-size:22mm;font-weight:600;color:var(--ink);white-space:nowrap}}
.tag small{{display:block;font-size:13mm;font-weight:400;color:var(--mute);margin-top:1mm}}
.tag:before{{content:"";position:absolute;top:13mm;height:.7mm;background:var(--cy)}}
.tl:before{{left:100%;margin-left:4mm;width:var(--w)}}
.tr:before{{right:100%;margin-right:4mm;width:var(--w)}}
.stats{{top:1090mm;display:grid;grid-template-columns:repeat(4,1fr);border-top:.7mm solid var(--line);border-bottom:.7mm solid var(--line);padding:12mm 0}}
.stats div{{padding-left:8mm;border-left:.7mm solid var(--line)}} .stats div:first-child{{border:0;padding-left:0}}
.stats b{{display:block;font-size:68mm;line-height:1;font-weight:800;color:var(--cy);font-family:"Helvetica Neue",sans-serif}}
.stats span{{display:block;font-size:15mm;margin-top:3mm;color:var(--ink)}}
h2{{font-size:36mm;font-weight:700;line-height:1.15}} h2 small{{font-size:15mm;color:var(--mute);font-weight:400;margin-left:6mm}}
.flow{{top:1232mm}}
.fl{{display:grid;grid-template-columns:1.15fr 12mm 1fr 12mm 1fr;align-items:stretch;margin-top:12mm}}
.ar{{align-self:center;justify-self:center;width:0;height:0;border-left:9mm solid var(--or);border-top:7mm solid transparent;border-bottom:7mm solid transparent}}
.st{{background:var(--card);border:.7mm solid var(--line);border-radius:5mm;padding:9mm 9mm}}
.st h3{{font-size:21mm;color:var(--cy);margin-bottom:5mm}}
.st p,.st li{{font-size:13.5mm;line-height:1.42;color:var(--ink);list-style:none}} .st li b{{color:var(--or);font-weight:600;margin-right:3mm}}
.quote{{margin-top:9mm;font-size:17mm;line-height:1.35;border-left:2mm solid var(--or);padding-left:7mm}} .quote span{{color:var(--or);font-weight:600}}
.mods{{top:1478mm}}
.mg{{display:grid;grid-template-columns:repeat(3,1fr);gap:8mm;margin-top:10mm}}
.m{{background:var(--card);border:.7mm solid var(--line);border-radius:5mm;padding:7mm;display:flex;flex-direction:column}}
.mi{{height:78mm;display:flex;align-items:center;justify-content:center}} .mi img{{max-width:100%;max-height:78mm}}
.mt{{display:flex;justify-content:space-between;align-items:baseline;margin:4mm 0 2mm}} .mt i{{font-style:normal;font-size:26mm;font-weight:700}}
.mt span{{font-size:30mm;font-weight:800;color:var(--cy);font-family:"Helvetica Neue",sans-serif}} .mt small{{font-size:12mm;color:var(--mute);font-weight:400;margin-left:2mm;font-family:"PingFang SC"}}
.m p{{font-size:12.5mm;line-height:1.4;color:var(--mute)}}
.ex{{top:1738mm}}
.fg{{display:grid;grid-template-columns:repeat(7,1fr);gap:5mm;margin-top:7mm}}
.f{{text-align:center}} .f svg{{width:100%;display:block;background:#141a2c;border-radius:4mm}} .f b{{display:block;font-size:14.5mm;font-weight:600;margin-top:2.5mm}}
.foot{{bottom:24mm;border-top:.7mm solid var(--line);padding-top:7mm;font-size:12.5mm;line-height:1.45;color:var(--mute);display:flex;justify-content:space-between;gap:12mm}}
.foot b{{color:var(--ink);font-weight:600}}
</style></head><body>
<div class="glow"></div>
<div class="pad kick">开源情感机器人头 · AFFECTIVE ROBOT HEAD</div>
<h1 class="pad">Emotion<em>Bot</em></h1>
<div class="pad slogan">读懂你的情绪，用一张脸回应你</div>
<img class="hero" src="c_hero.png">
<div class="tag tl" style="left:50mm;top:640mm;--w:34mm">眉<small>4 舵机</small></div>
<div class="tag tl" style="left:50mm;top:735mm;--w:36mm">眼<small>6 舵机</small></div>
<div class="tag tl" style="left:50mm;top:960mm;--w:78mm">嘴<small>11 舵机</small></div>
<div class="pad stats">
<div><b>21</b><span>个舵机驱动整张脸</span></div><div><b>3</b><span>块 Pico 分控五官</span></div>
<div><b>22</b><span>维连续动作空间</span></div><div><b>3</b><span>种模态：脸、声音、文字</span></div></div>
<div class="pad flow"><h2>从感知到表达，一条完整闭环</h2>
<div class="fl">
<div class="st"><h3>感知</h3><ul><li><b>看</b>摄像头读取人脸表情</li><li><b>听</b>麦克风捕捉语气变化</li><li><b>读</b>语音转写，理解话语内容</li></ul></div><div class="ar"></div>
<div class="st"><h3>理解</h3><p>三路结果融合成 7 类情绪和效价、唤醒度，再由大模型决定回应什么表情、多大强度。</p></div><div class="ar"></div>
<div class="st"><h3>表达</h3><p>决策变成 22 维向量，经 USB 下发到 3 块 Pico，舵机限速插值，过渡自然。</p></div></div>
<p class="quote">皱着眉说“太好了，又要加班”？字面是开心，语气不是。<span>它听得出这句话的矛盾。</span></p></div>
<div class="pad mods"><h2>一张会动的脸</h2><div class="mg">{mods}</div></div>
<div class="pad ex"><h2>七种基本情绪<small>按 FACS 面部动作编码设计，可连续混合</small></h2><div class="fg">{faces}</div></div>
<div class="pad foot"><div><b>实测：</b>同批 56 条样本上，本地模型的 UA 超过测试中的闭源大模型：RAVDESS 85.7 vs 66.1，CREMA-D 88.9 vs 59.3。</div>
<div style="flex:0 0 330mm"><b>基于</b> Will Cogley 的 Robot Head α2.0.33 与 EyeMech ε3.2 · CC BY-NC-SA 4.0 · 非商业用途</div></div>
</body></html>'''
open(f'{O}/poster.html', 'w', encoding='utf8').write(HTML)
chrome = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome'
subprocess.run([chrome, '--headless=new', '--disable-gpu', '--no-pdf-header-footer', f'--print-to-pdf={O}/EmotionBot_海报_80x200cm.pdf', f'file://{O}/poster.html'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=180)
