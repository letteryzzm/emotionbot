"""生成 docs/电源线焊接流程.html：方案 A 电源线的逐步配图流程。
PCB 图来自 pcb/render/*.json，照片内嵌进 HTML，单文件可以直接打开。
用法：.venv/bin/python scripts/power_guide/build.py"""
import base64, json, os

ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
OUT = os.path.join(ROOT, 'docs/电源线焊接流程.html')
RED, BLK, CU, TUBE, INK, MUT, OK, BAD = '#d32f2f', '#222', '#c98a3c', '#6d7f8c', '#1d1d1f', '#5f6368', '#1b7f3b', '#c62828'


def tx(x, y, s, size=20, color=INK, w=700, a='start'):
    return f'<text x="{x}" y="{y}" font-size="{size}" font-weight="{w}" fill="{color}" text-anchor="{a}">{s}</text>'


def svg(w, h, body, label):
    return f'<svg viewBox="0 0 {w} {h}" role="img" aria-label="{label}">{body}</svg>'


def photo(name, w, h, marks, label):
    d = base64.b64encode(open(os.path.join(ROOT, 'docs/figs_power', name), 'rb').read()).decode()
    return svg(w, h, f'<image href="data:image/jpeg;base64,{d}" width="{w}" height="{h}"/>' + marks, label)


def tag(x, y, s, color=BAD, a='start', size=22):
    wd = len(s.encode('gbk')) * size * 0.52 + 18
    x0 = x if a == 'start' else x - wd
    return (f'<rect x="{x0:.0f}" y="{y - size - 6}" width="{wd:.0f}" height="{size + 16}" rx="6" fill="{color}"/>'
            + tx(x0 + wd / 2, y, s, size, '#fff', 800, 'middle'))


def ring(x, y, r, color=BAD):
    return f'<circle cx="{x}" cy="{y}" r="{r}" fill="none" stroke="{color}" stroke-width="5"/>'


# ---------- 总览 ----------
def overview():
    b = '<rect x="10" y="150" width="170" height="110" rx="10" fill="#333"/>' + tx(95, 195, '5V 10A', 22, '#fff', 800, 'middle') + tx(95, 225, '电源适配器', 18, '#fff', 600, 'middle')
    b += f'<path d="M180 205 H250" stroke="#333" stroke-width="7"/>' + tx(215, 190, 'DC 圆头', 15, MUT, 600, 'middle')
    b += '<rect x="250" y="165" width="120" height="80" rx="8" fill="#2f2f2f"/><rect x="330" y="165" width="56" height="80" fill="#35b27a"/>'
    b += tx(290, 212, '转接头', 17, '#fff', 700, 'middle') + tx(358, 192, '+', 26, '#fff', 800, 'middle') + tx(358, 236, '−', 26, '#fff', 800, 'middle')
    b += f'<path d="M386 185 H480" stroke="{RED}" stroke-width="8"/><path d="M386 225 H480" stroke="{BLK}" stroke-width="8"/>'
    b += f'<circle cx="480" cy="185" r="13" fill="#b9bcc0" stroke="{RED}" stroke-width="3"/><circle cx="480" cy="225" r="13" fill="#b9bcc0" stroke="{BLK}" stroke-width="3"/>'
    b += tx(400, 110, '只有这 2 处要焊', 20, BAD, 800, 'middle') + f'<path d="M420 120 L472 170" stroke="{BAD}" stroke-width="3"/>'
    rows = [(60, 'XH 线', '眼部板'), (205, 'XT60 线（粗）', '嘴部板'), (350, 'XH 线', '眉部板')]
    for y, n, bd in rows:
        wd = 8 if 'XT60' in n else 4
        b += f'<path d="M480 185 C540 185 540 {y - 9} 610 {y - 9} H740" stroke="{RED}" stroke-width="{wd}" fill="none"/>'
        b += f'<path d="M480 225 C540 225 540 {y + 9} 610 {y + 9} H740" stroke="{BLK}" stroke-width="{wd}" fill="none"/>'
        b += tx(615, y - 22, n, 17, INK, 700)
        b += f'<rect x="740" y="{y - 40}" width="190" height="80" rx="8" fill="#2e7d32"/>' + tx(835, y + 8, bd, 22, '#fff', 800, 'middle')
    return svg(940, 410, b, '方案 A 总接线')


# ---------- 线的步骤图：10 px = 1 mm ----------
def thick(x1, x2, color=RED, y=90):
    return f'<rect x="{x1}" y="{y - 14}" width="{x2 - x1}" height="28" rx="4" fill="{color}"/>'


def copper(x1, x2, y=90, h=18):
    return f'<rect x="{x1}" y="{y - h / 2}" width="{x2 - x1}" height="{h}" fill="{CU}"/>' + ''.join(
        f'<path d="M{x1} {y - h / 2 + i} H{x2}" stroke="#8a5b20" stroke-width="1"/>' for i in range(3, int(h), 4))


def thin(x1, x2, y, color=RED):
    return f'<rect x="{x1}" y="{y - 6}" width="{x2 - x1}" height="12" rx="3" fill="{color}"/>'


def dim(x1, x2, y, s):
    return (f'<path d="M{x1} {y - 8} V{y + 8} M{x2} {y - 8} V{y + 8} M{x1} {y} H{x2}" stroke="{BAD}" stroke-width="3"/>'
            + tx((x1 + x2) / 2, y - 14, s, 20, BAD, 800, 'middle'))


TIP0, TIP1, END = 520, 590, 670  # 焊接段 440-520；前端 520-590


def strip():
    b = thick(30, 440) + copper(440, 590) + dim(440, 590, 40, '剥 15 mm') + tx(40, 60, 'XT60 红线（粗）', 19)
    for y in (180, 230):
        b += thin(30, 440, y) + copper(440, 590, y, 7)
    b += dim(440, 590, 275, '也剥 15 mm') + tx(40, 164, '两根 XH 红线（细）', 19)
    return svg(720, 300, b, '剥线长度')


def tube():
    b = thick(30, 440, y=110) + copper(440, 590, 110) + thin(30, 440, 74) + copper(440, 590, 74, 7) + thin(30, 440, 146) + copper(440, 590, 146, 7)
    b += f'<rect x="130" y="50" width="150" height="120" rx="10" fill="{TUBE}" fill-opacity=".78"/>'
    b += tx(205, 118, '热缩管', 22, '#fff', 800, 'middle') + tx(205, 200, '3 根线一起穿过去，先推到远处', 20, BAD, 800, 'middle')
    return svg(720, 225, b, '先套热缩管')


def wrap(solder=False):
    b = thick(30, 440) + copper(440, 590) + thin(30, 430, 58) + thin(30, 430, 122)
    for i in range(6):
        x = 448 + i * 13
        b += f'<path d="M{x} 70 C{x + 15} 80 {x - 3} 102 {x + 12} 112" stroke="{CU}" stroke-width="7" fill="none"/>'
        b += f'<path d="M{x} 70 C{x + 15} 80 {x - 3} 102 {x + 12} 112" stroke="#8a5b20" stroke-width="1" fill="none"/>'
    if solder:
        b += '<path d="M440 74 C460 62 505 62 522 76 C530 86 530 96 522 104 C505 118 460 118 440 106 Z" fill="#c9ccd1" stroke="#7b7f85" stroke-width="2"/>'
        b += dim(440, 520, 28, '只焊这 8 mm') + dim(520, 590, 170, '这 7 mm 不上锡')
    else:
        b += dim(440, 520, 28, '细线绕在根部') + dim(520, 590, 170, '前端留空')
    return svg(720, 205, b, '焊接位置' if solder else '绕线位置')


def shrunk():
    b = thick(30, 400) + thin(30, 380, 58) + thin(30, 380, 122) + copper(520, 590)
    b += f'<path d="M380 44 H530 V136 H380 Z" fill="{TUBE}"/>' + tx(455, 98, '热缩管', 22, '#fff', 800, 'middle')
    b += dim(520, 590, 170, '只露这段') + tx(30, 180, '接着把黑线也做一遍，红黑不能碰在一起', 20, BAD, 800)
    return svg(720, 205, b, '收缩后')


# ---------- PCB ----------
def pad(c, n):
    for p in c['pads']:
        if str(p.get('num') or p.get('n') or p.get('number')) == str(n):
            return p['x'], -p['y'], p.get('net')
    raise KeyError((c['ref'], n))


def pcb(name, marks, label, left=1000, right=1000, crop=None):
    d = json.load(open(os.path.join(ROOT, 'pcb/render', name + '.json')))
    C = {c['ref']: c for c in d['comps']}
    xs = [p[0] for o in d['outline'] for p in o['pts']]; ys = [-p[1] for o in d['outline'] for p in o['pts']]
    x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
    path = ' '.join('M' + 'L'.join(f'{x:.0f},{-y:.0f}' for x, y in o['pts']) + 'Z' for o in d['outline'])
    b = f'<path d="{path}" fill="#1f6b43" fill-rule="evenodd" stroke="#0e3d25" stroke-width="10"/>'
    for c in d['comps']:
        for p in c['pads']:
            b += f'<circle cx="{p["x"]:.0f}" cy="{-p["y"]:.0f}" r="24" fill="#d8c27a"/>'
    fs = (y1 - y0) / 34
    for ref, n, s, col, tx0, ty0 in marks:
        x, y, _ = pad(C[ref], n)
        b += f'<path d="M{x:.0f} {y:.0f} L{tx0} {ty0}" stroke="{col}" stroke-width="{fs * .16:.0f}"/>'
        b += f'<circle cx="{x:.0f}" cy="{y:.0f}" r="{fs * .75:.0f}" fill="none" stroke="{col}" stroke-width="{fs * .28:.0f}"/>'
        a = 'end' if tx0 < x else 'start'
        b += f'<text x="{tx0 + (-fs * .4 if a == "end" else fs * .4):.0f}" y="{ty0 + fs * .35:.0f}" font-size="{fs * 1.25:.0f}" font-weight="800" fill="{col}" text-anchor="{a}">{s}</text>'
    b += f'<text x="{(x0 + x1) / 2:.0f}" y="{y0 - fs * .5:.0f}" font-size="{fs * 1.1:.0f}" font-weight="800" fill="{MUT}" text-anchor="middle">↑ USB 端（俯视，正面朝上）</text>'
    y0 -= fs * 2
    if crop:
        crop = (x0 - left, y0, x1 - x0 + left + right, (y1 - y0) * crop[0]) if crop[1] == 'top' else (x0 - left, y1 - (y1 - y0) * crop[0], x1 - x0 + left + right, (y1 - y0) * crop[0] + 60)
    vb = crop or (x0 - left, y0 - 100, x1 - x0 + left + right, y1 - y0 + 200)
    return f'<svg viewBox="{vb[0]:.0f} {vb[1]:.0f} {vb[2]:.0f} {vb[3]:.0f}" role="img" aria-label="{label}">{b}</svg>'


# ---------- 测量图 ----------
def meter(mode, read):
    return ('<rect x="20" y="30" width="170" height="210" rx="14" fill="#f2b705" stroke="#8a6b00" stroke-width="3"/>'
            '<rect x="38" y="50" width="134" height="62" fill="#c9dcc3" stroke="#333"/>' + tx(105, 92, read, 24, INK, 800, 'middle')
            + tx(105, 150, mode, 20, INK, 800, 'middle'))


def short_test():
    b = meter('蜂鸣档', '不响')
    b += '<rect x="500" y="85" width="170" height="100" rx="8" fill="#2f2f2f"/><rect x="620" y="85" width="70" height="100" fill="#35b27a"/>'
    b += tx(655, 123, '+', 28, '#fff', 800, 'middle') + tx(655, 174, '−', 28, '#fff', 800, 'middle') + tx(565, 142, '转接头', 20, '#fff', 700, 'middle')
    b += f'<path d="M190 100 C320 40 520 40 640 112" stroke="{RED}" stroke-width="6" fill="none"/><path d="M190 180 C320 240 520 240 640 162" stroke="{BLK}" stroke-width="6" fill="none"/>'
    return svg(720, 270, b, '量短路')


def plug_test():
    b = meter('直流电压', '5.0–5.2 V')
    b += '<rect x="430" y="28" width="120" height="74" rx="6" fill="#efe7d8" stroke="#888" stroke-width="2"/><circle cx="465" cy="65" r="11" fill="#333"/><circle cx="515" cy="65" r="11" fill="#333"/>' + tx(600, 58, 'XH 插头', 21) + tx(600, 86, '两个孔，孔里量', 18, MUT, 600)
    b += '<path d="M430 170 H535 L560 195 V235 L535 260 H430 Z" fill="#f2b705" stroke="#8a6b00" stroke-width="2"/><circle cx="470" cy="215" r="13" fill="#caa23b" stroke="#6b5200" stroke-width="2"/><circle cx="520" cy="215" r="13" fill="#caa23b" stroke="#6b5200" stroke-width="2"/>' + tx(600, 206, 'XT60 公头', 21) + tx(600, 234, '两根金针，别让它们相碰', 18, BAD, 700)
    b += f'<path d="M190 96 C290 70 370 62 454 64" stroke="{RED}" stroke-width="5" fill="none"/><path d="M190 180 C300 190 380 210 458 214" stroke="{BLK}" stroke-width="5" fill="none"/>'
    b += tx(330, 138, '红表笔 = 红线那边', 18, RED, 800, 'middle') + tx(330, 162, '黑表笔 = 黑线那边', 18, BLK, 800, 'middle')
    return svg(860, 285, b, '量插头电压')


def bench():
    b = '<rect x="20" y="40" width="240" height="160" rx="10" fill="#37474f"/>' + tx(140, 88, '可调电源', 24, '#fff', 800, 'middle') + tx(140, 124, '5.0 V · 0.3 A', 26, '#ffd54f', 800, 'middle')
    b += f'<circle cx="90" cy="165" r="16" fill="{RED}"/><circle cx="190" cy="165" r="16" fill="#111" stroke="#fff"/>'
    b += '<rect x="520" y="70" width="130" height="100" rx="8" fill="#2f2f2f"/><rect x="620" y="70" width="60" height="100" fill="#35b27a"/>' + tx(650, 106, '+', 26, '#fff', 800, 'middle') + tx(650, 156, '−', 26, '#fff', 800, 'middle') + tx(565, 126, '转接头', 18, '#fff', 700, 'middle')
    b += f'<path d="M90 181 V240 H470 C520 240 590 180 650 96" stroke="{RED}" stroke-width="6" fill="none"/><path d="M190 181 V215 H440 C500 215 590 200 650 146" stroke="{BLK}" stroke-width="6" fill="none"/>'
    b += tx(395, 30, '可调电源的线接到转接头端子', 20, INK, 700, 'middle') + tx(395, 58, '适配器这时不要插', 20, BAD, 800, 'middle')
    return svg(720, 265, b, '可调电源接线')


def card(n, title, body):
    return f'<section><h2><label><input type="checkbox"> {n}. {title}</label></h2>{body}</section>'


jack = photo('dc_jack_terminal.jpg', 600, 450, ring(386, 268, 36) + ring(424, 256, 36) + tag(190, 150, '螺丝：从上面拧', BAD) + ring(396, 345, 30, OK) + ring(440, 320, 30, OK) + tag(80, 410, '线从这两个孔插进去', OK), 'DC 转接头')
xt = photo('xt60_pair.jpg', 600, 480, ring(450, 250, 150, OK) + tag(350, 80, '买这个：公头', OK) + tag(20, 80, '板子上的母座', MUT), 'XT60')
xhc = photo('xh_cable_female.jpg', 600, 480, tag(300, 90, 'XH 线，白色插头', OK), 'XH 线')
adp = photo('adapter_5v10a.jpg', 640, 480, tag(250, 70, '5V 10A 适配器', OK), '适配器')
eye_pol = pcb('eye', [('H1', 2, 'H1 第 2 脚：测 +', RED, 330, -1100), ('H1', 3, 'H1 第 3 脚：测 −', '#111', 330, -880), ('U1', 2, 'XH 口在背面', '#0b57a4', -1050, -1100)], '眼部板极性测试点', left=1100, right=1100, crop=(.42, 'top'))
eye_v = pcb('eye', [('J1', 3, 'J1 的 +：红表笔', RED, 330, 700), ('J1', 5, 'J1 的 −：黑表笔', '#111', 330, 900)], '眼部板 V+ 测试点', left=1100, right=1100, crop=(.35, 'bot'))
mouth_v = pcb('mouth', [('U3', 3, 'U3 的 +：红表笔', RED, 3800, 4300), ('U3', 5, 'U3 的 −：黑表笔', '#111', 3800, 4700), ('U1', 3, 'XT60 口', '#0b57a4', 3800, 3300)], '嘴部板 V+ 测试点', left=1500, right=120)

html = f'''<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="color-scheme" content="light"><title>电源线焊接流程</title>
<style>:root{{color-scheme:light}}body{{margin:0;background:#f4f4f1;color:{INK};font:17px/1.65 -apple-system,"PingFang SC",sans-serif}}main{{max-width:900px;margin:auto;padding:20px 16px 60px}}h1{{font-size:28px;margin:6px 0}}h2{{font-size:20px;margin:0 0 8px}}h2 input{{width:20px;height:20px;vertical-align:-3px}}section{{background:#fff;border:1px solid #dddcd6;border-radius:12px;padding:16px;margin:14px 0}}svg{{width:100%;height:auto;display:block;margin:10px 0;background:#fff;border-radius:8px}}.g{{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:10px}}.w{{background:#fdecea;border-left:4px solid {BAD};padding:8px 12px;border-radius:6px}}.k{{background:#e8f4ec;border-left:4px solid {OK};padding:8px 12px;border-radius:6px}}table{{border-collapse:collapse;width:100%}}th,td{{border:1px solid #dddcd6;padding:7px 9px;text-align:left}}th{{background:#f2f2ee}}figcaption{{font-size:14px;color:{MUT}}}figure{{margin:0}}</style></head><body><main>
<h1>电源线焊接流程（方案 A）</h1>
<p>适配器 → DC 转接头 → 分成 3 路。全程<b>不插 Pico、不接舵机</b>。零件实物以你手上的印字为准，图里的照片只用来认形状。</p>
<section><h2>接完是这样</h2>{overview()}</section>
<section><h2>认零件</h2><div class="g"><figure>{adp}<figcaption>插墙，另一头是 DC 圆头</figcaption></figure><figure>{jack}<figcaption>DC 转接头，端子上印 + 和 −</figcaption></figure><figure>{xt}<figcaption>线上用公头，里面是两根金针</figcaption></figure><figure>{xhc}<figcaption>2 根，眼部板和眉部板各 1 根</figcaption></figure></div>
<p>还要准备：烙铁（约 350°C）、焊锡、剥线钳、万用表、直径约 6 mm 的热缩管 2 段（每段约 25 mm），没有热缩管就用电工胶布。</p></section>
<div class="w"><b>全程适配器不要插墙。</b>第 8 步才第一次通电。</div>
{card(1, '剥线', f'{strip()}<p>红线 3 根：1 根 XT60 粗线，2 根 XH 细线。都剥 15 mm，不要剪断铜丝。</p>')}
{card(2, '先套热缩管', f'{tube()}<p>把 3 根线剥好的一端一起穿进热缩管，推到离接头远的地方。这一步忘了，焊完就套不进去了。</p>')}
{card(3, '把细线绕在粗线根部', f'{wrap()}<p>两根细线的铜丝绕在粗线裸铜的根部，紧贴绝缘皮，绕 2 圈左右。前端 7 mm 什么都不绕。</p>')}
{card(4, '只焊根部', f'{wrap(True)}<p>烙铁头贴住缠线处，焊锡送到线上，焊锡流满缠线就移开，一般几秒内完成。冷却前别动线。</p><div class="w"><b>前端 7 mm 不上锡。</b>这段要进螺丝端子，上锡后时间久了容易松。</div><p>冷却后分别拉一下 3 根线，不能松动。</p>')}
{card(5, '收缩热缩管，再做黑线', f'{shrunk()}<p>把热缩管推到焊点上，用热风枪或打火机远处烘烤收缩。露出的只有前端 7 mm。黑线按第 1 到第 5 步再做一遍。</p>')}
{card(6, '接到转接头', f'<div class="g"><figure>{jack}</figure><div><p>1. 松开端子螺丝。</p><p>2. <b>红线裸铜插 +，黑线裸铜插 −</b>。</p><p>3. 拧紧后用手拉一下，不能拔出来。</p><p>4. 铜丝不能露出端子太多，也不能碰到另一边。露太多就剪短一点。</p></div></div>')}
{card(7, '通电前量短路', f'{short_test()}<p>万用表打蜂鸣档，量转接头 + 和 −。<b>不应该响</b>。响了就是红黑碰到了，先别通电，回去查端子和焊点。</p>')}
{card(8, '量 3 个插头的电压', f'{plug_test()}<p>这一步还没接板子。插上适配器，3 个插头都量一遍：</p><table><tr><th>量哪里</th><th>应该</th></tr><tr><td>转接头 + 和 −</td><td>5.0～5.2 V</td></tr><tr><td>2 个 XH 插头</td><td>5.0～5.2 V</td></tr><tr><td>XT60 公头</td><td>5.0～5.2 V</td></tr></table><div class="w">超过 5.5 V 不要往下接。量完<b>拔掉适配器</b>，再做下一步。</div>')}
{card(9, '眼部板、眉部板：确认 XH 线没反', f'{eye_pol}<p>XH 线插到板子上，<b>不通电</b>，不插 Pico。万用表打蜂鸣档，一支表笔放转接头，另一支伸进 Pico 排母的孔里：</p><table><tr><th>转接头</th><th>Pico 插座</th><th>应该</th></tr><tr><td>+</td><td>H1 第 2 脚（USB 端数第 2 个）</td><td>响</td></tr><tr><td>−</td><td>H1 第 3 脚</td><td>响</td></tr></table><p>两项都不响：XH 线多半反了，用镊子挑出端子对调。只有第 2 脚不响：查 C12 有没有短接好。两块板都要测。</p>')}
{card(10, '第一次给板子上电：用可调电源', f'{bench()}<p>一次只接一块板。设 5.0 V、限流 0.3 A，电源线松开端子塞进去，或用鳄鱼夹夹在 + 和 − 的裸铜上，接好后再打开输出。电流如果顶到限流，马上关掉查板子。</p><div class="k"><b>眼部板、眉部板：</b>量 J1 的 + 和 −，应该是 4.7～4.9 V。</div>{eye_v}<div class="k"><b>嘴部板：</b>XT60 插好，量 U3 的 + 和 −，应该是 4.7～4.9 V。读数接近 0 或是负数，马上关电源，查 XT60 线的红黑。</div>{mouth_v}')}
{card(11, '换回适配器', '<p>三块板都通过后，关掉可调电源，拆下它的线，再把 DC 圆头插进转接头，插上适配器。</p><p>后面插 Pico、接舵机按 <code>焊接流程.html</code> 的“插 Pico 联调”做。整机跑起来后摸一下 DC 插头和端子，明显发烫就停机，换更粗的接线方式。</p>')}
</main></body></html>'''
open(OUT, 'w', encoding='utf8').write(html)
print('ok', len(html) // 1024, 'KB')
