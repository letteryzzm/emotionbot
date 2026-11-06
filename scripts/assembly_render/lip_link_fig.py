"""图 8 的补充：从机器人左侧看 4 根短连杆各接哪个舵机、朝哪边。右侧镜像。"""
import numpy as np
from render import render
from jaw_m2_fig import b64

C_BASE, C_SERVO, C_LINK = (0.82, 0.86, 0.92), (0.60, 0.60, 0.64), (0.30, 0.72, 0.42)
# 编号: (连杆组, 舵机组, 输出轴 y, z)
L = {1: (159, 149, -52.7, -34.5), 2: (157, 94, -20.3, -44.4), 3: (130, 95, -23.3, -61.6), 4: (148, 89, -43.5, -96.8)}


def fig(S):
    W, H = 1000, 640
    items = [(S.tris(188), C_BASE, 188), (S.tris(113), C_BASE, 113)]
    items += [(S.tris(v[1]), C_SERVO, v[1]) for v in L.values()] + [(S.tris(v[0]), C_LINK, v[0]) for v in L.values()]
    im, proj, _ = render(items, (-1, 0, 0), W=W, H=H, fit=np.concatenate([S.pts(188), S.pts(113), S.pts(130), S.pts(159)]))
    b = [f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{H}"/>']
    for k, (g, _, y, z) in L.items():
        x, yy = proj(np.array([S.pts(g)[:, 0].max() + 1, y, z]))
        b.append(f'<circle cx="{x:.1f}" cy="{yy:.1f}" r="15" fill="#c62828" stroke="#fff" stroke-width="2"/>'
                 f'<text x="{x:.1f}" y="{yy + 6:.1f}" text-anchor="middle" font-size="18" font-weight="800" style="fill:#fff!important">{k}</text>')
    b.append('<text x="16" y="28" font-size="18" font-weight="700" style="fill:#1d1d1f!important" paint-order="stroke" stroke="#fff" stroke-width="4">← 脸（前）　绿色 = 连杆，红圈 = 输出轴和 M2.5 螺丝</text>')
    return f'<div class="fig3d"><svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="嘴唇连杆朝向">{"".join(b)}</svg></div>'


def html(S):
    rows = [(1, '上颌座前部 · 上唇 LUL / LUR', 'ULLLinkA', 'Part_35', '朝前，略向下', '13.7'), (2, '上颌座中间上面 · 嘴角上下 CUL / CUR', 'Part_31', 'Part_42', '朝前上方约 45°', '14.5'),
            (3, '上颌座中间下面 · 嘴角前后 CLL / CLR', 'Part_32', 'Part_43', '朝前下方约 45°', '18.7'), (4, '下颌座两侧 · 下唇 LLL / LLR', 'Part_27', 'Part_38', '朝前，略向上', '13.4')]
    return ('<h4>4 根连杆分别接哪个舵机、朝哪边</h4><p>从机器人左侧看，<b>所有连杆都朝脸的方向伸出</b>，右侧镜像。朝向是模型姿态，装的时候舵机在 90°，差一个齿以内都正常；差很多就拔下来换齿位，不要硬掰。</p>'
            + fig(S) + '<table class="sc"><thead><tr><th>标</th><th>舵机</th><th>机器人左侧零件</th><th>机器人右侧零件</th><th>连杆朝向</th><th>孔距 mm</th></tr></thead><tbody>'
            + ''.join('<tr>' + ''.join(f'<td>{c}</td>' for c in r) + '</tr>' for r in rows) + '</tbody></table>'
            '<p>顺序：舵机 → 连杆中心孔套上输出轴 → M2.5×8 从外往里拧，连杆贴紧但别拧到舵机转不动。</p>')
