"""生成 docs/舵机标定图.html：每组舵机发 90° 时实物应该是什么样，用来对照实物报偏差。
  .venv/bin/python scripts/assembly_render/calib_html.py

可信度要写实：模型画的姿态没有标注对应哪个角度，只有眼部有官方校准说明。
"""
import base64
import io
import json
import os

import numpy as np
from PIL import Image

from render import Scene, render

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
S = Scene(os.path.join(ROOT, 'outputs/assembly/mesh.npz'))
OBJS = json.load(open(os.path.join(ROOT, 'outputs/assembly/meta.json')))['objs']
OUT = os.path.join(ROOT, 'docs/舵机标定图.html')

HIDE = {'RearPlate', 'RearVent', 'FrontPlate', 'FrontVent', 'FanBracket'}
CTX = (0.86, 0.86, 0.84)
LEFT = (0.93, 0.50, 0.12)    # 面对机器人的左手边
RIGHT = (0.16, 0.45, 0.85)   # 右手边
MID = (0.80, 0.20, 0.45)     # 中间单个舵机

FRONT = ((0, 1, 0), (0, 0, 1), '正面')
SIDE = ((-1, 0, 0), (0, 0, 1), '侧面，脸朝左')
TOP = ((0, 0, -1), (0, 1, 0), '俯视，脸朝下')
BOTTOM = ((0, 0, 1), (0, 1, 0), '从下往上看，脸朝下')

# 放大到部位；侧视和俯视只显示这个模块，不然被头骨框架挡住
REGION = {'mouth': ('03', '04', '05'), 'brow': ('02',), 'eye': ('01',)}


def by_name(*names):
    return [o['gi'] for o in OBJS if any(n in o['name'] for n in names)]


def in_module(prefix, *names):
    return [o['gi'] for o in OBJS if o['module'].startswith(prefix) and any(n in o['name'] for n in names)]


EYEBALL = [46, 53]
GROUPS = [
    dict(n=1, title='舌头', names='TON', parts=[155], region='mouth', views=(BOTTOM, SIDE), level='低',
         want='舌头悬在口腔里，既不顶上颚，也不压在下颌上。', look='舌头离上下两边的距离，能不能自由动一点。',
         why='没有来源写明 90° 的位置。90° 在范围 55–130 的中段，作者 rest 是 130（舌头在下）。',
         report='TON 往上 3 mm，顶到上颚'),
    dict(n=2, title='下唇', names='LLL / LLR', parts=[89, 109, 148, 183], region='mouth', views=(FRONT, SIDE), level='低',
         want='两侧下唇等高，左右对称。', look='正面看两侧下唇的高度差。',
         why='没有来源写明 90° 的位置。作者 rest 是 LLL 82、LLR 85，所以 90° 时两侧都会比作者的中位略偏上，属于正常。',
         report='LLR 比 LLL 低 2 mm'),
    dict(n=3, title='嘴角前后', names='CLL / CLR', parts=[95, 100, 130, 144], region='mouth', views=(FRONT, SIDE), level='中',
         want='两侧嘴角都在最窄位，左右对称。', look='两个嘴角到中线的距离。',
         why='config 写 90 = 窄。这是行程的一端，再往窄的方向没有余量。',
         report='CLL 嘴角比 CLR 靠外 3 mm'),
    dict(n=4, title='下巴', names='JL / JR', parts=[176, 185] + by_name('JawLink', 'Part 33'), region='mouth', views=(FRONT, SIDE), level='中',
         want='下巴闭合，两侧连杆对称，两个 MG996R 不互相顶。', look='上下牙之间的缝是否左右一样，有没有歪。',
         why='组装文档和 config 都写 90 = 闭。模型里上下牙之间有一点缝，以闭合且不顶为准。',
         report='下巴右手边比左手边低 2 mm'),
    dict(n=5, title='嘴角上下', names='CUL / CUR', parts=[94, 123, 157, 83], region='mouth', views=(FRONT, SIDE), level='低',
         want='两侧嘴角大致等高，连杆不顶。', look='两个嘴角的高度差。',
         why='没有来源写明 90° 的位置。两侧 config 不对称（CUL 100–60、CUR 75–105），90° 时 CUR 比 CUL 更偏"笑"，有一点高度差不一定是错。',
         report='CUR 嘴角比 CUL 高 4 mm'),
    dict(n=6, title='上唇', names='LUL / LUR', parts=[91, 149, 159, 106], region='mouth', views=(FRONT, SIDE), level='低',
         want='两侧上唇等高，左右对称。', look='正面看两侧上唇的高度差。',
         why='没有来源写明绝对位置，但两侧范围互为镜像，所以左右对称这一条是可靠的。作者 rest 是 75 / 105，90° 时上唇比 rest 低。',
         report='LUL 比 LUR 高 2 mm'),
    dict(n=7, title='眉外侧', names='LO / RO', parts=[79], mirror=True, region='brow', views=(FRONT, TOP), level='低',
         want='两侧眉尾等高，左右对称。', look='两侧眉尾的高度差。',
         why='没有来源写明绝对位置，但两侧范围互为镜像。作者 rest 是 100 / 80，90° 时眉毛比 rest 低。',
         report='LO 比 RO 高 3 mm'),
    dict(n=8, title='眉内侧', names='LI / RI', parts=[75], mirror=True, region='brow', views=(FRONT, TOP), level='低',
         want='两侧眉头等高，左右对称。', look='两侧眉头的高度差。',
         why='没有来源写明绝对位置，但两侧范围互为镜像。作者 rest 是 80 / 100，90° 时眉毛比 rest 低。',
         report='RI 比 LI 低 2 mm'),
    dict(n=9, title='下眼皮', names='BL / BR', parts=[40, 51, 28, 29] + by_name('LidTR'), region='eye', views=(FRONT, TOP), level='高',
         want='下眼皮合到中间，和上眼皮对齐。舵盘臂向眼球倾斜约 20°。', look='眼皮中缝的位置，两眼是否一致。',
         why='EyeMech 官方校准：回中时眼皮在中间合上。这是行程的一端。模型图里眼皮留着一条缝，以官方说明为准。',
         report='BL 比中缝低 3 mm，没合上'),
    dict(n=10, title='上眼皮', names='TL / TR', parts=[43, 52, 30, 31] + by_name('LidBR'), region='eye', views=(FRONT, TOP), level='高',
         want='上眼皮合到中间，和下眼皮对齐。舵盘臂向眼球倾斜约 20°。', look='眼皮中缝的位置，两眼是否一致。',
         why='EyeMech 官方校准：回中时眼皮在中间合上。这是行程的一端。模型图里眼皮留着一条缝，以官方说明为准。',
         report='TR 比中缝高 2 mm，没合上'),
    dict(n=11, title='眼球左右', names='LR', parts=[35, 54] + EYEBALL, region='eye', views=(FRONT, TOP), level='高',
         want='两眼朝正前方。CentralServoHorn 舵盘臂朝正后。', look='俯视看两眼是否正对前方，舵盘臂是否在中线上。',
         why='EyeMech 官方校准。', report='两眼向我的左手边偏 10°'),
    dict(n=12, title='眼球上下', names='UD', parts=[61, 47] + EYEBALL, region='eye', views=(FRONT, SIDE), level='高',
         want='两眼朝正前方，不上不下。VerticalHorn 舵盘臂朝正上。', look='侧面看眼球是否水平朝前，舵盘臂是否竖直。',
         why='EyeMech 官方校准。', measured='已报告：90° 时向下约 30°，还伴有嗡嗡声（来源待确认）。',
         report='两眼向下 30°'),
]


def b64(im):
    b = io.BytesIO()
    im = im.convert('RGBA')
    flat = Image.new('RGB', im.size, 'white')
    flat.paste(im, mask=im.split()[3])
    flat.save(b, 'PNG', optimize=True)
    return base64.b64encode(b.getvalue()).decode()


def mirror(T):
    return T * np.array([-1.0, 1, 1])


def color(gi):
    x = OBJS[gi]['c'][0]
    return MID if abs(x) < 8 else (LEFT if x < 0 else RIGHT)


BASE = [o['gi'] for o in OBJS if o['name'] not in HIDE and not o['module'].startswith('06')]


def view(g, v):
    d, up, label = v
    parts = set(g['parts'])
    region = [i for i in BASE if OBJS[i]['module'][:2] in REGION[g['region']]]
    shown = BASE if v is FRONT else region
    items = [(S.tris(i), color(i) if i in parts else CTX, i) for i in shown]
    fit = [S.pts(i) for i in region]
    if g['region'] == 'brow':
        # 模型只画了一侧的眉毛舵机，另一侧镜像
        fit += [mirror(S.pts(i)) for i in region]
    if g.get('mirror'):
        items += [(mirror(S.tris(i)), RIGHT, i + 1000) for i in g['parts']]
    im, _, _ = render(items, d, W=560, H=560, fit=np.concatenate(fit), up=up, margin=0.04)
    return f'<figure><img alt="{g["title"]} {label}" src="data:image/png;base64,{b64(im)}"><figcaption>{label}</figcaption></figure>'


CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1f2328;--dim:#5f6670;--line:#e2e0d8;--hi:#1a7f4b;--mid:#a86a00;--lo:#b3412f}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--card:#1f2228;--ink:#e8e8e6;--dim:#a0a6b0;--line:#33363d;--hi:#4cc38a;--mid:#e0a84a;--lo:#ff8f7f}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"PingFang SC",sans-serif}
main{max-width:920px;margin:0 auto;padding:24px 16px 64px}h1{font-size:26px;margin:0 0 6px}h2{font-size:19px;margin:0}
.lead{color:var(--dim);margin:0 0 16px}section{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:16px;margin:14px 0}
.top{display:flex;justify-content:space-between;gap:12px;align-items:baseline;flex-wrap:wrap}code{font:14px ui-monospace,Menlo,monospace}
.lv{font-size:13px;font-weight:600}.高{color:var(--hi)}.中{color:var(--mid)}.低{color:var(--lo)}
.imgs{display:grid;grid-template-columns:1fr 1fr;gap:10px;margin:12px 0}figure{margin:0}img{width:100%;display:block;background:#fff;border:1px solid var(--line);border-radius:6px}
figcaption{font-size:13px;color:var(--dim);text-align:center;padding-top:3px}
dl{display:grid;grid-template-columns:76px 1fr;gap:4px 10px;margin:0}dt{color:var(--dim)}dd{margin:0}.meas{color:var(--lo);font-weight:600}
.key span{display:inline-block;width:12px;height:12px;border-radius:3px;margin:0 4px 0 12px;vertical-align:-1px}
table{border-collapse:collapse;width:100%}td,th{text-align:left;padding:5px 8px;border-bottom:1px solid var(--line)}
@media (max-width:560px){.imgs{grid-template-columns:1fr}}
"""


def section(g):
    meas = f'<dt>实测</dt><dd class="meas">{g["measured"]}</dd>' if g.get('measured') else ''
    return (f'<section id="g{g["n"]}"><div class="top"><h2>{g["n"]}. {g["title"]} <code>{g["names"]}</code></h2>'
            f'<span class="lv {g["level"]}">标准可信度：{g["level"]}</span></div>'
            f'<div class="imgs">{"".join(view(g, v) for v in g["views"])}</div>'
            f'<dl><dt>应该</dt><dd>{g["want"]}</dd><dt>看哪里</dt><dd>{g["look"]}</dd>'
            f'<dt>依据</dt><dd>{g["why"]}</dd>{meas}<dt>这样报</dt><dd>“{g["report"]}”</dd></dl></section>')


page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>舵机标定图</title><style>{CSS}</style></head><body><main>
<h1>舵机标定图</h1>
<p class="lead">每组舵机发 90° 时实物应该是什么样。从下到上逐组对照，告诉我朝哪个方向偏了多少。</p>
<section><h2>怎么用</h2>
<p>舵机没有角度反馈，只能靠看。每组通电到 90° 后对照下面的图和文字，按“部位 + 方向 + 多少”报给我，mm 或度都行，估计值就够。左右一律按<b>面对机器人</b>说。</p>
<p class="key">图中颜色：<span style="background:#ed8020"></span>你的左手边<span style="background:#2973d9"></span>你的右手边<span style="background:#cc3373"></span>中间单个舵机</p>
<table><tr><th>可信度</th><th>含义</th></tr>
<tr><td class="高">高</td><td>有 EyeMech 官方校准说明，偏了就要修。</td></tr>
<tr><td class="中">中</td><td>来自本项目文档和 config 的约定，没有官方说明。</td></tr>
<tr><td class="低">低</td><td>没有来源写明 90° 的绝对位置，主要看左右对称和有没有顶住。图只是参考：模型的姿态没有标明对应哪个角度。</td></tr></table>
</section>
{"".join(section(g) for g in GROUPS)}
</main></body></html>"""
open(OUT, 'w', encoding='utf8').write(page)
print(OUT, f'{len(page) / 1e6:.1f} MB')
