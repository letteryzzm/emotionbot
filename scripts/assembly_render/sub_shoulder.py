"""生成「台阶螺丝替代方案」小节（剖面示意 SVG + 测试步骤），插到 组装流程.html 的 <!--SUB-BEGIN--> <!--SUB-END--> 之间。"""
import os, re

NOTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../docs/组装流程.html')
s = 13.0          # px / mm
Y0 = 80.0         # 螺丝头顶


def y(t):
    return Y0 + t * s


def rect(x0, t0, x1, t1, cls):
    return f'<rect x="{min(x0, x1):.1f}" y="{y(t0):.1f}" width="{abs(x1 - x0):.1f}" height="{(t1 - t0) * s:.1f}" class="{cls}"/>'


def poly(pts, cls):
    return '<polygon points="' + ' '.join(f'{x:.1f},{y(t):.1f}' for x, t in pts) + f'" class="{cls}"/>'


def text(x, t, txt, cls='an', anchor='start'):
    return f'<text x="{x:.1f}" y="{y(t):.1f}" class="{cls}" text-anchor="{anchor}">{txt}</text>'


def lead(x0, t0, x1, t1):
    return f'<path d="M{x0:.1f},{y(t0):.1f}L{x1:.1f},{y(t1):.1f}" class="ld"/>'


def parts(cx):
    """转动连杆 t 3–6.8（孔 Ø4.3），嘴唇零件 t 7–11（孔 Ø3.6，背面六角槽 Ø6.4 深 2.6），槽里一颗 M3 螺母"""
    g = []
    W = 92
    for sg in (-1, 1):
        g.append(rect(cx + sg * 2.15 * s, 3, cx + sg * (2.15 * s + W), 6.8, 'lk'))
        g.append(poly([(cx + sg * (2.15 * s + W + 14), 7), (cx + sg * 1.8 * s, 7), (cx + sg * 1.8 * s, 8.4),
                       (cx + sg * 3.2 * s, 8.4), (cx + sg * 3.2 * s, 11), (cx + sg * (2.15 * s + W + 14), 11)], 'lp'))
        g.append(rect(cx + sg * 1.5 * s, 8.6, cx + sg * 2.75 * s, 11, 'nt'))
    return g


def thread(cx, r, t0, t1):
    g = [rect(cx - r * s, t0, cx + r * s, t1, 'sc')]
    t = t0 + 0.25
    while t < t1 - 0.1:
        g.append(f'<path d="M{cx - r * s:.1f},{y(t):.1f}L{cx + r * s:.1f},{y(t + 0.35):.1f}" class="th"/>')
        t += 0.5
    return g


def panel(cx, kind):
    g = parts(cx)
    if kind == 'A':
        g += [rect(cx - 3 * s, 0, cx + 3 * s, 3, 'sc'), rect(cx - 2 * s, 3, cx + 2 * s, 7, 'sc sh')] + thread(cx, 1.5, 7, 11)
    elif kind == 'B':
        g += [rect(cx - 2.75 * s, 0, cx + 2.75 * s, 3, 'sc')] + thread(cx, 1.5, 3, 11)
        for sg in (-1, 1):  # 间隙高亮
            g.append(rect(cx + sg * 1.5 * s, 3, cx + sg * 2.15 * s, 6.8, 'gap'))
        for sg in (-1, 1):  # 夹紧箭头
            x = cx + sg * 2.4 * s
            g.append(f'<path d="M{x:.1f},{y(-2.0):.1f}L{x:.1f},{y(-0.2):.1f}" class="pr" marker-end="url(#ar)"/>')
    else:
        g += [rect(cx - 2.75 * s, 0, cx + 2.75 * s, 3, 'sc')] + thread(cx, 1.5, 3, 11)
        for sg in (-1, 1):
            g.append(rect(cx + sg * 1.5 * s, 3, cx + sg * 2.0 * s, 7, 'tb'))
    return g


def svg():
    g = ['<defs><marker id="ar" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="7" markerHeight="7" orient="auto">'
         '<path d="M0,0L10,5L0,10z" class="arh"/></marker></defs>']
    cols = [(165, 'A', 'A · 原版：M3 台阶螺丝', '✓ 不晃 · 拧紧也能转'),
            (495, 'B', 'B · 临时：M3×8 + M3 螺母', '会晃 · 只能拧到刚好能转'),
            (825, 'C', 'C · 改良：M3×8 + 黄铜套管', '≈ 原版，不用买台阶螺丝')]
    for cx, k, title, sub in cols:
        g.append(text(cx, -4.4, title, 'ttl', 'middle'))
        g.append(text(cx, -3.1, sub, 'sub ' + ('ok' if k != 'B' else 'bad'), 'middle'))
        g += panel(cx, k)
    # A 的标注
    cx = 165
    g += [lead(cx + 2 * s, 5, cx + 128, 4.2), text(cx + 132, 4.4, '轴肩 Ø4 光杆'),
          text(cx + 132, 5.5, '连杆绕它转', 'an2'),
          lead(cx - 2 * s - 2, 6.9, cx - 130, 13.0), text(cx - 150, 13.9, '轴肩比连杆长 0.2，', 'an2'),
          text(cx - 150, 15.0, '顶在嘴唇上 → 拧紧也不夹连杆', 'an2'),
          lead(cx + 2.4 * s, 9.8, cx + 120, 13.0), text(cx + 70, 13.9, 'M3 螺母（嵌在', 'an2'),
          text(cx + 70, 15.0, '嘴唇背面六角槽）', 'an2')]
    cx = 495
    g += [lead(cx - 1.85 * s, 5, cx - 128, 13.0), text(cx - 150, 13.9, 'Ø3 螺杆在 Ø4.3 孔里', 'an2 bad'),
          text(cx - 150, 15.0, '单边约 0.65 mm 旷量', 'an2 bad'),
          text(cx + 2.6 * s + 8, -0.9, '拧紧 = 夹死连杆', 'an2 bad'),
          lead(cx + 2.4 * s, 9.8, cx + 120, 13.0), text(cx + 70, 13.9, '螺丝伸出长度', 'an2'),
          text(cx + 70, 15.0, '= 原版（8 mm）', 'an2')]
    cx = 825
    g += [lead(cx + 1.75 * s, 5, cx + 120, 13.0), text(984, 13.9, '黄铜管 外Ø4 内Ø3', 'an2', 'end'),
          text(984, 15.0, '长 4.0（= 轴肩长）', 'an2', 'end'),
          lead(cx - 1.75 * s, 6.95, cx - 130, 13.0), text(cx - 150, 13.9, '管子顶在嘴唇上 =', 'an2'),
          text(cx - 150, 15.0, '代替轴肩，连杆绕管子转', 'an2')]
    # 图例
    lg = [('lk', '转动的连杆（孔 Ø4.3）'), ('lp', '嘴唇 / 后一个零件'), ('nt', 'M3 螺母'), ('sc', '螺丝'), ('tb', '黄铜套管'), ('gap', '旷量')]
    x = 60
    for c, t in lg:
        g.append(f'<rect x="{x}" y="{y(16.6):.1f}" width="14" height="14" class="{c}"/><text x="{x + 20}" y="{y(16.6) + 12:.1f}" class="an2">{t}</text>')
        x += 150
    return (f'<svg viewBox="0 0 990 {y(18.4):.0f}" xmlns="http://www.w3.org/2000/svg" role="img" '
            f'aria-label="M3 台阶螺丝和两种替代做法的剖面对比">' + ''.join(g) + '</svg>')


CSS = """
/*SUBSH*/
.xsec svg{width:100%;height:auto;display:block}
.xsec{overflow-x:auto}.xsec svg{min-width:640px}
.xsec .lk{fill:color-mix(in srgb,var(--elec) 45%,var(--card));stroke:var(--elec);stroke-width:1.5}
.xsec .lp{fill:color-mix(in srgb,var(--mech) 40%,var(--card));stroke:var(--mech);stroke-width:1.5}
.xsec .nt{fill:#9a9aa0;stroke:#55555a;stroke-width:1.2}
.xsec .sc{fill:#3d4048;stroke:#1d1f24;stroke-width:1.2}.xsec .sh{fill:#5b606b}
.xsec .th{stroke:#9aa0aa;stroke-width:1}
.xsec .tb{fill:#d9a634;stroke:#7a5a10;stroke-width:1.2}
.xsec .gap{fill:color-mix(in srgb,var(--warn) 55%,transparent);stroke:var(--warn);stroke-width:1}
.xsec .pr{stroke:var(--warn);stroke-width:2.5}.xsec .arh{fill:var(--warn)}
.xsec .ld{fill:none;stroke:var(--muted);stroke-width:1}
.xsec text{fill:var(--fg);font-family:-apple-system,"PingFang SC",sans-serif}
.xsec .ttl{font-size:16px;font-weight:800}.xsec .sub{font-size:13px;font-weight:700}
.xsec .ok{fill:var(--elec)}.xsec .bad{fill:var(--warn)}
.xsec .an{font-size:13.5px;font-weight:700}.xsec .an2{font-size:12.5px}
"""

BODY = f"""<!--SUB-BEGIN-->
<section class="stp" id="sub-shoulder" style="border-left-color:var(--gate)">
<h3>台阶螺丝怎么用普通螺丝代替（图 9、图 10 的替代做法）</h3>
<p>台阶螺丝头下面有一段<b>光滑的轴肩</b>，连杆就套在轴肩上转。轴肩比连杆略长，拧紧时轴肩顶住后面的零件，所以<b>拧紧也不会夹死连杆</b>。普通螺丝没有这一段，要么晃、要么夹死，下面三种做法对比：</p>
<div class="xsec">{svg()}</div>
<p class="muted">剖面示意，按 M3 台阶螺丝的真实尺寸画（1 mm ≈ 13 px）：头 Ø6×3，轴肩 Ø4×4，螺纹 M3×4；连杆孔 Ø4.3，嘴唇孔 Ø3.6，背面六角槽深约 2.6 mm。</p>

<h3>尺寸对照</h3>
<table>
<thead><tr><th>位置</th><th>原版</th><th>B 临时替代</th><th>C 改良（加套管）</th></tr></thead>
<tbody>
<tr><td>嘴唇、嘴角转轴 ×14（图 9）</td><td>M3 台阶螺丝：轴肩 Ø4×4 + 螺纹 4</td><td><b>M3×8</b> + M3 螺母</td><td><b>M3×8</b> + M3 螺母 + 黄铜管 <b>外 Ø4 / 内 Ø3，长 4.0</b></td></tr>
<tr><td>上唇、下唇大转轴 ×4（图 10）</td><td>M4 台阶螺丝：轴肩 Ø5×5 + 螺纹 4.5</td><td><b>M4×10</b>，拧进 M4 热熔螺母</td><td><b>M4×10</b> + 黄铜管 <b>外 Ø5 / 内 Ø4，长 5.0</b></td></tr>
</tbody>
</table>
<p class="muted">怎么算的：普通螺丝长度 = 轴肩长 + 螺纹长（M3：4 + 4 = 8；M4：5 + 4.5 ≈ 10），这样螺丝尖停的位置和原版一样。套管长度 = 原版轴肩长度。黄铜管淘宝搜"黄铜管 外径4 壁厚0.5"（内径正好 3）、"外径5 壁厚0.5"（内径 4），用割管器或小锯切，再用锉刀锉到长度，卡尺量准到 ±0.1 mm。套管外径不能超过孔径（Ø4.3 / Ø5.3）减 0.1。</p>

<h3>B 的装法和测试（先挑一个嘴唇连杆试）</h3>
<div class="step"><input type="checkbox" data-k="sub1"><div><b>1. 放螺母</b>：M3 螺母压进嘴唇零件<b>背面</b>的六角槽，压平。太紧就用螺丝从正面拧一下把它拉进去。</div></div>
<div class="step"><input type="checkbox" data-k="sub2"><div><b>2. 穿螺丝</b>：M3×8 先穿过<b>转动的连杆</b>（Ø4.3 孔），再穿嘴唇零件，拧进螺母。</div></div>
<div class="step"><input type="checkbox" data-k="sub3"><div><b>3. 边拧边转</b>：一边拧一边用手拨连杆，拧到连杆<b>开始有点涩</b>就往回退 1/4 圈。</div></div>
<div class="step"><input type="checkbox" data-k="sub4"><div><b>4. 测转动</b>：手拨连杆，整个行程都能自由转，没有卡顿。</div></div>
<div class="step"><input type="checkbox" data-k="sub5"><div><b>5. 测旷量</b>：捏住连杆前后、左右晃，目测几乎不晃（&lt; 0.5 mm）。B 做法一定会有一点晃，晃得明显就改用 C。</div></div>
<div class="step"><input type="checkbox" data-k="sub6"><div><b>6. 测会不会松</b>：接上舵机来回扫 20 次（或者手转 20 次），再看螺丝有没有退出来。会松：在螺母那一侧点一小滴螺纹胶（蓝色中强度），<b>不要滴到连杆和螺杆之间</b>，否则关节会被粘死。</div></div>
<div class="step"><input type="checkbox" data-k="sub7"><div><b>7. 查长度</b>：螺丝尖不能从背面伸出来顶到别的零件或连杆的运动范围；也不能还没碰到连杆就拧不动（说明拧到孔底了）。出问题就换长一号或短一号。</div></div>
<div class="step"><input type="checkbox" data-k="sub8"><div><b>8. M4 下颌位置</b>：M4×10 拧进 M4 热熔螺母，同样拧到能转就停，重点看张嘴、闭嘴时下巴<b>上下晃有没有超过 1 mm</b>。超过就用 C（加 Ø5/Ø4 套管）或者买 M4 台阶螺丝。</div></div>
<p class="muted">C 做法的装法：套管先套在螺丝上，再一起穿过连杆；这时可以正常拧紧，螺丝头压的是套管，不是连杆。拧紧后连杆还能自由转、几乎不晃，就说明套管长度对了；转不动 = 套管短了，晃 = 套管太长。</p>
</section>
<!--SUB-END-->"""

if __name__ == '__main__':
    h = open(NOTE).read()
    if '/*SUBSH*/' not in h:
        h = h.replace('</style>', CSS + '</style>', 1)
    if '<!--SUB-BEGIN-->' in h:
        h = re.sub(r'<!--SUB-BEGIN-->.*?<!--SUB-END-->', lambda m: BODY, h, flags=re.S)
    else:
        h = h.replace('<!--STEPS-END-->', '<!--STEPS-END-->\n' + BODY, 1)
    open(NOTE, 'w').write(h)
    print('ok')
