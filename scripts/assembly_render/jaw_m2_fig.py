"""图 2 的补充图：下颌座 6 个 M2 孔都是通孔，两头一样大，要按舵机安装耳的位置判断从哪头压。"""
import base64, io
import numpy as np
from render import render

C_JAW = (0.60, 0.74, 0.92)
C_SERVO = (0.62, 0.62, 0.66)
JAW, SERVOS = 113, (155, 109, 89)
# 编号: (孔口坐标, 螺丝头方向 +1=从 x+ 来)
H = {1: ((20.4, -24.4, -97.1), 1), 2: ((20.4, -52.4, -96.7), 1),
     3: ((-20.7, -24.4, -97.1), -1), 4: ((-20.7, -52.4, -96.7), -1),
     5: ((-0.8, -9.1, -74.3), -1), 6: ((-0.8, -14.5, -101.8), -1)}


def b64(im):
    buf = io.BytesIO(); im.save(buf, 'PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def mark(x, y, n):
    return (f'<circle cx="{x:.1f}" cy="{y:.1f}" r="11" fill="#e0a526" stroke="#5a3d00" stroke-width="1.5"/>'
            f'<text x="{x:.1f}" y="{y + 4.5:.1f}" text-anchor="middle" font-size="13" font-weight="800" style="fill:#3a2600!important">{n}</text>')


def label(x, y, t, anchor='middle', size=14):
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" font-size="{size}" font-weight="700" style="fill:#1d1d1f!important" '
            f'paint-order="stroke" stroke="#fff" stroke-width="4">{t}</text>')


def svg(im, W, Hh, body, title):
    return (f'<svg viewBox="0 0 {W} {Hh}" xmlns="http://www.w3.org/2000/svg" role="img" aria-label="{title}">'
            f'<image href="data:image/png;base64,{b64(im)}" x="0" y="0" width="{W}" height="{Hh}"/>{body}</svg>')


def top_view(S):
    W, Hh = 1000, 640
    items = [(S.tris(JAW), C_JAW, JAW)] + [(S.tris(g), C_SERVO, g) for g in SERVOS]
    fit = np.concatenate([S.pts(JAW), S.pts(155), S.pts(109), S.pts(89),
                          np.array([[62, -40, -90], [-62, -40, -90]], float)])
    im, proj, _ = render(items, (0, 0, -1), W=W, H=Hh, fit=fit, up=(0, -1, 0))
    g = ['<defs><marker id="m2a" markerWidth="9" markerHeight="9" refX="7" refY="4" orient="auto">'
         '<path d="M0,0 L8,4 L0,8 z" fill="#c62828"/></marker></defs>']
    for n, (p, s) in H.items():
        p = np.array(p); x1, y1 = proj(p); x0, y0 = proj(p + np.array([s * 26, 0, 0]))
        g.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" stroke="#c62828" stroke-width="3" marker-end="url(#m2a)"/>')
        g.append(mark(x0, y0, n))
    g.append(label(W / 2, 24, '↑ 脸（前）'))
    g.append(label(16, Hh - 14, '← 机器人左侧', 'start'))
    g.append(label(W - 16, Hh - 14, '机器人右侧 →', 'end'))
    return svg(im, W, Hh, ''.join(g), '从上往下看下颌座和三个舵机')


def side_view(S, sign, nums, title):
    W, Hh = 640, 420
    im, proj, _ = render([(S.tris(JAW), C_JAW, JAW)], (-sign, 0, 0), W=W, H=Hh, fit=S.pts(JAW))
    g = [mark(*proj(np.array(H[n][0])), n) for n in nums]
    g.append(label(W / 2, 22, title))
    return svg(im, W, Hh, ''.join(g), title)


def html(S):
    return ('<h4>下颌座的 6 个 M2 孔从哪头压</h4>'
            '<p>这 6 个孔都是<b>通孔</b>，两头一样大，所以看孔本身分不出方向。判断方法：<b>舵机的安装耳贴在哪个面，就从哪个面压</b>。'
            '压反了螺丝够不着：M2×6 穿过安装耳后，只能伸进孔口约 3 mm。红箭头 = 压螺母和拧螺丝的方向。</p>'
            f'<div class="fig3d">{top_view(S)}</div>'
            f'<div class="fig3d">{side_view(S, 1, (1, 2), "从机器人左侧看：压 1、2")}</div>'
            f'<div class="fig3d">{side_view(S, -1, (3, 4, 5, 6), "从机器人右侧看：压 3、4（外面）和 5、6（里面）")}</div>'
            '<table class="sc"><thead><tr><th>编号</th><th>属于</th><th>压哪一面</th></tr></thead><tbody>'
            '<tr><td><b>1、2</b></td><td>机器人左侧的舵机</td><td>下颌座左侧外表面，往中线压</td></tr>'
            '<tr><td><b>3、4</b></td><td>机器人右侧的舵机</td><td>下颌座右侧外表面，往中线压</td></tr>'
            '<tr><td><b>5、6</b></td><td>中间的舵机（竖着放，安装耳一上一下）</td><td>下颌座中间那块竖板<b>朝机器人右侧</b>的一面，也是从右往左压</td></tr>'
            '</tbody></table>'
            '<p>中间这个舵机大概率是舌头舵机。<b>不装舌头就不用压 5、6。</b>要装的话，6 号最难：孔口外 17 mm 就是下颌座侧壁，烙铁伸不直，只能斜着进，压之前先试一下够不够得着。</p>')
