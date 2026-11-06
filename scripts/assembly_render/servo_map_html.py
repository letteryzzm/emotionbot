"""生成 docs/舵机接线与上电检查.html：舵机位置图、插口表、万用表清单、首次接线步骤。
  .venv/bin/python scripts/assembly_render/servo_map_html.py
图里的左右都是"面对机器人"的方向：屏幕右 = 模型 x+ = 机器人自己的左边。
"""
import base64
import io
import json
import os

import numpy as np

from render import Scene, render

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
S = Scene(os.path.join(ROOT, 'outputs/assembly/mesh.npz'))
OUT = os.path.join(ROOT, 'docs/舵机接线与上电检查.html')

CTX = (0.86, 0.86, 0.84)
GROUP = {'eye': (0.30, 0.55, 0.85), 'lidT': (0.93, 0.55, 0.20), 'lidB': (0.35, 0.68, 0.40), 'brow': (0.62, 0.45, 0.80),
         'lip': (0.85, 0.35, 0.40), 'corner': (0.93, 0.55, 0.20), 'corner2': (0.35, 0.68, 0.40), 'low': (0.30, 0.55, 0.85),
         'jaw': (0.45, 0.45, 0.50), 'ton': (0.62, 0.45, 0.80)}


def b64(im):
    b = io.BytesIO()
    im.convert('RGBA').save(b, 'PNG', optimize=True)
    return base64.b64encode(b.getvalue()).decode()


def mirror(T):
    return T * np.array([-1.0, 1, 1])


def figure(items, dirv, up, fit, labels, W=1000, H=620, inset=190, aria=''):
    """labels: (模型点, 左/右栏, 标准名, 翻转名, 说明)。图放在中间，标签排两侧，引线连到舵机。"""
    im, proj, _ = render(items, dirv, W=W - 2 * inset, H=H, up=up, fit=fit, margin=0.05)
    out = [f'<image href="data:image/png;base64,{b64(im)}" x="{inset}" y="0" width="{W - 2 * inset}" height="{H}"/>']
    for col in ('L', 'R'):
        rows = [l for l in labels if l[1] == col]
        rows.sort(key=lambda l: proj(np.array(l[0], float))[1])
        step = H / (len(rows) + 1)
        for i, (p, _, std, flip, note) in enumerate(rows, 1):
            x, y = proj(np.array(p, float))
            x += inset
            ty = step * i
            bx = 8 if col == 'L' else W - inset + 14
            ex = inset - 6 if col == 'L' else W - inset + 6
            anchor = f'x="{bx}"'
            out.append(f'<path d="M{ex} {ty:.0f} L{x:.0f} {y:.0f}" class="lead"/><circle cx="{x:.0f}" cy="{y:.0f}" r="5" class="dot"/>')
            out.append(f'<text {anchor} y="{ty - 3:.0f}" class="nm" data-std="{std}" data-flip="{flip}">{std}</text>'
                       f'<text {anchor} y="{ty + 17:.0f}" class="nt">{note}</text>')
    return f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="{aria}">{"".join(out)}</svg>'


def eye_fig():
    ctx = [(S.tris(g), CTX, g) for g in (44, 45, 59, 34, 33, 49, 36, 37, 39)]
    it = ctx + [(S.tris(35), GROUP['eye'], 35), (S.tris(61), GROUP['eye'], 61), (S.tris(54), GROUP['eye'], 54), (S.tris(47), GROUP['eye'], 47)]
    it += [(S.tris(g), GROUP['lidT'], g) for g in (43, 52, 30, 31)] + [(S.tris(g), GROUP['lidB'], g) for g in (40, 51, 28, 29)]
    P = np.concatenate([S.pts(g) for g in (44, 35, 46, 53)])
    lb = [((-43, 1.8, 6), 'L', 'BL', 'BR', '后排 · 长连杆 · 下眼皮'), ((-43, -23.4, 11), 'L', 'TL', 'TR', '前排 · 短连杆 · 上眼皮'),
          ((0, -63, 13), 'L', 'LR', 'LR', '两眼中间 · 眼球左右'),
          ((43, 1.8, 6), 'R', 'BR', 'BL', '后排 · 长连杆 · 下眼皮'), ((43, -23.4, 11), 'R', 'TR', 'TL', '前排 · 短连杆 · 上眼皮'),
          ((-1, -23.4, 12), 'R', 'UD', 'UD', '底板中间 · 眼球上下')]
    return figure(it, (0, 0, -1), (0, 1, 0), P, lb, H=560, aria='眼部舵机俯视图')


def brow_fig():
    it = [(S.tris(77), CTX, 77)]
    for g in (75, 79):
        it += [(S.tris(g), GROUP['brow'], g), (mirror(S.tris(g)), GROUP['brow'], g + 1000)]
    P = np.concatenate([S.pts(77), S.pts(75), mirror(S.pts(75)), S.pts(79), mirror(S.pts(79))])
    lb = [((-48, -22, 61), 'L', 'LO', 'RO', '外侧 · 靠太阳穴'), ((-29, -57, 61), 'L', 'LI', 'RI', '内侧 · 靠眉心'),
          ((48, -22, 61), 'R', 'RO', 'LO', '外侧 · 靠太阳穴'), ((29, -57, 61), 'R', 'RI', 'LI', '内侧 · 靠眉心')]
    return figure(it, (0, 0, -1), (0, 1, 0), P, lb, H=470, aria='眉毛舵机俯视图')


def mouth_fig():
    it = [(S.tris(188), CTX, 188), (S.tris(113), CTX, 113)]
    it += [(S.tris(g), GROUP['jaw'], g) for g in (176, 185)]
    for grp, gs in (('lip', (91, 149, 159, 106)), ('corner', (94, 123, 157, 83)), ('corner2', (95, 100, 130, 144)), ('low', (89, 109, 148, 183)), ('ton', (155,))):
        it += [(S.tris(g), GROUP[grp], g) for g in gs]
    P = np.concatenate([S.pts(g) for g in (188, 113, 176, 185, 89, 109)])
    # 主图从正前方看。机器人左侧 = 屏幕右
    lb = [((-34, -66, -36), 'L', 'LUR', 'LUL', '上颌座前部 · Part_35 · 上唇'), ((-44, -36, -39), 'L', 'CUR', 'CUL', '中间上面 · Part_42 · 嘴角上下'),
          ((-42, -35, -68), 'L', 'CLR', 'CLL', '中间下面 · Part_43 · 嘴角前后'), ((-35, -60, -95), 'L', 'LLR', 'LLL', '下颌座两侧 · Part_38 · 下唇'),
          ((-38.5, -4, -53), 'L', 'JL', 'JR', 'MG996R · Part_33 · 下颌'),
          ((34, -66, -36), 'R', 'LUL', 'LUR', '上颌座前部 · ULLLinkA · 上唇'), ((44, -36, -39), 'R', 'CUL', 'CUR', '中间上面 · Part_31 · 嘴角上下'),
          ((42, -35, -68), 'R', 'CLL', 'CLR', '中间下面 · Part_32 · 嘴角前后'), ((35, -60, -95), 'R', 'LLL', 'LLR', '下颌座两侧 · Part_27 · 下唇'),
          ((38.5, -4, -53), 'R', 'JR', 'JL', 'MG996R · JawLink · 下颌'), ((1.4, -30, -105), 'R', 'TON', 'TON', '下颌座中间 · 舌头')]
    return figure(it, (0, 1, 0), (0, 0, 1), P, lb, H=660, inset=235, aria='嘴部舵机正视图')


def side_fig():
    it = [(S.tris(188), CTX, 188), (S.tris(113), CTX, 113)]
    for grp, gs in (('lip', (149, 159)), ('corner', (94, 157)), ('corner2', (95, 130)), ('low', (89, 148))):
        it += [(S.tris(g), GROUP[grp], g) for g in gs]
    P = np.concatenate([S.pts(g) for g in (188, 113)])
    # 从机器人左侧看，脸朝屏幕左
    im, proj, _ = render(it, (-1, 0, 0), W=620, H=520, fit=P, up=(0, 0, 1), margin=0.06)
    t = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="620" height="520"/>']
    for (y, z, n) in ((-52.7, -34.5, 'U4 上唇'), (-20.3, -44.4, 'U6 嘴角上下'), (-23.3, -61.6, 'U7 嘴角前后'), (-43.5, -96.8, 'U5 下唇')):
        x, yy = proj(np.array([60, y, z], float))
        t.append(f'<circle cx="{x:.0f}" cy="{yy:.0f}" r="5" class="dot"/><text x="{x + 9:.0f}" y="{yy - 8:.0f}" class="sd">{n}</text>')
    t.append('<text x="12" y="26" class="sd">← 脸朝这边</text>')
    return f'<svg viewBox="0 0 620 520" role="img" aria-label="嘴部舵机侧视图">{"".join(t)}</svg>'


WIRE = {'S': '#f08c00', '+': '#d32f2f', '-': '#5d4037'}
FLIPSIDE = {'左手边': '右手边', '右手边': '左手边'}


def board_fig(f, title, usb_refs, groups, aria):
    """整板定位图 + 排针放大图。groups: [(排针名, [(名字, 功能, 位置), (...)])]，名字为空 = 不接。
    板子按 USB 朝上、正面朝自己画，和丝印方向一致（json 的 y 向上）。"""
    d = json.load(open(os.path.join(ROOT, f'pcb/render/{f}.json')))
    comps = {c['ref']: c for c in d['comps']}
    rect = max((o for o in d['outline'] if 'pts' in o), key=lambda o: float(np.prod(np.ptp(np.array(o['pts']), axis=0))))
    allp = np.array([q for o in d['outline'] if 'pts' in o for q in o['pts']])
    x0, y0 = allp.min(0); x1, y1 = allp.max(0)
    W, BH = 1000, 400
    sc = min((BH - 30) / (y1 - y0), 620 / (x1 - x0))
    ox = (W - (x1 - x0) * sc) / 2
    X = lambda x: ox + (x - x0) * sc  # noqa: E731
    Y = lambda y: 15 + (y1 - y) * sc  # noqa: E731
    o = []
    for ol in d['outline']:
        if 'pts' not in ol:
            continue
        pts = ' '.join(f'{X(a):.1f},{Y(b):.1f}' for a, b in ol['pts'])
        big = ol is rect
        o.append(f'<polygon points="{pts}" fill="{"#1f6b43" if big else "#fff"}" stroke="#123f28" stroke-width="1.5"/>')
    for t in d['tracks']:
        a, b, c, e = t['p']
        o.append(f'<line x1="{X(a):.1f}" y1="{Y(b):.1f}" x2="{X(c):.1f}" y2="{Y(e):.1f}" stroke="#2f8a5b" stroke-opacity=".55" stroke-width="{max(t["w"] * sc, 1):.1f}" stroke-linecap="round"/>')
    for r in usb_refs:
        P = np.array([[q['x'], q['y']] for q in comps[r]['pads']])
        o.append(f'<rect x="{X(P[:, 0].min()) - 5:.1f}" y="{Y(P[:, 1].max()) - 5:.1f}" width="{(np.ptp(P[:, 0])) * sc + 10:.1f}" height="{np.ptp(P[:, 1]) * sc + 10:.1f}" fill="#0e3a24" stroke="#d9d4c3" rx="2"/>')
    o.append(f'<text x="{X(x1) + 16:.0f}" y="36" style="font-size:18px;font-weight:700">↑ USB 这头朝上</text><text x="{X(x1) + 16:.0f}" y="60" style="font-size:15px;fill:#4f5660!important">深色两条是 Pico 位</text>')
    H = np.array([[q['x'], q['y']] for g, _ in groups for q in comps[g.split()[0]]['pads']])
    for g, _ in groups:
        for q in comps[g.split()[0]]['pads']:
            o.append(f'<circle cx="{X(q["x"]):.1f}" cy="{Y(q["y"]):.1f}" r="{max(19 * sc, 1.6):.1f}" fill="#e7c55a"/>')
    hx0, hx1, hy0, hy1 = X(H[:, 0].min()) - 7, X(H[:, 0].max()) + 7, Y(H[:, 1].max()) - 7, Y(H[:, 1].min()) + 7
    o.append(f'<rect x="{hx0:.1f}" y="{hy0:.1f}" width="{hx1 - hx0:.1f}" height="{hy1 - hy0:.1f}" fill="none" stroke="#ffd43b" stroke-width="3" rx="3"/>')
    # 放大图
    top = BH + 42
    n = sum(len(c) for _, c in groups)
    gap, left = 16, 118
    pitch = (W - left - 14 - gap * (len(groups) - 1)) / n
    o.append(f'<path d="M{hx0:.0f} {hy1:.0f} L{left - 14} {top - 6} M{hx1:.0f} {hy1:.0f} L{W - 8} {top - 6}" stroke="#c9a200" stroke-width="1.5" stroke-dasharray="5 5" fill="none"/>')
    rows = [('S', '橙 / 黄线'), ('+', '红线'), ('-', '棕 / 黑线')]
    ry = [top + 34, top + 84, top + 134]
    for (k, txt), y in zip(rows, ry):
        o.append(f'<text x="10" y="{y - 2}" style="font-size:20px;font-weight:800">{"−" if k == "-" else k} 行</text><text x="10" y="{y + 16}" style="font-size:13px;fill:#4f5660!important">{txt}</text>')
    x = left
    fs = 25 if n <= 6 else 17
    for g, cols in groups:
        gw = pitch * len(cols)
        o.append(f'<rect x="{x + 3:.1f}" y="{top}" width="{gw - 6:.1f}" height="164" rx="7" fill="#1f6b43"/>')
        o.append(f'<text x="{x + gw / 2:.1f}" y="{top - 8}" text-anchor="middle" style="font-size:14px;font-weight:700">{g}</text>')
        for nm, fn, loc in cols:
            c = x + pitch / 2
            on = bool(nm)
            for (k, _), y in zip(rows, ry):
                o.append(f'<circle cx="{c:.1f}" cy="{y}" r="15" fill="{WIRE[k] if on else "#7d8a82"}" stroke="#fff" stroke-width="2"/>')
            o.append(f'<text x="{c:.1f}" y="{top + 196}" text-anchor="middle" style="font-size:{fs}px;font-weight:800;{"" if on else "fill:#8a9096!important"}">{nm or "不接"}</text>')
            o.append(f'<text x="{c:.1f}" y="{top + 217}" text-anchor="middle" style="font-size:13px;fill:#4f5660!important">{fn}</text>')
            if loc in FLIPSIDE:
                o.append(f'<text x="{c:.1f}" y="{top + 236}" text-anchor="middle" style="font-size:13px;font-weight:700;fill:#0b6b5a!important" data-std="{loc}" data-flip="{FLIPSIDE[loc]}">{loc}</text>')
            elif loc:
                o.append(f'<text x="{c:.1f}" y="{top + 236}" text-anchor="middle" style="font-size:13px;fill:#4f5660!important">{loc}</text>')
            x += pitch
        x += gap
    Ht = top + 250
    return f'<figure><div class="tw"><svg style="min-width:680px" viewBox="0 0 {W} {Ht}" role="img" aria-label="{aria}">{"".join(o)}</svg></div><figcaption>{title}</figcaption></figure>'


def eye_board():
    return board_fig('eye', '板子转到 USB 朝上、正面朝自己。上半是整板，黄框是舵机排针，下半是放大图。一列插一个舵机，丝印 0–5 从左到右。', ['H1', 'H2'],
                     [('J1 · 丝印 0 1', [('LR', '眼球左右', '中间'), ('UD', '眼球上下', '中间')]),
                      ('J2 · 丝印 2 3', [('TL', '上眼皮', '左手边'), ('BL', '下眼皮', '左手边')]),
                      ('J3 · 丝印 4 5', [('TR', '上眼皮', '右手边'), ('BR', '下眼皮', '右手边')])], '眼睛板舵机接线图')


def brow_board():
    return board_fig('eye', '同款板子，方向相同。J3 这两列不接。', ['H1', 'H2'],
                     [('J1 · 丝印 0 1', [('LO', '眉外侧', '左手边'), ('LI', '眉内侧', '左手边')]),
                      ('J2 · 丝印 2 3', [('RI', '眉内侧', '右手边'), ('RO', '眉外侧', '右手边')]),
                      ('J3 · 丝印 4 5', [('', '', ''), ('', '', '')])], '眉毛板舵机接线图')


def mouth_board():
    return board_fig('mouth', '板子转到 USB 朝上、正面朝自己。12 列从左到右，U3 是最左边的两列，板上丝印也印着这些名字。', ['U9', 'U10'],
                     [('U3 下颌', [('JL', 'MG996R', '左手边'), ('JR', 'MG996R', '右手边')]),
                      ('U4 上唇', [('LUL', '上唇', '右手边'), ('LUR', '上唇', '左手边')]),
                      ('U5 下唇', [('LLL', '下唇', '右手边'), ('LLR', '下唇', '左手边')]),
                      ('U6 嘴角上下', [('CUL', '笑', '右手边'), ('CUR', '笑', '左手边')]),
                      ('U7 嘴角前后', [('CLL', '变宽', '右手边'), ('CLR', '变宽', '左手边')]),
                      ('U8', [('TON', '舌头', '中间'), ('', '', '')])], '嘴部板舵机接线图')


def ck(id_, html):
    return f'<label class="ck"><input type="checkbox" data-k="{id_}"><span>{html}</span></label>'


def table(head, rows, cls=''):
    h = ''.join(f'<th>{c}</th>' for c in head)
    b = ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows)
    return f'<div class="tw"><table class="{cls}"><thead><tr>{h}</tr></thead><tbody>{b}</tbody></table></div>'


def side(std):
    """std 是 '左' 或 '右'，LR 测试翻转时自动换"""
    o = '右' if std == '左' else '左'
    return f'<span class="sw" data-std="{std}手边" data-flip="{o}手边">{std}手边</span>'


def checks(prefix, rows):
    return ''.join(ck(f'{prefix}{i}', r) for i, r in enumerate(rows))


ACTION = [('LR', '<code>LR=110</code>', '上一节的 LR 测试，看结果选表'), ('UD', '<code>UD=100</code>', '眼球向上'),
          ('TL', '<code>TL=100</code>', '上眼皮睁开'), ('TR', '<code>TR=80</code>', '上眼皮睁开'),
          ('BL', '<code>BL=80</code>', '下眼皮睁开'), ('BR', '<code>BR=100</code>', '下眼皮睁开'),
          ('LO', '<code>LO=95</code>', '外侧眉毛抬起'), ('RO', '<code>RO=85</code>', '外侧眉毛抬起'),
          ('LI', '<code>LI=85</code>', '内侧眉毛抬起'), ('RI', '<code>RI=95</code>', '内侧眉毛抬起'),
          ('JL', '<code>JL</code>，再 <code>JL=85</code>', '下巴张开（JR 松开）'), ('JR', '<code>JR</code>，再 <code>JR=95</code>', '下巴张开（JL 松开）'),
          ('LUL', '<code>LUL=85</code>', '上唇这一半抬起'), ('LUR', '<code>LUR=95</code>', '上唇这一半抬起'),
          ('LLL', '<code>LLL=95</code>', '下唇这一半往下'), ('LLR', '<code>LLR=85</code>', '下唇这一半往下'),
          ('CUL', '<code>CUL=85</code>', '嘴角上抬'), ('CUR', '<code>CUR=95</code>', '嘴角上抬'),
          ('CLL', '<code>CLL=95</code>', '嘴角往后，略往下'), ('CLR', '<code>CLR=85</code>', '嘴角往后，略往下'),
          ('TON', '<code>TON=100</code>', '舌头往下')]

CSS = """
:root{--bg:#fbfaf7;--card:#fff;--ink:#1f2328;--mut:#5d6570;--line:#dcdad3;--acc:#0b6b5a;--warn:#fff3df;--warnl:#b86e00;--bad:#fde8e6;--badl:#b3261e;--code:#f0efea;--fig:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#15181b;--card:#1d2125;--ink:#e8e8e6;--mut:#a3aab2;--line:#343a40;--acc:#5ad1b8;--warn:#3a2c12;--warnl:#f0b45a;--bad:#3d1c1a;--badl:#f2938b;--code:#2a2f34;--fig:#fff}}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.65 -apple-system,"PingFang SC","Hiragino Sans GB",sans-serif}
main{max-width:1000px;margin:auto;padding:24px 16px 70px}
h1{font-size:28px;line-height:1.25;margin:6px 0 8px}h2{font-size:22px;margin:44px 0 10px;padding-top:6px}h3{font-size:17px;margin:24px 0 6px}
p{margin:8px 0}.sub{color:var(--mut)}
nav{display:flex;flex-wrap:wrap;gap:6px 14px;margin:14px 0;font-size:15px}a{color:var(--acc)}
code{background:var(--code);padding:1px 5px;border-radius:4px;font:14px ui-monospace,Menlo,monospace}
pre{background:var(--code);padding:10px 12px;border-radius:8px;overflow-x:auto;font:14px/1.5 ui-monospace,Menlo,monospace;margin:8px 0}pre code{padding:0;background:none}
.tw{overflow-x:auto;margin:10px 0}table{border-collapse:collapse;width:100%;background:var(--card);font-size:15px}
th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}th{font-weight:600;background:var(--code)}
.note,.warn,.bad{padding:10px 13px;border-radius:8px;margin:12px 0;border-left:4px solid}
.note{background:var(--card);border-color:var(--acc)}.warn{background:var(--warn);border-color:var(--warnl)}.bad{background:var(--bad);border-color:var(--badl)}
figure{margin:12px 0}figcaption{color:var(--mut);font-size:14px;margin-top:4px}
svg{display:block;width:100%;height:auto;background:var(--fig);border:1px solid var(--line);border-radius:8px}
svg text{fill:#1f2328;font-family:-apple-system,"PingFang SC",sans-serif}
.nm{font-size:24px;font-weight:800}.nt{font-size:14px;fill:#4f5660!important}.sd{font-size:17px;font-weight:700;paint-order:stroke;stroke:#fff;stroke-width:4px}
.lead{stroke:#6d747c;stroke-width:1.3;fill:none}.dot{fill:#c62828;stroke:#fff;stroke-width:1.5}
.ck{display:flex;gap:9px;padding:6px 2px;border-bottom:1px solid var(--line);cursor:pointer}.ck input{width:19px;height:19px;flex:none;margin-top:3px;accent-color:var(--acc)}
.ck:has(input:checked) span{color:var(--mut)}
.seg{display:flex;flex-wrap:wrap;gap:8px;margin:10px 0}.seg button{font:inherit;padding:8px 12px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer}
.seg button[aria-pressed=true]{background:var(--acc);border-color:var(--acc);color:#fff}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]) .seg button[aria-pressed=true]{color:#10231f}}
ol{padding-left:22px}li{margin:5px 0}
.pending{color:var(--warnl);font-weight:600}
@media print{.seg{display:none}}
"""

JS = """
const K='head-wiring-v1',S=(()=>{try{return JSON.parse(localStorage.getItem(K))||{}}catch(e){return {}}})();
const save=()=>{try{localStorage.setItem(K,JSON.stringify(S))}catch(e){}};
document.querySelectorAll('input[data-k]').forEach(c=>{c.checked=!!S[c.dataset.k];c.onchange=()=>{S[c.dataset.k]=c.checked;save();}});
function apply(v){document.querySelectorAll('[data-std]').forEach(e=>{e.textContent=v==='flip'?e.dataset.flip:e.dataset.std});
 document.querySelectorAll('.seg button').forEach(b=>b.setAttribute('aria-pressed',b.dataset.v===v));
 document.querySelectorAll('.only-flip').forEach(e=>e.hidden=v!=='flip');}
document.querySelectorAll('.seg button').forEach(b=>b.onclick=()=>{S.lr=b.dataset.v;save();apply(b.dataset.v)});
apply(S.lr||'std');
document.getElementById('reset').onclick=()=>{Object.keys(S).forEach(k=>delete S[k]);save();document.querySelectorAll('input[data-k]').forEach(c=>c.checked=false);apply('std')};
"""


def page():
    eye_rows = [('0', 'GP8', 'LR', '两眼中间，轴朝上'), ('1', 'GP9', 'UD', '底板中间'),
                ('2', 'GP13', 'TL', f'{side("左")}，前排'), ('3', 'GP12', 'BL', f'{side("左")}，后排'),
                ('4', 'GP11', 'TR', f'{side("右")}，前排'), ('5', 'GP10', 'BR', f'{side("右")}，后排')]
    brow_rows = [('0', 'GP8', 'LO', f'{side("左")}，外侧'), ('1', 'GP9', 'LI', f'{side("左")}，内侧'),
                 ('2', 'GP13', 'RI', f'{side("右")}，内侧'), ('3', 'GP12', 'RO', f'{side("右")}，外侧'), ('4、5', '', '空', '不接')]
    mouth_rows = [('U3', 'JL（GP4）', 'JR（GP5）', '下颌 MG996R', f'JL 在{side("左")}，零件 Part_33', f'JR 在{side("右")}，零件 JawLink'),
                  ('U4', 'LUL（GP6）', 'LUR（GP7）', '上唇', f'LUL 在{side("右")}，ULLLinkA', f'LUR 在{side("左")}，Part_35'),
                  ('U5', 'LLL（GP8）', 'LLR（GP9）', '下唇', f'LLL 在{side("右")}，Part_27', f'LLR 在{side("左")}，Part_38'),
                  ('U6', 'CUL（GP10）', 'CUR（GP11）', '嘴角上下（笑）', f'CUL 在{side("右")}，Part_31', f'CUR 在{side("左")}，Part_42'),
                  ('U7', 'CLL（GP12）', 'CLR（GP13）', '嘴角前后（变宽）', f'CLL 在{side("右")}，Part_32', f'CLR 在{side("左")}，Part_43'),
                  ('U8', 'TON（GP14）', 'EXA（GP15）', '舌头 / 备用', 'TON 在下颌座中间，Part_20', 'EXA 不接')]
    off1 = ['XH 座 VIN 和 GND：<b>不响</b>，读数慢慢升高是电容在充电（眼板、眉板各量一次）', '排针 + 行和 − 行：<b>不响</b>（眼板、眉板）',
            'VIN 和 H1 第 2 脚（USB 端数起）：<b>响</b>，说明 C12 短接好了（眼板、眉板）', '每一列 S 和 +：<b>不响</b>（眼板、眉板，各 6 列）',
            'XT60 的 + 和 −：<b>不响</b>（嘴部板）', '任一排针 + 行和 − 行：<b>不响</b>（嘴部板）',
            'U10 从 USB 端数第 2 位（VSYS）和第 3 位（GND）：<b>不响</b>（嘴部板）', '每一列 S 和 +：<b>不响</b>（嘴部板，12 列）',
            '二极管档，红表笔接输入侧、黑表笔接 V+ 或输出侧：眼板、眉板的 D2，嘴部板的 D1、D2 都是 <b>0.15–0.35 V</b>，表笔对调后显示 OL']
    mount = ['板子固定以后，再量一次三块板的 VIN–GND 和 V+–GND：<b>不响</b>。响了先松螺丝，多半是螺丝或铜柱压到了走线']
    cable = ['转接头 + 和 −：<b>不响</b>', '不接板子时通电，转接头、2 个 XH 插头、XT60：都是 <b>5.0–5.2 V</b>，超过 5.5 V 就不要往下接。量完断电',
             '断电，XH 插到板子上，转接头 + 到 H1 第 2 脚 <b>响</b>，转接头 − 到 H1 第 3 脚 <b>响</b>（眼板、眉板）。都不响多半是 XH 线反了']
    power = ['眼板、眉板：排针 + 和 − 是 <b>4.7–4.9 V</b>，H1 第 2、3 脚约 <b>5.0 V</b>', '嘴部板：U3 的 + 和 − 是 <b>4.7–4.9 V</b>。接近 0 或为负值就马上断电，查 XT60 红黑',
             '嘴部板：BOARD POWER 输出是 <b>3.5–4 V</b>，偏低是正常的。插上跳线帽后，U10 的 VSYS 读数相同']
    sw = ['眼睛板 SW1 第 1、2 脚<b>导通 = 正常运行</b>，不通 = 校准。拨到校准档的那一下，全部舵机会通电到 90°。用记号笔标出档位（量通断时不插 Pico）',
          '嘴部板 SW1 第 1、2 脚<b>导通 = 校准</b>，不通 = 正常运行，和眼睛板<b>相反</b>。也标出来']
    act = ''.join(f'<tr><td>{ck("a" + n, "<b>" + n + "</b>")}</td><td>{c}</td><td>{w}</td></tr>' for n, c, w in ACTION)
    html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>舵机接线与上电检查</title><style>{CSS}</style></head><body><main>
<h1>舵机接线与上电检查</h1>
<p class="sub">Robot Head α2.0.33 · 2026-11-05 · 文中的左手边、右手边都是<b>你面对机器人的脸</b>时的方向。复选框的进度只存在这个浏览器里。</p>
<nav><a href="#fix">已改了什么</a><a href="#map">舵机在哪</a><a href="#ports">插哪个口</a><a href="#meter">万用表</a><a href="#first">第一次接舵机</a><a href="#act">动作核对</a><a href="#how">不对怎么改</a><a href="#care">注意事项</a></nav>

<div class="bad"><b>眼皮不要一上来就跑表情。</b>全部通电后眼皮会转到全睁（TL 到 160°）。插反时会朝反方向猛转 70°，可能打坏舵盘和连杆。第一次一定按<a href="#first">这里的顺序</a>一个一个来。</div>

<h2 id="fix">已经改了什么</h2>
{table(['问题', '改动', '你要做什么'], [
 ('<b>舵机名的 L/R 不统一</b>：眼、眉、下颌的 L 在面对时的左手边，嘴唇、嘴角的 L 在右手边', '这页的表和图按此重写；<code>firmware/config_*.py</code> 注释写明实际位置', '按这页接线，<b>不要</b>按旧的 焊接流程 里"左/右"的中文说明'),
 ('组装流程 图 7、图 10 的 TL/BL/TR/BR 左右标反', '<code>组装流程.html</code> 已重新生成', '无'),
 ('下唇 LLL/LLR 上下写反', '<code>config_mouth.py</code> 对调 a/b，现在 u=1 是上抬。两端角度不变', '<b>不用重刷</b>固件，固件只用范围和 rest'),
 ('表情模仿按"L = 机器人左"，眼皮、眉毛、眼球左右都会反', '<code>head/actuators.py</code> 加了左右开关，<code>blendshape_map.py</code>、<code>viz.py</code> 按实际位置映射，加了测试', '只在 LR 测试结果相反时改，见<a href="#how">下面</a>'),
 ('图 2 说下颌座是"下唇、下嘴角"', '改成下唇 + 舌头。图 17 的连杆表加上了通道名', '无'),
 ('<code>mpremote repl</code> 按回车发的是 \\r，固件要 \\n，命令可能不生效', '新增 <code>scripts/servo_step.py</code>，一步超过 15° 会拒绝', '用它发命令'),
])}
<div class="note"><b>这些结论是怎么来的：</b>从模型的连杆方向反推，假设舵机角度增大时逆时针转。眼皮、眉毛、下颌方向互相一致，UD 的方向和官方代码的眼皮联动也一致；嘴角用连杆模拟过，笑时上抬约 15 mm，变宽时后移约 12 mm。<b>没有在实物上验证</b>，所以要做第 3 步的 LR 测试和动作核对。</div>

<h2 id="map">舵机在哪</h2>
<p>LR 测试之后选结果，下面所有的图和表都会跟着变：</p>
<div class="seg" role="group" aria-label="LR 测试结果"><button data-v="std">眼球转向你的右手边（预期）</button><button data-v="flip">眼球转向你的左手边</button></div>
<p class="only-flip warn" hidden>已切到相反结果。记得把 <code>head/actuators.py</code> 的 <code>ANGLE_UP_IS_CCW</code> 改成 <code>False</code>。</p>
<h3>眼部（俯视，脸朝下方）</h3>
<figure>{eye_fig()}<figcaption>橙色前排 = 上眼皮，绿色后排 = 下眼皮，蓝色 = 眼球。图的左边就是你面对机器人时的左手边。</figcaption></figure>
<h3>眉毛（俯视，脸朝下方）</h3>
<figure>{brow_fig()}<figcaption>模型只画了一侧的 2 个舵机，另一侧是镜像补上的。</figcaption></figure>
<h3>嘴部（正面）</h3>
<figure>{mouth_fig()}<figcaption>红 = 上唇，橙 = 嘴角上下，绿 = 嘴角前后，蓝 = 下唇，紫 = 舌头，灰 = MG996R。注意嘴唇、嘴角的 L 在右边，下颌的 L 在左边。这是沿用作者的舵机名和角度（JL 90→50、JR 90→130 张嘴），板子丝印也不用改。</figcaption></figure>
<h3>嘴部（侧面，上下 4 排怎么认）</h3>
<figure style="max-width:620px">{side_fig()}<figcaption>左右各一排一样的。名字最好用美纹纸贴到线上再插。</figcaption></figure>

<h2 id="ports">插哪个口</h2>
<p>三块板的排针都是<b>上 S、中 +、下 −</b>：橙/黄线对 S，红线对 +，棕/黑线对 −。一个舵机插一竖列，棕/黑线朝板子边。图下的左手边、右手边是舵机在头上的位置。</p>
<h3>眼睛板</h3>{eye_board()}{table(['丝印', 'GPIO', '名字', '舵机位置'], eye_rows)}
<h3>眉毛板（同款板子）</h3>{brow_board()}{table(['丝印', 'GPIO', '名字', '舵机位置'], brow_rows)}
<h3>嘴部板</h3><p>U3 在 U4 左边，你截图里被标签挡住了。每个排针左列接第一个名字，右列接第二个。</p>
{mouth_board()}{table(['排针', '左列', '右列', '功能', '左列舵机', '右列舵机'], mouth_rows)}

<h2 id="meter">上电前用万用表量什么</h2>
<h3>① 断电，不插 Pico，不接舵机（蜂鸣档）</h3>{checks('m', off1)}
<h3>② 板子上螺丝以后</h3>{checks('n', mount)}
<h3>③ 拨动开关（断电，不插 Pico）</h3>{checks('s', sw)}
<h3>④ 电源线</h3>{checks('c', cable)}
<h3>⑤ 第一次给板子通电（一次一块，不插 Pico，不接舵机）</h3><p>有可调电源就设 5.0 V、限流 0.3 A，电流顶到限流就马上关。</p>{checks('p', power)}

<h2 id="first">第一次接舵机</h2>
<div class="note">固件开机时<b>所有舵机都不发信号</b>，接上 5V 也不会动，选到谁才通电谁。舵机线可以全部插着。眼睛板和嘴部板要刷 2026-11-06 之后的固件。</div>
<ol>
<li>确认已经刷了新固件。<b>先接 5V，再插 USB。</b>断电时先拔 USB。眼板、眉板只插 USB 时，电会从 Pico 倒灌到舵机那一路，电脑 USB 带不动。</li>
<li>运行工具，先做 LR 测试：
<pre><code>cd /Volumes/Robotics/projects/head
.venv/bin/python scripts/servo_step.py
&gt; LR
&gt; LR=100
&gt; LR=110</code></pre>
面对机器人看眼球往哪边转，到<a href="#map">这里</a>选结果。转完发 <code>LR=90</code>。</li>
<li>输入 <code>walk</code>，每个舵机单独通电到 90°，回车换下一个。一直响就发 <code>X</code>，记下名字。</li>
<li>输入名字（比如 <code>TL</code>）只让它通电，再照下面的动作表走 5–10° 小步。听到嗡嗡响就马上输入 <code>X</code> 卸力。</li>
<li>全部通过后，才能发 <code>!C</code> 或跑表情。最后用 <code>.venv/bin/python scripts/servo_check.py</code> 全部扫一遍。</li>
</ol>
<div class="note">第一次通电时舵机会全速转到 90°，因为固件不知道它原来在哪。校准开关只有拨过去的那一下才会让全部舵机通电，测试时别拨它。</div>

<h2 id="act">动作核对表</h2>
<p>这张表<b>不受 LR 测试结果影响</b>，最终以它为准。舵机从 90° 开始。</p>
<div class="tw"><table><thead><tr><th>舵机</th><th>输入</th><th>应该看到</th></tr></thead><tbody>{act}</tbody></table></div>
<p class="sub">JL、JR 通过后再一起试：<code>JL JR</code>，然后 <code>JL=85 JR=95</code>，看下巴不别劲。</p>

<h2 id="how">不对怎么改</h2>
{table(['现象', '怎么改', '要不要重刷'], [
 ('LR 测试眼球转向你的左手边', '上面选"左手边"，表和图自动换。把 <code>head/actuators.py</code> 的 <code>ANGLE_UP_IS_CCW</code> 改成 <code>False</code>', '不用'),
 ('某一对方向反了（比如 TL 往闭的方向走）', '马上 <code>X</code>，断电，对调这一对的插头', '不用'),
 ('只有一个反，它的另一半是对的', '先查舵机是不是放反了、连杆是否接错。不要只改一边的角度', '看情况'),
 ('90° 时位置不对，差一点', '拔下舵盘或连杆错一齿。别掰', '不用'),
 ('不到范围就顶死、嗡嗡响', '<code>X</code> 卸力，慢慢试出极限，在 <code>firmware/config_*.py</code> 里把 a 或 b 收回，留 5°', '要，<code>firmware/flash.sh eyes</code>（<code>brows</code> / <code>mouth</code>）'),
 ('舵机抖或不动', '量该列 + − 电压，看插头有没有插反，检查 S 列焊点', '不用'),
 ('Pico 反复重启', '舵机太多同时动导致掉压：查 XT60 和 DC 接头，电源是否真有 5V 10A', '不用'),
])}
<pre><code># 改了范围以后重刷（每次只插一块板的 USB）
cd /Volumes/Robotics/projects/head
PATH=$PWD/.venv/bin:$PATH firmware/flash.sh eyes
.venv/bin/python -m pytest -q tests</code></pre>

<h2 id="care">注意事项</h2>
<ul>
<li><b>绝对不要接 12V。</b>眼眉板上有 12V 字样，但舵机直接接在电源上，会烧。</li>
<li>Pico 插反、XH 反接都能烧板。上电前再看一次 USB 朝向：USB 朝 H1 第 1 脚那一端，嘴部板插里侧两排。</li>
<li>嘴部板 BOARD POWER 要插跳线帽，否则 Pico 没有电。</li>
<li>插拔舵机都要先断电。USB 插着时 Pico 一直在运行。</li>
<li>JL、JR 是硬连在同一个下巴上的。第一次只给一个通电，确认方向后再一起转，否则两个舵机会对顶，大电流还可能打坏 JawLink。</li>
<li>同一侧嘴角的两个舵机（CUR 和 CLR、CUL 和 CLL）也连在一起。一个到不了 90° 时，试试这一对一起通电。</li>
<li>EXA 不接。眉毛板 4、5 列空着。</li>
<li>舵机线先别扎死，全部通过后再走线，转到两端看线有没有被连杆夹住。</li>
<li>整机跑起来后摸 DC 插头和端子，发烫就停。后盖封死以后再测一次温度。</li>
</ul>
<p><button id="reset" style="font:inherit;padding:7px 11px;border-radius:8px;border:1px solid var(--line);background:var(--card);color:var(--ink);cursor:pointer">清空勾选和 LR 结果</button></p>
</main><script>{JS}</script></body></html>"""
    open(OUT, 'w', encoding='utf8').write(html)
    print(OUT, len(html) // 1024, 'KB')


if __name__ == '__main__':
    page()
