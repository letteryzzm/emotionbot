"""图 8 的补充：4 种舵机连杆的 1 比 1 比例对照图，轴孔对齐，方便按长度和台阶认零件。
数据来自 mesh：每种连杆自身关于孔连线对称，左右两根形状相同。"""
import numpy as np
from render import render
from jaw_m2_fig import b64

C = (0.30, 0.72, 0.42)
PX = 20  # 每 mm 像素，4 张图同一比例
U0, U1, V = -6.0, 25.0, 6.5
W = int((U1 - U0) * PX)
HF, HS = int(2 * V * PX), 170
# 图8行, 左, 右, 组号, 轴孔(y,z), Ø4.3孔(y,z), 孔距, 总长, 轴端厚, 薄臂位置
T = [(1, 'ULLLinkA', 'Part_35', 159, (-52.7, -34.5), (-66.0, -37.7), 13.7, 22.7, 5.7, '抬起'),
     (2, 'Part_31', 'Part_42', 157, (-20.3, -44.4), (-31.0, -34.6), 14.5, 23.5, 6.2, '抬起'),
     (3, 'Part_32', 'Part_43', 130, (-23.3, -61.6), (-37.2, -74.1), 18.7, 27.7, 6.2, '抬起'),
     (4, 'Part_27', 'Part_38', 148, (-43.5, -96.8), (-56.5, -93.7), 13.4, 22.4, 4.9, '贴桌面')]


def shot(S, g, f, up, a, d, w_axis, h, hh):
    xm = S.pts(g)[:, 0].mean()
    o = np.array([xm, a[0], a[1]])
    box = np.array([o + d * u + w_axis * v for u in (U0, U1) for v in (-h, h)])
    im, proj, _ = render([(S.tris(g), C, g)], f, W=W, H=hh, fit=box, margin=0, up=up)
    return im, proj, o


def card(S, row, l, r, g, a, b, dist, tot, hub, arm):
    a, b = np.array(a), np.array(b)
    d2 = (b - a) / np.linalg.norm(b - a)
    d = np.array([0, d2[0], d2[1]]); n = np.array([0, -d2[1], d2[0]]); x = np.array([1.0, 0, 0])
    side, ps, o = shot(S, g, np.cross(x, d), x, a, d, x, HS / PX / 2, HS)
    face, pf, _ = shot(S, g, x, np.cross(d, x), a, d, n, V, HF)
    TOP = 46
    H = TOP + HS + HF + 30
    t = ('<text x="{}" y="{}" text-anchor="{}" font-size="{}" font-weight="{}" style="fill:{}!important">{}</text>').format
    s = [t(14, 30, 'start', 24, 800, '#1d1d1f', f'第 {row} 行：{l} / {r}'),
         f'<image href="data:image/png;base64,{b64(side)}" x="0" y="{TOP}" width="{W}" height="{HS}"/>',
         f'<image href="data:image/png;base64,{b64(face)}" x="0" y="{TOP + HS}" width="{W}" height="{HF}"/>']
    x0, y0 = pf(o); x1, _ = pf(o + d * dist)
    y0 += TOP + HS
    s.append(f'<line x1="{x0:.0f}" y1="{y0:.0f}" x2="{x1:.0f}" y2="{y0:.0f}" stroke="#c62828" stroke-width="2.5"/>'
             f'<circle cx="{x0:.0f}" cy="{y0:.0f}" r="4" fill="#c62828"/><circle cx="{x1:.0f}" cy="{y0:.0f}" r="4" fill="#c62828"/>')
    s.append(f'<text x="{(x0 + x1) / 2:.0f}" y="{y0 - 10:.0f}" text-anchor="middle" font-size="19" font-weight="800" style="fill:#c62828!important" paint-order="stroke" stroke="#fff" stroke-width="4">孔距 {dist}</text>')
    s.append(t(W - 14, TOP + HS - 8, 'end', 16, 600, '#555', '侧面，上 = 朝外，下 = 朝舵机'))
    s.append(t(14, TOP + HS + 22, 'start', 16, 600, '#555', '朝舵机的一面'))
    s.append(t(W - 14, H - 10, 'end', 18, 700, '#1d1d1f', f'总长 {tot}　轴端厚 {hub}'))
    return f'<div class="fig3d"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{l} 对照图">{"".join(s)}</svg></div>'


def html(S):
    rows = ''.join(f'<tr><td>{r[0]}</td><td>{r[1]} / {r[2]}</td><td>{r[6]}</td><td>{r[7]}</td><td>{r[8]}</td><td>{r[9]}</td></tr>' for r in T)
    return ('<h4>图 8 每一行是哪个零件</h4><p>图 8 从上到下 4 行，每行左右各一根，一共 4 种。<b>每种的两根形状相同，左右可以互换，只要别换到别的行。</b></p>'
            '<table class="sc"><thead><tr><th>图 8 第几行</th><th>STL 名字</th><th>孔距 mm</th><th>总长 mm</th><th>轴端厚 mm</th><th>舵机面朝下放，薄臂</th></tr></thead><tbody>'
            + rows + '</tbody></table>'
            '<p><b>按这个顺序分：</b></p><ol>'
            '<li>先挑出 8 根舵机连杆：一端是台阶孔，外面 Ø3 小孔，朝舵机的一面是 Ø4.4 光滑沉孔，舵机轴插进这个沉孔。两端都是直通孔的（Ø5.3 + Ø4.3：ULLLinkB、Part_36、Part_28、Part_39）不属于这一步。</li>'
            '<li>沉孔一面朝下放在桌上。薄臂贴着桌面的 2 根是第 4 行。</li>'
            '<li>剩下 6 根里最长的 2 根是第 3 行，比其他的长 4 mm 以上。</li>'
            '<li>最后 4 根量轴端厚度或总长：6.2 / 23.5 是第 2 行，5.7 / 22.7 是第 1 行。这两种只差 0.5 到 0.8 mm，要用卡尺；没有卡尺就把 4 根并排比。</li></ol>'
            '<div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(340px,1fr));gap:8px">'
            + ''.join(card(S, *r[:7], r[7], r[8], r[9]) for r in T) + '</div>')
