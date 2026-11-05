"""图 3：颧骨、眼部底板、头骨框架分开画，每个零件都画完整，孔口朝向一眼能看到。
三个零件左右对称，这里从机器人左侧斜看，标左侧的孔；右侧在对称位置。"""
import numpy as np
from render import render
from jaw_m2_fig import b64

C_RECV = (0.60, 0.74, 0.92)
C_SKULL = (0.93, 0.92, 0.88)
VIEW = (-0.86, 0.30, -0.42)   # 视线方向：从机器人左前上方看
PANELS = [
    (27, C_RECV, '颧骨：每侧 2 个，共 4 个', [(72.5, -8.8, -27.2), (72.5, -25.6, -27.2)], []),
    (44, C_RECV, '眼部底板：每侧 2 个，共 4 个', [(72.7, -8.8, -15.2), (72.7, -25.6, -15.2)], [(72.7, 8.0, -15.2)]),
    (0, C_SKULL, '头骨框架：每侧 3 个，共 6 个（可以先不压）', [(76.8, -2.1, 24.6), (76.7, -3.5, 15.7), (76.8, -5.0, 6.9)], []),
]


def panel(S, g, col, title, pts, opt):
    W, H = 640, 470
    view = (-1, 0.12, -0.10) if g == 0 else VIEW
    r = 6 if g == 0 else 9
    im, proj, _ = render([(S.tris(g), col, g)], view, W=W, H=H, fit=S.pts(g), ss=2)
    b = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H}"/>']
    for p in pts:
        x, y = proj(np.array(p))
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#e0a526" stroke="#5a3d00" stroke-width="2"/>')
    for p in opt:
        x, y = proj(np.array(p))
        b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{r}" fill="#fff" stroke="#b26a00" stroke-width="3" stroke-dasharray="4 3"/>')
    b.append(f'<text x="{W / 2}" y="28" text-anchor="middle" font-size="22" font-weight="700" style="fill:#1d1d1f!important" paint-order="stroke" stroke="#fff" stroke-width="5">{title}</text>')
    return f'<div class="fig3d"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">{"".join(b)}</svg></div>'


BROW = 77
BROW_OUT = dict(view=VIEW, m4=[(43.6, -6.5, 60.6), (43.6, -6.5, 49.5), (43.6, -6.5, 38.4), (35.4, -57.4, 63.6), (59.6, -22.2, 65.7)],
                m2=[(50.6, -22.2, 58.5), (50.6, -22.2, 30.5)], title='眉毛底板 · 朝外的孔（左侧 M4 ×5、M2 ×2）')
BROW_IN = dict(view=(0.86, 0.30, -0.42), m4=[(17.5, -57.3, 65.7)], m2=[(26.55, -57.3, 58.5), (26.55, -57.3, 30.5)],
               title='眉毛底板 · 朝中线的孔（左侧 M4 ×1、M2 ×2）')


def brow_panel(S, view, m4, m2, title):
    W, H = 640, 470
    im, proj, _ = render([(S.tris(BROW), (0.86, 0.82, 0.74), BROW)], view, W=W, H=H, fit=S.pts(BROW), ss=2)
    b = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H}"/>']
    for L, col, t in ((m4, '#e0a526', 'M4'), (m2, '#3b82c4', 'M2')):
        for p in L:
            x, y = proj(np.array(p))
            b.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="8" fill="{col}" stroke="#222" stroke-width="1.5"/>'
                     f'<text x="{x + 11:.1f}" y="{y - 7:.1f}" font-size="15" font-weight="800" style="fill:#1d1d1f!important" paint-order="stroke" stroke="#fff" stroke-width="4">{t}</text>')
    b.append(f'<text x="{W / 2}" y="28" text-anchor="middle" font-size="22" font-weight="700" style="fill:#1d1d1f!important" paint-order="stroke" stroke="#fff" stroke-width="5">{title}</text>')
    return f'<div class="fig3d"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">{"".join(b)}</svg></div>'


BROW_HTML = ('<h4>眉毛底板 Part_4：M4 ×12、M2 ×8（2026-11-04 补）</h4>'
             '<p>模型里这块底板没画螺丝和热熔螺母，是按孔径查出来的。图只标机器人左侧，<b>右侧对称</b>。'
             'M2 是 4 个眉毛舵机的安装耳：外侧 2 个舵机的孔朝外压，前面 2 个舵机的孔朝中线压（安装耳贴在内侧）。'
             'M4 里 8 个接头骨框架（框架上是 Ø4.6 通孔，螺丝模型没画，用 M4×10 或 M4×12）；z 最高的 4 个（x=±54.6、±22.8）用途未确认，推测是眉毛的 M4 台阶螺丝转轴。</p>')


def html(S):
    return ('<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px">'
            + ''.join(panel(S, *p) for p in PANELS) + '</div>'
            '<p>三个零件分开压，图里只标机器人左侧，<b>右侧在对称位置，数量已算进标题</b>。这些孔都朝外，从外侧往中线压。'
            '虚线白圈 = 眼部底板后侧的孔，模型没画螺丝，可压可不压。</p>'
            + BROW_HTML + '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px">'
            + brow_panel(S, **BROW_OUT) + brow_panel(S, **BROW_IN) + '</div>'
            '<h4>可选：风扇和外壳</h4><p>装这些零件才需要压，都是 M3：头骨框架接 FanBracket 6 个、FanBracket 上接风扇 4 个、头骨框架接 RearPlate 10 个、接 FrontVent 4 个。外壳先不装的话，这些都可以以后再压。'
            '框架上另有 12 个 Ø4.4 孔没有对应零件（4 个深 6、8 个深 4.5，后者疑似固定 PCB），先别压。</p>')
