"""舵机输出轴不在机身中间，偏向一头约 5 mm（MG996R 约 10 mm）；安装孔是对称的，反着也能装上，所以单独画一张。"""
import numpy as np
from render import render
from jaw_m2_fig import b64

C_BASE = (0.60, 0.74, 0.92)
C_SERVO = (0.55, 0.55, 0.60)
# 机器人左侧 (x+)，名字: (舵机组, 输出轴 y, z)
SHAFTS = {'A': (149, -52.7, -34.5), 'B': (94, -20.3, -44.4), 'C': (95, -23.3, -61.6),
          'D': (185, -2.4, -40.7), 'E': (89, -43.5, -96.8)}


def fig(S):
    W, H = 1000, 640
    items = [(S.tris(188), C_BASE, 188), (S.tris(113), (0.75, 0.84, 0.95), 113)] + [(S.tris(v[0]), C_SERVO, v[0]) for v in SHAFTS.values()]
    fit = np.concatenate([S.pts(188), S.pts(113)])
    im, proj, _ = render(items, (-1, 0, 0), W=W, H=H, fit=fit)
    b = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H}"/>']
    for k, (g, y, z) in SHAFTS.items():
        P = S.pts(g); px, py = proj(np.array([P[:, 0].max(), y, z]))
        b.append(f'<circle cx="{px:.1f}" cy="{py:.1f}" r="13" fill="none" stroke="#c62828" stroke-width="4"/>'
                 f'<text x="{px + 17:.1f}" y="{py - 11:.1f}" font-size="22" font-weight="800" style="fill:#c62828!important" paint-order="stroke" stroke="#fff" stroke-width="5">{k}</text>')
    b.append(f'<text x="16" y="28" font-size="18" font-weight="700" style="fill:#1d1d1f!important" paint-order="stroke" stroke="#fff" stroke-width="4">← 脸（前）</text>')
    return f'<div class="fig3d"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="舵机输出轴位置">{"".join(b)}</svg></div>'


def html(S):
    rows = [('A', '上颌座前部（左右各 1）', '朝外', '靠<b>前</b>（靠脸）'), ('B', '上颌座中间，上面那个（左右各 1）', '朝外', '靠<b>下</b>'),
            ('C', '上颌座中间，下面那个（左右各 1）', '朝外', '靠<b>上</b>（B、C 的轴互相靠近）'), ('D', 'MG996R（左右各 1）', '朝外', '靠<b>上</b>，偏约 10 mm'),
            ('E', '下颌座两侧（左右各 1）', '朝外', '靠<b>前</b>（靠脸）'), ('—', '下颌座中间（舌头，图上没画）', '<b>朝机器人右侧</b>', '靠<b>下</b>'),
            ('—', '眉毛外侧 2 个', '朝外', '靠<b>上</b>'), ('—', '眉毛前面 2 个', '<b>朝中线</b>', '靠<b>上</b>')]
    return ('<h4>舵机输出轴朝哪边（装之前先看）</h4><p>输出轴不在机身中间，MG90S 偏向一头约 5 mm。安装孔是对称的，<b>装反了螺丝也拧得上，但连杆位置会错</b>。'
            '图从机器人左侧看，红圈 = 输出轴，右侧镜像。</p>' + f'<div class="fig3d">{fig(S)}</div>'
            '<table class="sc"><thead><tr><th>标</th><th>舵机</th><th>输出轴朝向</th><th>输出轴靠机身哪头</th></tr></thead><tbody>'
            + ''.join(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>' for a, b, c, d in rows) + '</tbody></table>')
