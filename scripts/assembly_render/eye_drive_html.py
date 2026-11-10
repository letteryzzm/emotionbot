"""生成 docs/眼部传动与组装.html：眼球传动结构 + 组装流程，图片内嵌。
.venv/bin/python scripts/assembly_render/eye_drive_html.py
"""
import base64, io, os, sys
import numpy as np
from PIL import Image, ImageDraw, ImageFont
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
from render import Scene, render
import final_fig
import matplotlib; matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.collections import LineCollection

ROOT = os.path.dirname(os.path.dirname(HERE))
S = Scene(os.path.join(ROOT, 'outputs/assembly/mesh.npz'))
FONT = '/System/Library/Fonts/Hiragino Sans GB.ttc'
GRAY, DARK, WHITE = (.82, .83, .85), (.30, .32, .37), (.97, .97, .96)
OR, BL, GR, PU = (.96, .55, .16), (.26, .58, .92), (.35, .72, .50), (.66, .48, .86)


def part_a():
    """X 轴件 A 的正确姿态：绕 x 转 180°，平面朝上、销柱朝下。平面和舵机耳朵顶面 z=1.5 齐平"""
    T = final_fig.stl('plate7_Eyes/EyeCorePivotHolder_v2*')
    T = T - T.reshape(-1, 3).min(0)
    return ((T - np.array([43.5, 0, 0])) * np.array([1, -1, -1]) + np.array([0, -45.72, 1.5]))[:, ::-1]


A, B = part_a(), final_fig.lateral_frame()
RA = final_fig.right_adaptors(S)


def png(im):
    b = io.BytesIO(); im.save(b, 'PNG', optimize=True)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


def shot(items, view, notes, W=1100, H=640):
    img, proj = render([(t, c, i) for i, (t, c) in enumerate(items)], view, W=W, H=H)[:2]
    bg = Image.new('RGBA', img.size, 'white'); bg.alpha_composite(img.convert('RGBA'))
    k = img.size[0] / W
    d = ImageDraw.Draw(bg); f = ImageFont.truetype(FONT, int(24 * k))
    for pt, txt, dx, dy in notes:
        p = proj(np.array(pt, float)); x, y = float(p[0]), float(p[1])
        if max(x, y) > max(W, H) * 1.2:      # proj 可能是超采样坐标
            x, y = x / 2, y / 2
        x, y = x * k, y * k; tx, ty = x + dx * k, y + dy * k
        w = d.textlength(txt, font=f)
        d.line([x, y, tx, ty], fill=(40, 45, 55), width=max(2, int(2 * k))); d.ellipse([x - 5 * k, y - 5 * k, x + 5 * k, y + 5 * k], fill=(40, 45, 55))
        bx = tx - w / 2
        d.rectangle([bx - 8 * k, ty - 18 * k, bx + w + 8 * k, ty + 18 * k], fill=(255, 255, 255, 235), outline=(150, 155, 165))
        d.text((bx, ty - 14 * k), txt, fill=(25, 30, 40), font=f)
    return png(bg.convert('RGB'))


def fig_lr():
    it = [(S.tris(46), WHITE), (S.tris(53), WHITE), (S.tris(35), DARK), (S.tris(39), GRAY), (S.tris(33), GRAY), (S.tris(49), GRAY), (A, GR),
          (S.tris(41), GR), (RA[1], GR), (S.tris(62), OR), (RA[0], OR), (B, OR), (S.tris(54), OR)]
    return shot(it, (.12, -.62, -.78), [((0, -68.6, 14), 'LR 舵机轴', 170, -70), ((0, -53.8, 13), '舵盘后端卡柱', -10, 150), ((-30, -48.5, 8), 'LateralFrame', 130, 170),
                                        ((37.5, -53.7, 9.5), 'EyeAdaptor 尾柱', -30, 215)])


def fig_ud():
    it = [(S.tris(46), WHITE), (S.tris(62) * np.array([-1, 1, 1]), OR), (RA[1], GR), (S.tris(35), DARK), (A, GR), (S.tris(39), BL), (S.tris(56), BL), (S.tris(47), BL), (S.tris(61), DARK), (S.tris(49), GRAY), (S.tris(44), (.90, .90, .91))]
    return shot(it, (1, .0, -.08), [((-12, -68.7, 17), '力臂卡柱', 40, -110), ((-12, -46, 34), 'VerticalLever', -150, -30), ((-12, -23.4, 8), 'VerticalHorn', -150, -60),
                                    ((-12, -23.4, -8), 'UD 舵机', -170, 30), ((-15, -68.7, 0), '上下转轴', -130, 170)], H=620)


def sec(T, val):
    a = T[(T[:, :, 1].min(1) < val) & (T[:, :, 1].max(1) > val)]; R = []
    for t in a:
        P = []
        for i in range(3):
            p, q = t[i], t[(i + 1) % 3]
            if (p[1] - val) * (q[1] - val) < 0:
                P.append((p + (q - p) * (val - p[1]) / (q[1] - p[1]))[[0, 2]])
        if len(P) == 2:
            R.append(P)
    return np.array(R)


def fig_stack():
    from matplotlib import font_manager as fm
    fp = fm.FontProperties(fname=FONT, size=12)
    fig, ax = plt.subplots(figsize=(9.2, 5.2), dpi=130)
    for t, c, w in ((S.tris(53), '#555', 1.2), (A, '#2f9e63', 2.2), (S.tris(41), '#2f9e63', 1.4), (S.tris(62), '#ee8a1f', 2)):
        g = sec(t, -68.7); g = g[g[:, :, 0].max(1) < -18]       # 只留左眼这一段
        ax.add_collection(LineCollection(g, colors=c, linewidths=w))
    ax.axvline(-37.5, color='#d33', ls='--', lw=1.1)
    for xy, txt, tx in (((-37.5, 5.5), '上 EyeAdaptor（孔空着）', (-14, 11)), ((-34, 0), 'A 的端环（在两片之间）', (-14, 4)), ((-33.5, -5.5), '下 EyeAdaptor_v2（套在 A 的销柱上）', (-14, -3.5)),
                        ((-35.5, -9.2), 'A 销柱尖端朝下', (-14, -11)), ((-47, 12), '眼球', (-60, 15))):
        ax.annotate(txt, xy=xy, xytext=tx, fontproperties=fp, arrowprops=dict(arrowstyle='-', color='#333', lw=.8))
    ax.text(-36.6, 13, '左右转轴', color='#d33', fontproperties=fp)
    ax.set_xlim(-66, 26); ax.set_ylim(-18, 18); ax.set_aspect(1); ax.axis('off')
    b = io.BytesIO(); fig.savefig(b, format='png', bbox_inches='tight'); plt.close(fig)
    return 'data:image/png;base64,' + base64.b64encode(b.getvalue()).decode()


HTML = '''<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>眼部传动与组装</title><style>
:root{--ink:#1f2530;--mute:#5f6a7a;--line:#dfe3e8;--bg:#fff;--soft:#f5f7f9;--acc:#c75b12}
@media (prefers-color-scheme:dark){:root{--ink:#e7ebf0;--mute:#a0abb9;--line:#333b47;--bg:#14181f;--soft:#1d232c;--acc:#f09a50}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.7 -apple-system,"PingFang SC",sans-serif}
main{max-width:860px;margin:auto;padding:28px 16px 60px}h1{font-size:28px;margin:0 0 6px}h2{font-size:21px;margin:36px 0 10px;padding-bottom:6px;border-bottom:1px solid var(--line)}h3{font-size:17px;margin:22px 0 6px}
p{margin:8px 0}.mute{color:var(--mute);font-size:14px}figure{margin:14px 0}figure img{width:100%;display:block;border:1px solid var(--line);border-radius:8px;background:#fff}figcaption{color:var(--mute);font-size:14px;margin-top:5px}
ol{padding-left:24px}li{margin:7px 0}table{width:100%;border-collapse:collapse;font-size:15px;margin:10px 0}th,td{border:1px solid var(--line);padding:7px 9px;text-align:left;vertical-align:top}th{background:var(--soft)}td:first-child{white-space:nowrap}
.chain{background:var(--soft);border-radius:8px;padding:10px 14px;font-weight:600}.key{border-left:3px solid var(--acc);padding:4px 0 4px 12px;margin:12px 0}code{font-size:.92em}
</style></head><body><main>
<h1>眼部传动与组装</h1>
<p class="mute">方向约定：“前”是眼睛朝向，“左/右”是面对机器人时的左右手。依据官方 EyeMech ε3.2 说明书、官方 3mf 和 STL 实测；标“推断”的地方来自几何分析，还没有在实物上验证。</p>

<h2>1. 眼球怎么动</h2>
<p>两只眼球靠两根横梁连成一组，只用 2 个舵机：LR 管左右，UD 管上下。LR 舵机本身也跟着整组一起上下摆。</p>
<div class="key">先记住这个结构：每只眼球背面卡着上下两片 EyeAdaptor。下片套在 X 轴件 A 的销柱上，这是眼球的左右转轴。上片带尾柱，接 LateralFrame，负责把力传给眼球。</div>
<figure><img src="@@STACK@@" alt="眼球转轴截面"><figcaption>图 1：穿过眼球转轴的截面。A 的销柱朝下穿过下片；上片的 Ø7 孔不套销柱，靠眼球定位（推断）。</figcaption></figure>

<h3>左右传动（LR）</h3>
<p class="chain">LR 舵机 → CentralServoHorn → LateralFrame → 两片上 EyeAdaptor 的尾柱 → 两只眼球</p>
<p>舵盘臂和 EyeAdaptor 的尾部臂都约 15 mm，三个环的中心距是 37.5 mm，和两只眼的转轴间距一致，组成平行四边形。舵盘一转，LateralFrame 横向平移，两只眼转过相同的角度。</p>
<figure><img src="@@LR@@" alt="左右传动"><figcaption>图 2：从后上方看。橙色是左右传动件，绿色是 X 轴件 A 和下 EyeAdaptor_v2。</figcaption></figure>

<h3>上下传动（UD）</h3>
<p class="chain">UD 舵机 → VerticalHorn → VerticalLever → Y 轴支架 → 整个眼球核心</p>
<p>Y 轴支架 <code>EyeCorePivotHolder</code> 左右两根销轴插在两个 Base_v2 的环里，这是上下转轴。支架上有一根力臂，卡柱在转轴上方 17 mm；UD 舵盘臂也是 17 mm。连杆一拉，Y 轴支架连同 LR 舵机、A、LateralFrame 和两只眼球一起上下摆。</p>
<figure><img src="@@UD@@" alt="上下传动"><figcaption>图 3：从左侧看，已隐去左眼。蓝色是上下传动件。</figcaption></figure>

<h2>2. 先组 3 个子组件</h2>
<table><tr><th>子组件</th><th>零件</th><th>怎么组</th></tr>
<tr><td>X 轴 A</td><td><code>EyeCorePivotHolder_v2</code> + 2×<code>EyeAdaptor_v2</code></td><td>两片压到 A 两端销柱上，V 形尖朝前，要能自由转</td></tr>
<tr><td>X 轴 B</td><td><code>LateralFrame</code> + <code>CentralServoHorn</code> + 2×<code>EyeAdaptor</code></td><td>有小圆点的一面朝上；两端环套 EyeAdaptor 尾柱，中环套舵盘卡柱</td></tr>
<tr><td>Y 轴</td><td><code>EyeCorePivotHolder</code> + <code>VerticalLever</code> + <code>VerticalHorn</code></td><td>连杆前环套到力臂卡柱上，舵盘卡柱穿进连杆后环，不拧螺丝</td></tr></table>

<h2>3. 组装流程</h2>
<ol>
<li><b>装 LR 舵机。</b>A <b>平面朝上、销柱朝下</b>。舵机放进方框，输出轴朝上并靠前，线从缺口出去，耳朵落在 A 的上平面位置。</li>
<li><b>扣 Y 轴。</b>Y 轴支架从舵机上方扣下，卡钩钩住 A 的方框，把舵机夹住。力臂在左侧。</li>
<li><b>装中心枢轴座。</b>两个 <code>Base_v2</code> 的环分别套上 Y 轴左右销轴，有一点阻力，装好后要转动顺滑。</li>
<li><b>松装 X 轴 B。</b>整组放到 LR 舵机轴上，先不拧舵盘螺丝，校准时还要提起来。</li>
<li><b>卡进底板。</b>两个 <code>Base_v2</code> 从底板 <code>SnapEyemech_v20</code> 下面往上卡。</li>
<li><b>压眼球。</b>每只眼球从前面压到上下两片 EyeAdaptor 的 V 形翼上，卡进背面凹槽。轻轻左右拨，两只眼应该一起动。</li>
<li><b>装眼皮。</b>连杆先从外侧套到眼皮卡柱上（上眼皮 <code>LidBR</code> 配短杆，下眼皮 <code>LidTR</code> / <code>LidTR_v2</code> 配长杆）。上下眼皮对齐后一起插进中心枢轴，可以掰一下机构，或把眼球转到一侧。内侧顺序：Base_v2 → 下眼皮耳 → 上眼皮耳。</li>
<li><b>装外侧枢轴。</b>两个 <code>Base</code> 从底板下面卡上，Ø6 销穿过两片眼皮的外耳。外侧顺序：上眼皮耳 → 下眼皮耳 → Base 板。</li>
<li><b>放 5 个舵机并扣压扣。</b>TL、TR 竖放，轴朝外、在上端，机身向下穿过底板；BL、BR 平躺，长边前后方向，轴在后端；UD 竖放，轴朝左。两个 <code>SnapEyemech_v20_v2</code> 各压一侧的眼皮舵机，<code>SnapEyemech_v20_v3</code> 压 UD。</li>
<li><b>通电回中，逐个校准。</b>运行 <code>.venv/bin/python scripts/servo_check.py --center</code>，全部转到 90° 后按下表装舵盘。</li>
<li><b>检查。</b>断电后轻推全行程，确认没有卡点，再用 M3×8 把底板装到头骨框架上。</li>
</ol>

<h2>4. 校准（舵机在 90°）</h2>
<table><tr><th>舵机</th><th>操作</th><th>应有状态</th></tr>
<tr><td>LR</td><td>提起 CentralServoHorn，不用拆 LateralFrame。眼球摆正，压回花键，拧螺丝</td><td>舵盘臂朝正后，两眼朝前</td></tr>
<tr><td>UD</td><td>取下压扣拿出舵机，把轴压进 VerticalHorn，拧螺丝后放回。记住原来的位置和朝向</td><td>舵盘臂朝正上，两眼朝前</td></tr>
<tr><td>TL / BL / TR / BR</td><td>眼皮合到中间，舵盘从外侧同时压进连杆后环和舵机轴，再拧螺丝</td><td>舵盘臂向眼球倾斜约 20°，上下眼皮闭合</td></tr></table>
<p class="mute">差一个齿时，拔下舵盘换齿位，不要掰连杆。还差一点再改 <code>firmware/config_eyes.py</code> 的范围。</p>

<h2>5. 容易装错的地方</h2>
<table><tr><th>现象</th><th>原因</th><th>处理</th></tr>
<tr><td>眼球压不到底</td><td>A 上下装反，端环顶到眼球壳壁</td><td>翻成平面朝上、销柱朝下</td></tr>
<tr><td>两只眼不一起转</td><td>上片 EyeAdaptor 没接 LateralFrame，或漏装</td><td>每只眼要上下 2 片，共 4 片</td></tr>
<tr><td>UD 连杆套不上</td><td>舵机固定后才接连杆，两头都要轴向套（推断）</td><td>先在 Y 轴子组件里接好</td></tr>
<tr><td>眼皮连杆套不上舵盘</td><td>舵盘先压上了轴，卡柱朝向舵机（推断）</td><td>先装连杆，舵盘最后从外侧压</td></tr>
<tr><td>一侧上眼皮或外侧 Base 对不上</td><td>STL 导出时丢了镜像，打成两个同手性的件</td><td>两件面对面应能镜像对合；不能的话用原版 3mf 重打</td></tr></table>
<p class="mute">官方说明书：<code>upstream/EyeMech_3.2_download/EyeMech ε3.2/EYEMECH ε3.2 Assembly Document.pdf</code>，CC BY-NC-SA 4.0。官方视频：<a href="https://youtu.be/MeHLouL9ltw">youtu.be/MeHLouL9ltw</a></p>
</main></body></html>'''
out = HTML.replace('@@STACK@@', fig_stack()).replace('@@LR@@', fig_lr()).replace('@@UD@@', fig_ud())
p = os.path.join(ROOT, 'docs/眼部传动与组装.html')
open(p, 'w', encoding='utf8').write(out); print(p, len(out))
