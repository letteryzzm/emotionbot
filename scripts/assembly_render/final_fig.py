"""总装部分的图和表：模块总览、全部打印件对照、舌头牙齿、眼球核心、眉毛上框架、PCB、风扇、外壳、支架。

模型没画这些连接。孔位来自 SkullFrame / Part_4 / RearPlate / FrontVent / FanBracket 的同轴孔测量，
PCB 孔距来自 pcb/render/*.json。图里的 @@key@@ 由 build_steps.py 换成图号。
"""
import glob, html as H, io, base64, os, subprocess
import numpy as np
from PIL import Image
from render import render
from jaw_m2_fig import b64

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
STL = os.path.join(ROOT, 'print_package/STL')
SK = (0.90, 0.89, 0.85); BLUE = (0.60, 0.74, 0.92); GREEN = (0.62, 0.85, 0.62); ORANGE = (0.96, 0.62, 0.25)
PURPLE = (0.70, 0.55, 0.88); PINK = (0.93, 0.70, 0.72); DARK = (0.33, 0.35, 0.40); YELLOW = (0.95, 0.88, 0.55); RED = '#db3838'; M4C = '#9e192d'
EYE = list(range(28, 63))
BROW = [4, 12, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79]


def stl(rel):
    p = glob.glob(os.path.join(STL, rel))[0]
    b = open(p, 'rb').read(); n = int.from_bytes(b[80:84], 'little')
    dt = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])
    return np.frombuffer(b, dtype=dt, offset=84, count=n)['v'].reshape(-1, 3, 3).astype(float)


def box(c, s):
    c, s = np.array(c, float), np.array(s, float) / 2
    v = np.array([[x, y, z] for x in (-1, 1) for y in (-1, 1) for z in (-1, 1)]) * s + c
    q = [(0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)]
    return np.array([[v[a], v[b], v[c2]] for a, b, c2, d in q] + [[v[a], v[c2], v[d]] for a, b, c2, d in q])


def shot(items, view, W=1000, H_=760, joins=(), notes=(), polys=(), fit=None, margin=0.07, title='', up=(0, 0, 1)):
    """items: (tris, 颜色)；joins: (外端, 孔口, 字母, 颜色)；notes: (点, 文字)；polys: (点列表, 文字)"""
    it = [(t, c, i) for i, (t, c) in enumerate(items)]
    fp = np.concatenate([t.reshape(-1, 3) for t, _ in items]) if fit is None else fit
    extra = [np.array([j[0], j[1]], float) for j in joins]
    if extra:
        fp = np.concatenate([fp] + extra)
    im, proj, _ = render(it, view, W=W, H=H_, fit=fp, margin=margin, up=up)
    g = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H_}"/>']
    for pts, txt in polys:
        q = [proj(np.array(p, float)) for p in pts]
        g.append('<polygon points="' + ' '.join(f'{x:.1f},{y:.1f}' for x, y in q) + '" fill="#2e8b57" fill-opacity=".28" stroke="#1d6b42" stroke-width="2"/>')
        cx, cy = np.mean(q, axis=0)
        g.append(f'<text x="{cx:.1f}" y="{cy:.1f}" class="fnote" text-anchor="middle">{H.escape(txt)}</text>')
    for a, b, k, col in joins:
        x0, y0 = proj(np.array(a, float)); x1, y1 = proj(np.array(b, float))
        g.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" class="exl"/><circle cx="{x1:.1f}" cy="{y1:.1f}" r="3.2" class="exd"/>')
        if k:
            lx, ly = min(max(x0, 14), W - 14), min(max(y0, 14), H_ - 14)
            g.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="12" fill="{col}" class="lbc"/><text x="{lx:.1f}" y="{ly + .5:.1f}" class="lbt">{k}</text>')
    for p, txt in notes:
        x, y = proj(np.array(p, float))
        g.append(f'<text x="{x:.1f}" y="{y:.1f}" class="fnote" text-anchor="middle">{H.escape(txt)}</text>')
    return (f'<div class="fig3d"><svg viewBox="0 0 {W} {H_}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{H.escape(title)}">' + ''.join(g) + '</svg></div>')


def table(head, rows):
    return ('<table class="sc"><thead><tr>' + ''.join(f'<th>{h}</th>' for h in head) + '</tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows) + '</tbody></table>')


def mouth_ids(S):
    n = S.names
    return [g for g in S.faces if g >= 80 and not any(k in n[g] for k in ('screw', 'Shoulder', 'washer'))]


# ---------- 总览 ----------
def overview(S):
    d = dict(eye=np.array([0, -105, 10.]), brow=np.array([0, -105, 85.]), mouth=np.array([0, -95, -80.]),
             fan=np.array([0, 78, 6.]), rear=np.array([0, 140, 0.]), vent=np.array([0, 195, 0.]), top=np.array([0, 10, 95.]), plate=np.array([0, 10, 125.]))
    it = [(S.tris(0), SK)]
    it += [(S.tris(g, d['eye']), BLUE) for g in EYE] + [(pivot_a() + d['eye'], BLUE), (lateral_frame() + d['eye'], BLUE)]
    it += [(S.tris(g, d['brow']), ORANGE) for g in BROW]
    it += [(S.tris(g, d['mouth']), PINK) for g in mouth_ids(S)] + [(S.tris(27, d['mouth']), PINK)]
    it += [(S.tris(63, d['fan']), GREEN), (box((0, 75 + d['fan'][1], 72 + d['fan'][2]), (50, 10, 50)), DARK)]
    it += [(S.tris(7, d['rear']), SK), (S.tris(9, d['vent']), SK), (S.tris(26, d['top']), PURPLE), (S.tris(10, d['plate']), PURPLE)]
    c = np.array([0, 10, 20.])
    joins = [(c + d['eye'] * .78, c + (0, -55, 0), '', ''), (c + d['brow'] * .8, c + (0, -55, 35), '', ''), (c + d['mouth'] * .75, c + (0, -55, -70), '', ''),
             (c + d['fan'] * .9 + (0, 0, 52), c + (0, 55, 52), '', ''), (c + (0, 170, 60), c + (0, 110, 60), '', '')]
    notes = [(np.array([0, -60, 60]) + d['brow'], 'C 眉毛模块'), (np.array([0, -60, 20]) + d['eye'], 'B 眼部模块'), (np.array([0, -60, -60]) + d['mouth'], 'D 嘴部模块 + 颧骨'),
             ((0, 10, 58), 'E 头骨框架'), (np.array([0, 60, 100]) + d['fan'], 'F 风扇支架 + 风扇'), (np.array([0, 60, 135]) + d['rear'], 'F 后盖'), (np.array([0, 100, 105]) + d['vent'], 'F 后格栅'),
             (np.array([0, -10, 145]) + d['top'], 'F 前上盖 + 额头条')]
    return shot(it, (-0.92, 0.32, -0.25), 1100, 760, joins=joins, notes=notes, margin=.04, title='整机模块总览')


CONN = [
    ('眼部底板 SnapEyemech_v20', '头骨框架', 'M3×8 ×6', '从框架外侧往里，拧进底板 M3 热熔螺母', 'skull_eye'),
    ('眉毛底板 Part_4', '头骨框架', 'M4×12 ×8', '从框架外侧往里，拧进 Part_4 的 M4 热熔螺母（模型没画）', 'brow_skull'),
    ('颧骨 CheekBone', '上颌座 TopBase', 'M4×6 ×2', '颧骨正面往里', 'cheek'),
    ('上颌座 TopBase', '头骨框架', 'M4×16 ×6', '框架下部竖板外侧往里', 'skull_mouth'),
    ('颧骨 CheekBone', '头骨框架', 'M3×8 ×4', '框架外侧往里', 'skull_cheek'),
    ('嘴部板 ×1、眼眉板 ×2', '头骨框架内部斜板', 'M3×10 + 5 mm 垫柱 ×8', '孔距 65×48 和 29.6 与板子吻合（模型没画）', 'pcb'),
    ('风扇支架 FanBracket', '头骨框架', 'M3×8 ×6', '模型没画螺丝', 'fan'),
    ('50×50×10 风扇', 'FanBracket', 'M3×14 ×4', '孔距 40，从后面拧进支架 M3 热熔螺母', 'fan'),
    ('后盖 RearPlate', '头骨框架', 'M3×6 ×11', '沉孔 Ø6，拧进框架 M3 热熔螺母', 'shell'),
    ('前上盖 FrontVent', '头骨框架', 'M3×6 ×4', '沉孔 Ø6，拧进框架 M3 热熔螺母', 'shell'),
    ('额头条 FrontPlate', '前上盖', '点胶', '没有螺丝孔，贴在开口上', 'shell'),
    ('头', '颈部支架 NeckStand', '扎带 ×2', '自己画的支架，穿立柱扎带孔', 'neck'),
]


def conn_table():
    return table(['这个零件', '接到', '紧固件', '怎么装', '图'],
                 [(a, b, f'<b>{c}</b>', d, f'<a class="fl" href="#{k}">图 @@{k}@@</a>') for a, b, c, d, k in CONN])


PLATES = [
    ('plate 1 外壳', [('RearPlate', 1, '后盖，改打封口版', 'shell'), ('FrontVent', 1, '前上盖', 'shell'), ('RearVent', 1, '后格栅，<b>用封口后盖时不用</b>', 'shell')]),
    ('plate 2 嘴部', [('TopBase', 1, '上颌座，嘴部骨架', 'ins_top'), ('JawBase', 1, '下颌座', 'ins_jaw'), ('JawLink、Part_33', 2, '左右下颌连杆', 'jawlink'),
                     ('UpperLeftLip、Part_34', 2, '上唇左右', 's3'), ('LowerLeftLip、Part_37', 2, '下唇左右', 's3'), ('Part_29、Part_40', 2, '嘴角下连杆', 's3'), ('Part_30、Part_41', 2, '嘴角件', 's3'),
                     ('ULLLinkA、Part_35', 2, '舵机连杆（第 1 行）', 'm25'), ('Part_31、Part_42', 2, '舵机连杆（第 2 行）', 'm25'), ('Part_32、Part_43', 2, '舵机连杆（第 3 行）', 'm25'), ('Part_27、Part_38', 2, '舵机连杆（第 4 行）', 'm25'),
                     ('ULLLinkB、Part_36', 2, '上唇转动连杆', 's4'), ('Part_28、Part_39', 2, '下唇转动连杆', 's4'), ('Part_19、Part_20、Part_21', 3, '舌头连杆组', 'tongue')]),
    ('plate 3 框架', [('SkullFrame', 1, '头骨框架，所有模块都装在它上面', 'skull_eye')]),
    ('plate 4 眉毛', [('Part_4', 1, '眉毛底板', 'brows'), ('Part_2 / _v2 / _v3 / _v4', 4, '从动连杆，4 个形状相同', 'brows'), ('Part_3 / _v2 / _v3 / _v4', 4, '舵机连杆，4 个形状相同', 'brows'), ('Part_9、Part_13', 2, '外侧臂，镜像', 'brows'), ('Part_8、Part_12', 2, '内侧臂，镜像', 'brows')]),
    ('plate 5 TPU', [('Part_11、Part_14', 2, '软眉毛', 'brows')]),
    ('plate 6 框架附件', [('CheekBone', 1, '颧骨', 'cheek'), ('FanBracket', 1, '风扇支架', 'fan')]),
    ('plate 7 眼部', [('SnapEyemech_v20', 1, '眼部底板', 'eye_base'), ('EyeCorePivotHolder_v2', 1, '<b>X 轴件 A</b>，托住 LR 舵机和眼球转轴，模型没画', 'eye_core'), ('LateralFrame', 1, '<b>X 轴件 B</b>，3 个环，带动两只眼，模型没画', 'eye_core'), ('EyeCorePivotHolder', 1, 'Y 轴支架', 'eye_core'),
                     ('VerticalLever、VerticalHorn', 2, 'UD 舵机到 Y 轴的连杆和舵盘', 'eye_ud'), ('CentralServoHorn', 1, 'LR 舵机舵盘', 'eye_lr'), ('Base_v2', 2, '中间枢轴座', 'eye_base'), ('Base', 2, '外侧眼皮枢轴座', 'eye_lid'),
                     ('EyeAdaptor', 2, '眼球接头，每只眼 1 个', 'eye_lid'), ('EyeAdaptor_v2', 2, '眼球接头，每只眼 1 个', 'eye_lid'), ('LidBR', 2, '上眼皮', 'eye_lid'), ('LidTR、LidTR_v2', 2, '下眼皮', 'eye_lid'),
                     ('SnapEyemech_v20_v2', 2, '眼皮舵机压扣', 'eye_servo'), ('SnapEyemech_v20_v3', 1, 'UD 舵机压扣', 'eye_servo'), ('4xTopLidHorn', 4, '眼皮舵盘', 'eye_horn'), ('2xTopLidLever', 2, '上眼皮短连杆', 'eye_horn'), ('2xBottomLidLever', 2, '下眼皮长连杆', 'eye_horn')]),
    ('plate 8 牙齿舌头', [('MouthAssembly - Part_1_1', 1, '上牙龈', 'tongue'), ('MouthAssembly - Part_1', 1, '上牙', 'tongue'), ('MouthAssembly - Part_1_2', 1, '下牙龈', 'tongue'), ('MouthAssembly - Part_1_3', 1, '下牙', 'tongue'), ('Tongue', 1, '舌头', 'tongue')]),
]


def parts_table():
    rows = []
    for plate, L in PLATES:
        rows.append((f'<b>{plate}</b>', '', '', ''))
        rows += [(n, c, u, f'<a class="fl" href="#{k}">图 @@{k}@@</a>') for n, c, u, k in L]
    tot = sum(c for _, L in PLATES for _, c, _, _ in L)
    assert tot == 83, tot
    return '<details><summary><b>全部 83 个打印件：每个用在哪一张图</b>（点开）</summary>' + table(['零件', '数量', '是什么', '图'], rows) + '</details>'


def overview_section(S):
    return ('<section id="overview" class="stp"><h2>整机怎么连起来</h2>'
            '<p>头骨框架 SkullFrame 是中心，其他模块都装在它上面。眼部、眉毛、嘴部先在桌上各自装好，再从<b>前面</b>送进框架，螺丝都从框架外侧往里拧。风扇和后盖从<b>后面</b>装。</p>'
            + overview(S) + conn_table() + parts_table() +
            '<p class="muted">送入方向是用模型模拟出来的：沿不同方向把模块移出框架，看会不会碰到框架和其他模块。眼部略向后下、嘴部从前下方送进去时都没有碰撞。模型没画的螺丝，规格按孔径和孔深算，表里的长度第一次装时先试一颗。</p></section>')


# ---------- 眼球核心 ----------
def pdf_pages():
    out = os.path.join(ROOT, 'outputs/assembly/eye_pdf')
    if not glob.glob(out + '/p-*.png'):
        os.makedirs(out, exist_ok=True)
        pdf = glob.glob(os.path.join(ROOT, 'upstream/EyeMech_3.2_download/*/EYEMECH*.pdf'))[0]
        subprocess.run(['pdftoppm', '-r', '110', '-f', '3', '-l', '6', '-png', '-gray', pdf, out + '/p'], check=True)
    return sorted(glob.glob(out + '/p-*.png'))


def page(i, y0, y1):
    im = Image.open(pdf_pages()[i]).convert('L'); W, Hh = im.size
    im = im.crop((int(W * .08), int(Hh * y0), int(W * .92), int(Hh * y1))).point(lambda v: 255 if v > 225 else v).quantize(8)
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


def cards(S, rows):
    h = []
    for name, T, note in rows:
        im, _, _ = render([(T, BLUE, 0)], (0.5, 0.6, -0.6), W=300, H=240, ss=2, margin=.08)
        h.append(f'<div style="flex:1 1 200px;max-width:260px;border:1px solid var(--line);border-radius:8px;overflow:hidden;background:#fafaf7"><img style="width:100%;display:block" src="data:image/png;base64,{b64(im)}" alt="{name}"><div style="padding:6px 8px;font-size:13.5px;color:#1d1d1f"><b>{name}</b><br>{note}</div></div>')
    return '<div style="display:flex;flex-wrap:wrap;gap:10px;margin:10px 0">' + ''.join(h) + '</div>'


def eye_core(S):
    e = 'plate7_Eyes/'
    c = cards(S, [('EyeCorePivotHolder_v2', stl(e + 'EyeCorePivotHolder_v2*'), 'X 轴件 A，长 87。中间方框装 LR 舵机'),
                  ('LateralFrame', stl(e + 'LateralFrame*'), 'X 轴件 B，长 85。3 个圆环，松放在上面'),
                  ('EyeCorePivotHolder', stl(e + 'EyeCorePivotHolder__*'), 'Y 轴支架，扣在舵机上'),
                  ('VerticalLever', S.tris(56), 'Y 轴的拱形连杆'),
                  ('Base_v2 ×2', stl(e + 'Base_v2*'), '中间枢轴座，下一步卡进底板'),
                  ('Base ×2', stl(e + 'Base__*'), '外侧枢轴座，装眼皮时才用')])
    imgs = [(page(0, .22, .88), '官方图：LR 舵机放进 X 轴件 A，再扣上 Y 轴组件'), (page(1, .02, .72), '官方图：装两个中间枢轴座，再松装 X 轴件 B')]
    g = ''.join(f'<figure style="flex:1 1 300px;margin:0"><img style="width:100%;background:#fff;border:1px solid var(--line);border-radius:8px" src="{s}" alt="{t}"><figcaption class="muted">{t}</figcaption></figure>' for s, t in imgs)
    ra = right_adaptors(S)
    it = [(S.tris(k), SK) for k in (39, 33, 49)] + [(S.tris(35), DARK), (S.tris(54), ORANGE), (S.tris(46), (.98, .98, .98)), (S.tris(53), (.98, .98, .98)), (S.tris(62), BLUE), (S.tris(41), BLUE), (ra[0], BLUE), (ra[1], BLUE), (pivot_a(), GREEN), (lateral_frame(), PURPLE)]
    pos = shot(it, (0.15, 0.5, -0.85), 1000, 640, notes=[((0, -38, 14), 'LateralFrame（X 轴件 B）'), ((-27, -70, -12), 'EyeCorePivotHolder_v2（X 轴件 A）'), ((0, -71, 16), '舵盘'), ((-37.5, -50, 12), 'EyeAdaptor 卡柱'), ((37.5, -50, 12), 'EyeAdaptor 卡柱')],
               fit=np.concatenate([S.pts(46), S.pts(53), S.pts(39), lateral_frame().reshape(-1, 3)]), title='两根横梁的位置')
    return (pos + c + f'<div style="display:flex;flex-wrap:wrap;gap:10px">{g}</div>'
            '<ol><li>LR 舵机放进 EyeCorePivotHolder_v2 的方框，线从缺口出去。</li><li>Y 轴支架扣到舵机上面，把舵机夹住。</li><li>两个 Base_v2 卡到组件上，有一点阻力，装好后要能自由转。</li>'
            '<li>LateralFrame 松松地放到舵机上。<b>图 @@eye_lr@@ 要拆下来校准，先别压死。</b></li></ol>'
            '<p class="muted">图片来自 Will Cogley / NM Robotics 的 EyeMech ε3.2 Assembly Document（CC BY-NC-SA 4.0）。官方图是一体打印版（PIP），我们用的是卡扣版，零件要先按上面的卡片组成子组件。零件名和官方图的对应是按形状判断的。</p>')


# ---------- 舌头、牙齿 ----------
def tongue(S):
    it = [(S.tris(113), SK), (S.tris(92), ORANGE), (S.tris(82), GREEN), (S.tris(164), PURPLE), (S.tris(155), DARK), (S.tris(134), YELLOW), (S.tris(170), PINK)]
    joins = [((-14, -60.8, -92.4), (4.3, -60.8, -92.4), 'A', M4C), ((24, -50.7, -78.7), (8, -50.7, -78.7), 'B', RED), ((-32, -2.7, -79.5), (-13, -2.7, -79.5), 'B', RED), ((-34, -12.8, -93.2), (-15.8, -12.8, -93.2), 'C', '#9e62d9')]
    notes = [((6, -56, -70), 'Part_19'), ((-2, -28, -66), 'Part_21'), ((-13, -8, -70), 'Part_20'), ((5, -14, -106), 'TON 舵机'), ((0, -84, -68), '下牙 + 下牙龈')]
    fig = shot(it, (0.62, 0.6, -0.5), 1000, 720, joins=joins, notes=notes, title='舌头连杆和下牙')
    up = [(S.tris(188), SK), (S.tris(154), YELLOW), (S.tris(150), PINK)]
    fig2 = shot(up, (0.45, 0.65, 0.6), 1000, 560, notes=[((0, -75, -48), '上牙龈 Part_1_1'), ((0, -86, -80), '上牙 Part_1')], title='上牙')
    c = cards(S, [('Tongue', stl('plate8*/Tongue*'), '舌头，长 42，底面没有孔'), ('Part_21', S.tris(164), '上面两个方槽朝上，舌头粘在这里')])
    rows = [('A', 'M4 台阶螺丝', 1, 'Part_19 的 Ø5.3 孔（能转）', '下颌座 · M4 热熔螺母'), ('B', 'M3 台阶螺丝', 2, 'Part_20、Part_19 的 Ø4.3 孔（能转）', 'Part_21 两端 · 背面 M3 螺母（试装确认）'), ('C', 'M2.5×8', 1, 'Part_20 的台阶孔', 'TON 舵机输出轴')]
    return fig + table(['标', '螺丝', '数量', '穿过', '拧进'], rows) + fig2 + c


# ---------- 眉毛 → 框架 ----------
def brow_skull(S):
    side = [(47.1, -6.6, 38.4), (47.1, -6.4, 49.5), (47.1, -6.6, 60.6)]
    joins = []
    for p in side:
        q = np.array(p) + (3, 0, 0); joins.append((q + (30, 0, 0), q, 'A', M4C))
    a = np.array([.94, -.34, 0]); q = np.array((38.7, -58.6, 63.6)) + a * 3; joins.append((q + a * 30, q, 'A', M4C))
    it = [(S.tris(0), SK), (S.tris(77), BLUE)]
    return shot(it, (-0.78, 0.52, -0.34), 1000, 760, joins=joins, notes=[((10, -40, 75), 'Part_4')], title='眉毛底板上框架')


# ---------- PCB ----------
def pcb(S):
    a = np.array([0, .53, .85]); a /= np.linalg.norm(a); e = np.cross(a, [1, 0, 0])
    T = S.tris(0); h = T.mean(1) @ a
    T = T[h < 62]
    P = lambda u, v: np.array([u, 0, 0]) + e * v + a * 44

    def rect(u0, u1, v0, v1):
        return [P(u0, v0), P(u1, v0), P(u1, v1), P(u0, v1)]
    polys = [(rect(-36, 36, -11.5, 43.4), '嘴部板 72×55'), (rect(-63.3, -36.7, -24, 38.5), '眼眉板'), (rect(36.7, 63.3, -24, 38.5), '眼眉板')]
    holes = [(-32.5, -8.1), (-32.5, 40), (32.5, -8.1), (32.5, 40), (-47.2, -7.4), (-47.2, 22.2), (52.8, -7.4), (52.8, 22.2)]
    joins = []
    for u, v in holes:
        p = P(u, v); joins.append((p + a * .01, p, '', ''))
    return shot([(T, SK)], -a, 1000, 680, polys=polys, joins=joins, fit=np.array(rect(-70, 70, -32, 50)), margin=.03, title='PCB 位置', up=e * -1)


# ---------- 风扇 ----------
def fan(S):
    F = np.array([0, 118, 0.]) * .5
    it = [(S.tris(0), SK), (S.tris(63), GREEN), (box((0, 112, 72), (50, 10, 50)), DARK)]
    jb = []
    for u, v, w in [(66.9, 42.4, 73.0), (60.1, 48.5, 83.6), (52.5, 53.2, 91.7)]:
        for s in (1, -1):
            p = np.array([s * u, v, w]) + (0, .87 * 1.8, -.5 * 1.8); d = np.array([0, .87, -.5])
            jb.append((p + d * 16, p, 'A', RED))
    for x in (-20, 20):
        for z in (52, 92):
            jb.append(((x, 118, z), (x, 69.8, z), 'B', '#d9782e'))
    return shot(it, (-0.55, -0.72, -0.36), 1000, 760, joins=jb, notes=[((0, 118, 72), '风扇，从后面装'), ((-40, 45, 70), 'FanBracket')], title='风扇')


# ---------- 外壳 ----------
def rear_closed():
    """封口版后盖（scripts/print_mods/），转回装配坐标"""
    d = os.path.join(ROOT, 'outputs/print_mods'); tf = np.load(d + '/rear_tf.npz')
    b = open(d + '/RearPlate_无出风口.stl', 'rb').read(); n = int.from_bytes(b[80:84], 'little')
    dt = np.dtype([('n', '<3f4'), ('v', '<9f4'), ('a', '<u2')])
    T = np.frombuffer(b, dtype=dt, offset=84, count=n)['v'].reshape(-1, 3, 3).astype(float)
    return (T - tf['t']) @ tf['R']


def shell(S):
    R = np.array([0, 62, 0.]); U = np.array([0, 0, 58.])
    rear = [((79.3, 48.9, 27.8), (1, 0, 0)), ((-79.3, 48.9, 27.8), (-1, 0, 0)), ((79.2, 20.6, -14.9), (1, 0, 0)), ((-79.2, 20.6, -14.9), (-1, 0, 0)), ((79.2, 27.4, 39.5), (1, 0, 0)), ((-79.2, 27.4, 39.5), (-1, 0, 0)),
            ((52, 53, 103.4), (.65, .35, .67)), ((-52, 53, 103.4), (-.65, .35, .67)), ((29.6, 96.4, -21.4), (.43, .81, -.39)), ((-29.6, 96.4, -21.4), (-.43, .81, -.39)), ((0, 61.8, 120.1), (0, .47, .88))]
    front = [((66.4, 31.1, 95.3), (.89, .19, .42)), ((-66.4, 31.1, 95.3), (-.89, .19, .42)), ((27, 51, 120.5), (.34, .47, .81)), ((-27, 51, 120.5), (-.34, .47, .81))]
    j = [(np.array(p) + R + np.array(d) * 20, np.array(p) + R, 'A', RED) for p, d in rear]
    j += [(np.array(p) + U + np.array(d) * 20, np.array(p) + U, 'B', '#d9782e') for p, d in front]
    it = [(S.tris(0), SK), (rear_closed() + R, BLUE), (S.tris(26, U), PURPLE), (S.tris(10, U * 1.6), YELLOW)]
    return shot(it, (-0.72, -0.55, -0.42), 1000, 780, joins=j, notes=[(np.array((0, 100, 60)) + R, 'RearPlate（封口版）'), (np.array((0, 0, 135)) + U, 'FrontVent'), (np.array((0, -60, 112)) + U * 1.6, 'FrontPlate')], margin=.04, title='外壳')


INS_ALL = [('头骨框架', 'M3', 'Ø4.4', 21, '后盖 11、前上盖 4、风扇支架 6'), ('头骨框架', 'M3', 'Ø4.4', 8, 'PCB（也可以不压，用尼龙柱或扎带）'), ('头骨框架', 'M3', 'Ø4.4', 6, '框架外侧 3+3，模型里有 M3×10 但没有对应零件，<b>可以不压</b>'),
           ('头骨框架', 'M3', 'Ø4.4', 4, '最上面一排斜孔，没找到对应零件，不用压'), ('风扇支架', 'M3', 'Ø4.35', 4, '风扇'), ('眉毛底板 Part_4', 'M4', 'Ø5.35', 12, '8 个接框架，4 个是 Part_2 转轴'), ('眉毛底板 Part_4', 'M2', 'Ø3.2', 8, '4 个眉毛舵机')]


NOW = '''<section id="now" style="border-left:5px solid var(--elec)">
<h2>这份流程怎么读</h2>
<p>2026-11-05 重新梳理：之前到眼部就没有下文了，是因为图是按补充时间排的。现在按真实顺序分成 6 个阶段，<b>眼部、眉毛、嘴部先在桌上各自组好，再一起装进头骨框架</b>。</p>
<table><thead><tr><th>阶段</th><th>做什么</th><th>图</th></tr></thead><tbody>
<tr><td><a href="#stage-A">A 准备</a></td><td>压热熔螺母</td><td>@@ins_top@@ 到 @@ins_other@@</td></tr>
<tr><td><a href="#stage-B">B 眼部</a></td><td>眼球核心 → 底板 → 眼球眼皮 → 5 个舵机 → 左右控制 → 上下控制 → 眼皮连杆</td><td>@@eye_core@@ 到 @@eye_done@@</td></tr>
<tr><td><a href="#stage-C">C 眉毛</a></td><td>底板、舵机、连杆、臂、TPU</td><td>@@brows@@</td></tr>
<tr><td><a href="#stage-D">D 嘴部</a></td><td>舵机、下颌、嘴唇连杆、舌头牙齿、颧骨</td><td>@@servo_top@@ 到 @@cheek@@</td></tr>
<tr><td><a href="#stage-E">E 总装</a></td><td>眼部 → 眉毛 → 嘴部和颧骨，依次装进框架</td><td>@@skull_eye@@ 到 @@skull_cheek@@</td></tr>
<tr><td><a href="#stage-F">F 电子和外壳</a></td><td>板子、风扇、标定走线、合壳、上支架</td><td>@@pcb@@ 到 @@neck@@</td></tr>
</tbody></table>
<p style="background:#fff4d6;padding:8px 10px;border-radius:6px"><b>你的眼部已经装了，先核对一件事：</b>两根横梁 <b>EyeCorePivotHolder_v2</b>（长 87）和 <b>LateralFrame</b>（长 85）有没有装上？模型没画它们，旧文档也漏了。没有它们，LR 舵机带不动两只眼球。见<a href="#eye_core">图 @@eye_core@@</a>。</p>
<p class="muted">上颚那部分（图 @@upper_l@@、@@upper_r@@）要等 M3 螺母到了再装。眉毛上框架要 8 颗 M4×12，见<code>螺丝与热熔螺母清单.md</code>。</p>
'''


def ins_all():
    return '<h4>图上没标的其他孔</h4>' + table(['零件', '规格', '孔径', '数量', '给谁用'], INS_ALL)


def neck(S):
    p = os.path.join(ROOT, 'print_package/给朋友打印_2026-11-01/预览_支架装在头上.png')
    im = Image.open(p).convert('RGB'); im.thumbnail((900, 700)); b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    return f'<div class="fig3d"><img style="width:100%;display:block" alt="颈部支架" src="data:image/png;base64,{base64.b64encode(b.getvalue()).decode()}"></div>'


# ---------- 模型没画的两根横梁：按孔位放回装配位置 ----------
def lateral_frame():
    """三个 Ø6.3 环的中心距 37.5，正好对上 EyeAdaptor 尾部 (±37.5,-53.7) 和舵盘后端 (0,-53.8) 的卡柱"""
    return stl('plate7_Eyes/LateralFrame*') + np.array([-42.5, -58.75, 5.7])


def pivot_a():
    """X 轴件 A：两端销钉中心距 75，插进下面的 EyeAdaptor_v2 (±37.5,-68.7)；绕 z 转 180°，方框落在 LR 舵机外面"""
    T = stl('plate7_Eyes/EyeCorePivotHolder_v2*') * np.array([-1, -1, 1]) + np.array([43.5, 22.97 - 68.7, -13.9])
    return T[:, ::-1]


def right_adaptors(S):
    m = np.array([-1, 1, 1])
    return [(S.tris(62) * m)[:, ::-1], (S.tris(41) * m)[:, ::-1]]
