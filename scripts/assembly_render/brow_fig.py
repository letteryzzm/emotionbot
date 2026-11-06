"""图 15 的补充：眉毛机构每个结构件的名字、数量和连接关系。
模型没画眉毛的螺丝，紧固件按孔径、同轴关系和螺母槽推出来。x+ = 机器人左。"""
import numpy as np
from render import render
from jaw_m2_fig import b64

BASE, SERVO, P2, P3, ARM, TPU = (0.78, 0.80, 0.84), (0.33, 0.35, 0.40), (0.95, 0.56, 0.17), (0.35, 0.63, 0.31), (0.31, 0.47, 0.65), (0.69, 0.48, 0.63)
OUT, IN, BR = np.array([-16.0, 0, 0]), np.array([16.0, 0, 0]), np.array([-16.0, -22, -16])
VIEW = (0.62, 0.70, -0.36)
# 字母, 从(零件上的孔, 偏移), 到(孔, 偏移)
J = [('A', (-62.6, -22.3, 65.7), OUT, (-54.6, -22.3, 65.8), 0), ('B', (-62.6, -34.2, 66.6), OUT, (-59.6, -34.0, 66.1), 0),
     ('C', (-62.6, -34.0, 50.6), OUT, (-59.6, -34.1, 50.1), 0), ('D', (-65.5, -22.0, 49.9), OUT, (-64.0, -22.0, 49.9), 0),
     ('A', (-14.4, -57.3, 65.8), IN, (-22.8, -57.3, 65.8), 0), ('B', (-14.4, -69.2, 65.4), IN, (-17.5, -69.2, 65.4), 0),
     ('C', (-14.4, -69.2, 49.4), IN, (-17.5, -69.2, 49.4), 0), ('D', (-11.6, -57.3, 49.7), IN, (-13.1, -57.3, 49.7), 0),
     ('E', (-67.5, -54.9, 23.9), BR, (-66.1, -54.7, 24.9), 0), ('E', (-24.5, -91.3, 36.5), BR, (-24.1, -89.5, 36.6), 0)]
NAMES = [('Part_4 底板', 77, 0, (-40, -30, 75)), ('Part_2 连杆', 71, OUT, (-64, -38, 78)), ('Part_3 连杆', 78, OUT, (-66, -40, 40)),
         ('Part_9 外侧臂', 76, 0, (-60, -44, 62)), ('Part_8 内侧臂', 68, 0, (-5, -82, 70)), ('Part_11 软眉毛', 66, BR, (-40, -105, 5))]


def overview(S):
    W, H = 1000, 760
    z = np.zeros(3)
    items = [(S.tris(77), BASE, 77), (S.tris(75), SERVO, 75), (S.tris(79), SERVO, 79), (S.tris(76), ARM, 76), (S.tris(68), ARM, 68),
             (S.tris(71, OUT), P2, 71), (S.tris(78, OUT), P3, 78), (S.tris(74, IN), P2, 74), (S.tris(72, IN), P3, 72), (S.tris(66, BR), TPU, 66)]
    fit = np.concatenate([S.pts(77)[S.pts(77)[:, 0] < 5], S.pts(71) + OUT, S.pts(72) + IN, S.pts(66) + BR])
    im, proj, _ = render(items, VIEW, W=W, H=H, fit=fit, margin=0.1)
    b = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H}"/>']
    for k, p, off, q, _ in J:
        x0, y0 = proj(np.array(p) + off); x1, y1 = proj(np.array(q))
        b.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#222" stroke-width="2" stroke-dasharray="6 4"/>'
                 f'<circle cx="{x0:.1f}" cy="{y0:.1f}" r="14" fill="#c62828" stroke="#fff" stroke-width="2"/>'
                 f'<text x="{x0:.1f}" y="{y0 + 6:.1f}" text-anchor="middle" font-size="17" font-weight="800" style="fill:#fff!important">{k}</text>')
    leg = [('Part_4 底板', BASE), ('Part_2 连杆 ×4', P2), ('Part_3 连杆 ×4', P3), ('臂 Part_8 / 9 / 12 / 13', ARM), ('软眉毛 Part_11 / 14（TPU）', TPU), ('MG90S', SERVO)]
    for i, (n, c) in enumerate(leg):
        y = 34 + 27 * i
        col = '#%02x%02x%02x' % tuple(int(v * 255) for v in c)
        b.append(f'<rect x="16" y="{y - 15}" width="18" height="18" rx="3" fill="{col}"/><text x="42" y="{y}" font-size="19" font-weight="700" style="fill:#1d1d1f!important" paint-order="stroke" stroke="#fff" stroke-width="4">{n}</text>')
    return f'<div class="fig3d"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="眉毛机构分解图">{"".join(b)}</svg></div>'


def shot(S, g, dirv, color, W=300, H=260, up=(0, 0, 1)):
    im, _, _ = render([(S.tris(g), color, g)], dirv, W=W, H=H, margin=0.08, up=up)
    return im


def card(S, title, sub, shots):
    W, H, T = 300, 260, 50
    w = W * len(shots)
    s = [f'<text x="12" y="30" font-size="21" font-weight="800" style="fill:#1d1d1f!important">{title}</text>']
    for i, (g, d, c, cap) in enumerate(shots):
        s.append(f'<image href="data:image/png;base64,{b64(shot(S, g, d, c))}" x="{i * W}" y="{T}" width="{W}" height="{H}"/>')
        s.append(f'<text x="{i * W + W / 2}" y="{T + H + 20}" text-anchor="middle" font-size="17" font-weight="700" style="fill:#1d1d1f!important">{cap}</text>')
    s.append(f'<text x="12" y="{T + H + 48}" font-size="16" font-weight="600" style="fill:#555!important">{sub}</text>')

    wide = ' style="grid-column:1/-1;max-width:640px"' if len(shots) > 1 else ''
    return f'<div class="fig3d"{wide}><svg viewBox="0 0 {w} {T + H + 60}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">{"".join(s)}</svg></div>'


def html(S):
    X, Xm = (-1, 0, 0), (1, 0, 0)
    cards = [card(S, 'Part_2 ×4', '薄片，厚 2.9，两个光孔', [(70, X, P2, 'Ø5.2 + Ø4.3，孔距 12')]),
             card(S, 'Part_3 ×4', '有台阶，轴端厚 5.9，和嘴部连杆同类', [(67, X, P3, 'Ø3 + Ø4.3，孔距 12')]),
             card(S, '外侧臂（长约 58）', 'Part_9 和 Part_13 互为镜像，按 STL 名字分左右，打印时做好记号', [(76, Xm, ARM, 'Part_9 机器人右，Part_13 是它的镜像')]),
             card(S, '内侧臂（长约 46）', 'Part_8 和 Part_12 互为镜像，左右不能互换', [(68, X, ARM, 'Part_8 机器人右，Part_12 是它的镜像')]),
             card(S, '软眉毛（TPU）', '长约 68，两端各一个 Ø3.5 孔，左右镜像', [(69, (-0.2, 1, 0.2), TPU, 'Part_14 机器人左'), (66, (0.2, 1, 0.2), TPU, 'Part_11 机器人右')])]
    rows = [('A', 'M4 台阶螺丝', 4, 'Part_2 的 Ø5.2 孔（能转）', '底板 Part_4 · M4 热熔螺母'),
            ('B', 'M3 台阶螺丝', 4, 'Part_2 的 Ø4.3 孔（能转）', '臂的上孔 · 背面 M3 螺母'),
            ('C', 'M3 台阶螺丝', 4, 'Part_3 的 Ø4.3 孔（能转）', '臂的下孔 · 背面 M3 螺母'),
            ('D', 'M2.5×8', 4, 'Part_3 的台阶孔', 'MG90S 输出轴'),
            ('E', 'M3×6（待试装）', 4, '软眉毛 Ø3.5 孔，螺丝头沉进 Ø5.7 窝', '臂末端 · 背面 M3 螺母'),
            ('—', 'M2×6', 8, 'MG90S 安装耳', '底板 Part_4 · M2 热熔螺母')]
    return ('<h4>眉毛的结构：每个角都是一组平行连杆</h4><p>眉毛有 4 个角，机器人左右各 2 个（外侧、内侧）。每个角是同一种结构：<b>舵机 → Part_3 → 臂 ← Part_2 ← 底板</b>。'
            'Part_3 由舵机带动，Part_2 只跟着转，两根孔距都是 12，所以臂上下平移，带动软眉毛。</p>'
            + overview(S) +
            '<p>图是机器人右半边，连杆和软眉毛拉开了画。左半边镜像，换成 Part_13、Part_12、Part_14。模型里只有右边 2 个舵机。</p>'
            '<table class="sc"><thead><tr><th>标</th><th>紧固件</th><th>数量</th><th>穿过</th><th>拧进</th></tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows) + '</tbody></table>'
            '<p><b>模型里没画这些螺丝</b>，表是按孔径、同轴关系和螺母槽推出来的，先装一个角试转。E 的长度模型里量不准，M3×6 太短就换 M3×8。</p>'
            '<p><b>连杆在哪一面：</b>外侧两个角的 Part_2、Part_3 贴在臂的外面，内侧两个角贴在靠头中线的一面，都和舵机轴同一边。臂上的 M3 螺母槽开在连杆的对面。Part_3 的台阶孔朝舵机。</p>'
            '<h4>认零件</h4><div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:8px">' + ''.join(cards) + '</div>'
            '<p class="muted">STL 文件名写的 Part_2、Part_3 是 x1，实际各要 4 个；打印 plate 4 的 13 个零件里已经包含。</p>')
