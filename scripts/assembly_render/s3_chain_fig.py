"""图 9 的补充：14 个 M3 关节分成上唇、嘴角、下唇三组，每个零件一种颜色并写上 STL 名字。
只画机器人左侧（x+），右侧镜像，名字见表。零件沿 x 方向拉开，虚线 = 台阶螺丝穿过的位置。"""
import numpy as np
from render import render
from jaw_m2_fig import b64

COL = [(0.31, 0.47, 0.65), (0.95, 0.56, 0.17), (0.35, 0.63, 0.31), (0.69, 0.48, 0.63)]
VIEW = (-0.78, 0.50, -0.30)
# 组名, 零件(组号, 名字, 外移量), 关节(编号, 螺丝组, 转动零件, 拧进零件)
GROUPS = [
    ('上唇组', [(105, 'UpperLeftLip', 0), (159, 'ULLLinkA', 16), (93, 'ULLLinkB', 16)], [(1, 85, 159, 105), (2, 104, 93, 105)]),
    ('嘴角组', [(98, 'Part_30', 0), (157, 'Part_31', 16), (171, 'Part_29', 16), (130, 'Part_32', 32)], [(3, 158, 157, 98), (4, 136, 171, 98), (5, 143, 130, 171)]),
    ('下唇组', [(138, 'LowerLeftLip', 0), (160, 'Part_28', 16), (148, 'Part_27', 16)], [(6, 99, 160, 138), (7, 189, 148, 138)]),
]
ROWS = [(1, 'ULLLinkA', 'UpperLeftLip', 'Part_35', 'Part_34'), (2, 'ULLLinkB', 'UpperLeftLip', 'Part_36', 'Part_34'),
        (3, 'Part_31', 'Part_30', 'Part_42', 'Part_41'), (4, 'Part_29', 'Part_30', 'Part_40', 'Part_41'),
        (5, 'Part_32', 'Part_29', 'Part_43', 'Part_40'), (6, 'Part_28', 'LowerLeftLip', 'Part_39', 'Part_37'),
        (7, 'Part_27', 'LowerLeftLip', 'Part_38', 'Part_37')]


def panel(S, title, parts, joints):
    W, H = 640, 520
    off = {g: o for g, _, o in parts}
    items, fit = [], []
    for i, (g, _, o) in enumerate(parts):
        d = np.array([o, 0, 0.0])
        items.append((S.tris(g, d), COL[i], g)); fit.append(S.pts(g) + d)
    im, proj, _ = render(items, VIEW, W=W, H=H, fit=np.concatenate(fit), margin=0.14)
    b = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H}"/>']
    for n, s, rot, recv in joints:
        h, t, a, _ = S.screw_axis(s)
        x0, y0 = proj(h + np.array([off[rot] + 8, 0, 0])); x1, y1 = proj(t + np.array([off[recv], 0, 0]))
        b.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#222" stroke-width="2" stroke-dasharray="6 4"/>'
                 f'<circle cx="{x0:.1f}" cy="{y0:.1f}" r="14" fill="#c62828" stroke="#fff" stroke-width="2"/>'
                 f'<text x="{x0:.1f}" y="{y0 + 6:.1f}" text-anchor="middle" font-size="17" font-weight="800" style="fill:#fff!important">{n}</text>')
    lx = 14
    for i, (g, name, _) in enumerate(parts):
        c = '#%02x%02x%02x' % tuple(int(v * 255) for v in COL[i])
        y = H - 16 - 26 * (len(parts) - 1 - i)
        b.append(f'<rect x="{lx}" y="{y - 15}" width="18" height="18" rx="3" fill="{c}"/><text x="{lx + 26}" y="{y}" font-size="19" font-weight="700" style="fill:#1d1d1f!important" paint-order="stroke" stroke="#fff" stroke-width="4">{name}</text>')
    b.append(f'<text x="{W / 2}" y="30" text-anchor="middle" font-size="24" font-weight="800" style="fill:#1d1d1f!important">{title}</text>')
    return f'<div class="fig3d"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">{"".join(b)}</svg></div>'


def nut_panel(S):
    """从头中线一侧看 UpperLeftLip：两个六角槽开在背面"""
    W, H = 640, 420
    im, proj, _ = render([(S.tris(105), (0.31, 0.47, 0.65), 105)], (0.86, 0.35, 0.2), W=W, H=H, margin=0.1)
    b = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H}"/>']
    for s in (85, 104):
        x, y = proj(S.screw_axis(s)[1])
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="24" fill="none" stroke="#c62828" stroke-width="3.5"/>')
    b.append('<text x="16" y="32" font-size="22" font-weight="800" style="fill:#1d1d1f!important">UpperLeftLip 背面，红圈 = M3 六角螺母槽</text>')
    return f'<div class="fig3d" style="max-width:520px"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="M3 螺母槽位置">{"".join(b)}</svg></div>'


def html(S):
    return ('<h4>螺丝拧进哪里：M3 六角螺母，不用热熔螺母</h4>'
            '<p>14 个 M3 台阶螺丝都拧进<b>普通 M3 六角螺母</b>，一共 14 颗。下表“拧进”列的零件上，螺丝孔的背面（朝头中线那面）有六角槽，槽深 2.6 mm，对边约 5.7 mm。</p>'
            '<ol><li>螺母从背面放进六角槽。</li><li>从外面穿过转动零件，再穿过 Ø3.6 孔，拧进螺母。</li><li>拧到台阶靠住就停，确认转动零件能自由转。</li></ol>'
            '<p>关节 5 的槽底只有约 0.3 mm 厚（Part_29 / Part_40），这里轻拧，别把槽底顶穿。</p>'
            + nut_panel(S) +
            '<h4>14 个关节分别接哪两个零件</h4><p>图只画机器人左侧，零件拉开了，装好后贴在一起。红圈编号 = 台阶螺丝从这里穿进去。'
            '<b>外层零件转动</b>（孔 Ø4.3），螺丝拧进内层零件背面的 M3 螺母。名字就是 plate 2 里的 STL 文件名。</p>'
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px">'
            + ''.join(panel(S, *g) for g in GROUPS) + '</div>'
            '<table class="sc"><thead><tr><th>关节</th><th>左侧：转动零件</th><th>左侧：拧进</th><th>右侧：转动零件</th><th>右侧：拧进</th></tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in ROWS) + '</tbody></table>')
