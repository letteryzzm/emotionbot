"""生成「螺丝装配图解」HTML 片段：每一步一张爆炸图（PNG 实体渲染 + SVG 标注）。

.venv/bin/python scripts/assembly_render/build_steps.py
输出：outputs/assembly/steps_fragment.html，然后由 inject.py 插到笔记里的 组装流程.html
"""
import base64, html, io, os, sys
import numpy as np
from PIL import Image

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from render import Scene, render  # noqa: E402
import jaw_m2_fig  # noqa: E402
import ins_other_fig  # noqa: E402
import servo_shaft_fig  # noqa: E402
import lip_link_fig  # noqa: E402
import link_id_fig  # noqa: E402
import s3_chain_fig  # noqa: E402
import brow_fig  # noqa: E402
import final_fig  # noqa: E402
import json, re  # noqa: E402

ROOT = os.path.dirname(os.path.dirname(HERE))
S = Scene(os.path.join(ROOT, 'outputs/assembly/mesh.npz'))
OUT = os.path.join(ROOT, 'outputs/assembly')

# ---------- 颜色 ----------
C_RECV = (0.60, 0.74, 0.92)   # 螺丝拧进去的零件（有热熔螺母）
C_CLAMP = (0.62, 0.85, 0.62)  # 被压住的零件
C_SERVO = (0.33, 0.35, 0.40)
C_MG996 = (0.30, 0.38, 0.52)
C_CTX = (0.88, 0.88, 0.86)
C_BRASS = (0.85, 0.66, 0.25)
SCREW_C = {'M2': (0.96, 0.55, 0.12), 'M2.5': (0.62, 0.38, 0.85), 'M3': (0.86, 0.22, 0.22),
           'M4': (0.62, 0.10, 0.18), 'S3': (0.10, 0.62, 0.45), 'S4': (0.05, 0.45, 0.55)}
HEX = {'M2': 1.5, 'M2.5': 2, 'M3': 2.5, 'M4': 3, 'S3': 2, 'S4': 2.5}  # 内六角扳手 mm

# ---------- 零件中文名（STL 文件名就是括号里的英文名） ----------
CN = {
    'SkullFrame': '头骨框架 SkullFrame（plate 3）', 'TopBase': '上颌座 TopBase（plate 2）', 'JawBase': '下颌座 JawBase（plate 2）',
    'CheekBone': '颧骨 CheekBone（plate 6）', 'SnapEyemech v20': '眼部机构底板 SnapEyemech（plate 7）',
    'JawLink': '右下颌连杆 JawLink', 'Part 33': '左下颌连杆 Part_33', 'Component2': 'MG996R', 'Component1': 'MG996R 圆舵盘',
    'MG90s_servo_FIX v1(Mirror)': 'MG90S', 'MG996R v6': 'MG996R 输出轴',
}


def cn(gi):
    n = S.names[gi]
    return CN.get(n, n.replace('Part ', 'Part_') + '（plate 2）' if n.startswith('Part ') or 'Lip' in n or 'ULLLink' in n else n)


def spec_of(gi):
    n = S.names[gi]
    if 'M3 Shoulder' in n:
        return 'S3'
    if 'M4 Shoulder' in n:
        return 'S4'
    import re
    m = re.search(r'(M[\d.]+)x0\.\d+ x (\d+)', n)
    return m.group(1)


def spec_label(gi):
    n = S.names[gi]
    if 'M3 Shoulder' in n:
        return 'M3 台阶螺丝'
    if 'M4 Shoulder' in n:
        return 'M4 台阶螺丝'
    import re
    m = re.search(r'(M[\d.]+)x0\.\d+ x (\d+)', n)
    return f'{m.group(1)}×{m.group(2)}'


def entry(screw, part):
    """螺丝轴线进入 part 的位置（孔口）和孔径"""
    h, t, a, _ = S.screw_axis(screw)
    P = S.pts(part); q = P - h; tp = q @ a
    rr = np.linalg.norm(q - np.outer(tp, a), axis=1)
    m = (rr < 3.6) & (tp > -1) & (tp < np.linalg.norm(t - h) + 1)
    if not m.any():
        return None, None
    rmin = rr[m].min()
    mm = m & (rr < rmin + 0.15)
    return h + a * tp[mm].min(), 2 * rmin


def img_b64(im):
    im = im.convert('RGBA')
    q = im.quantize(colors=96, method=Image.FASTOCTREE, dither=Image.NONE)
    buf = io.BytesIO(); q.save(buf, 'PNG', optimize=True)
    return base64.b64encode(buf.getvalue()).decode()


def auto_dir(screws, tilt=(0.55, 0.8), extra=None):
    a = np.mean([S.screw_axis(s)[2] for s in screws], 0); a /= np.linalg.norm(a)
    perp = np.cross(a, [0, 0, 1.0])
    if np.linalg.norm(perp) < 0.2:
        perp = np.cross(a, [1.0, 0, 0])
    perp /= np.linalg.norm(perp)
    d = tilt[0] * a + tilt[1] * perp
    if extra is not None:
        d = d + np.asarray(extra, float)
    return d


def figure(step):
    E = step.get('explode', 14)
    items, parts_only, screw_items = [], [], []
    fit = []
    for g, col in step['parts']:
        T = S.tris(g); items.append((T, col, g)); fit.append(S.pts(g))
    for g in step.get('context', []):
        items.append((S.tris(g), C_CTX, g))
    for i, (T, col) in enumerate(step.get('extra', [])):
        items.append((T, col, 900 + i)); fit.append(T.reshape(-1, 3))
    labels = []
    for s in step['screws']:
        h, t, a, hr = S.screw_axis(s)
        sp = spec_of(s)
        T = S.tris(s, -a * E)
        items.append((T, SCREW_C[sp], s)); screw_items.append((T, SCREW_C[sp], s))
        fit.append(np.array([h - a * (E + 2), t]))
        labels.append((s, sp, h, t, a))
    d = step.get('dir') or auto_dir(step['screws'], extra=step.get('dir_extra'))
    W, H = step.get('size', (1000, 720))
    fitp = np.concatenate(fit)
    im, proj, _ = render(items, d, W=W, H=H, fit=fitp, up=step.get('up', (0, 0, 1)))
    # 被挡住的螺丝：单独渲一遍，半透明叠上去
    if screw_items:
        im_s, _, _ = render(screw_items, d, W=W, H=H, fit=fitp, up=step.get('up', (0, 0, 1)))
        A = np.asarray(im).astype(float); B = np.asarray(im_s).astype(float)
        occl = (B[..., 3] > 128) & (np.abs(A[..., :3] - B[..., :3]).sum(-1) > 40)
        A[occl, :3] = A[occl, :3] * 0.45 + B[occl, :3] * 0.55
        im = Image.fromarray(A.astype(np.uint8), 'RGBA')
    b64 = img_b64(im)
    # SVG 标注
    g = [f'<image href="data:image/png;base64,{b64}" x="0" y="0" width="{W}" height="{H}"/>']
    letters = step['letters']  # spec_label -> 字母
    for s, sp, h, t, a in labels:
        x0, y0 = proj(t - a * E)           # 爆炸后螺丝尖
        x1, y1 = proj(h)                   # 装好后螺丝头位置（孔口）
        g.append(f'<line x1="{x0:.1f}" y1="{y0:.1f}" x2="{x1:.1f}" y2="{y1:.1f}" class="exl"/>')
        g.append(f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="3.2" class="exd"/>')
    for s, sp, h, t, a in labels:
        xh, yh = proj(h - a * (E + 1.5))
        xt, yt = proj(t - a * E)
        vx, vy = xh - xt, yh - yt; L = max(np.hypot(vx, vy), 1e-6)
        lx, ly = xh + vx / L * 16, yh + vy / L * 16
        lx = min(max(lx, 14), W - 14); ly = min(max(ly, 14), H - 14)
        lab = step['nums'][s] if 'nums' in step else letters[spec_label(s)]
        col = '#%02x%02x%02x' % tuple(int(c * 255) for c in SCREW_C[sp])
        g.append(f'<circle cx="{lx:.1f}" cy="{ly:.1f}" r="12" fill="{col}" class="lbc"/>'
                 f'<text x="{lx:.1f}" y="{ly + 0.5:.1f}" class="lbt">{lab}</text>')
    for p, txt in step.get('notes_on_fig', []):
        x, y = proj(np.asarray(p, float))
        g.append(f'<text x="{x:.1f}" y="{y:.1f}" class="fnote" text-anchor="middle">{html.escape(txt)}</text>')
    for (p, txt) in step.get('inserts', []):
        x, y = proj(p)
        g.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="6.5" class="ins"/><text x="{x + 9:.1f}" y="{y - 7:.1f}" class="inst">{txt}</text>')
    svg = (f'<svg viewBox="0 0 {W} {H}" xmlns="http://www.w3.org/2000/svg" role="img" '
           f'aria-label="{html.escape(step["title"])}">' + ''.join(g) + '</svg>')
    return svg


def insert_points(part, screws):
    pts = []
    for s in screws:
        p, dia = entry(s, part)
        if p is not None:
            pts.append((p, spec_of(s).replace('S', 'M'), dia))
    return pts


# ---------- 零件分组 ----------
MOUTH_SERVO_TOP = [91, 149, 94, 95, 123, 100]
MOUTH_SERVO_JAW = [155, 109, 89]
MG996 = [176, 185]
LIP_PARTS = [83, 93, 98, 105, 106, 130, 132, 138, 144, 146, 148, 157, 159, 160, 171, 174, 177, 181, 183, 156, 164, 82, 92]
TEETH = [134, 150, 154, 170]
EYE = [28, 29, 30, 31, 32, 33, 34, 36, 37, 38, 39, 41, 42, 44, 45, 47, 48, 49, 50, 54, 55, 56, 57, 58, 59, 60, 62]
EYE_SERVO = [35, 40, 43, 51, 52, 61]
EYEBALL = [46, 53]
BROW = [4, 12, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 76, 77, 78]
BROW_SERVO = [75, 79]

M2_TOP = [87, 117, 112, 120, 124, 107, 178, 182]
M2x8_TOP = [97, 163]
M2_JAW = [86, 116, 167, 173, 153, 184]
M3x6_996 = [114, 118, 119, 121, 126, 127, 168, 187]
M2_HORN_R = [108, 110, 128, 131]
M2_HORN_L = [80, 103, 133, 179]
M4x8_JAW = [81, 101, 137, 166]
M25 = [84, 88, 90, 122, 125, 147, 165, 169]
S3 = [85, 99, 104, 136, 141, 142, 143, 145, 152, 158, 175, 180, 186, 189]
S4 = [115, 135, 139, 140]
M4x6_CHEEK = [2, 14]
M4x16 = [1, 6, 20, 21, 64, 190]
M3x8_CHEEK = [5, 11, 17, 24]
M3x8_EYE = [3, 13, 18, 23]
M3x10_SIDE = [8, 15, 16, 19, 22, 25]


def L(*specs):
    return {s: chr(65 + i) for i, s in enumerate(specs)}


def ins_list(part, screws):
    out = []
    for p, sp, dia in insert_points(part, screws):
        out.append((p, ''))
    return out


STEPS = []

# 热熔螺母：TopBase
tb_ins = [(p, sp) for p, sp, _ in insert_points(188, M2_TOP + M2x8_TOP + M3x6_996 + M4x16 + M4x6_CHEEK + [135, 139])]
STEPS.append(dict(
    key='ins_top', title='热熔螺母 ① 上颌座 TopBase', parts=[(188, C_RECV)], screws=[], letters={},
    inserts=[(p, sp) for p, sp in tb_ins], dir=(0.55, 0.55, -0.62), size=(1000, 760),
    text='上颌座是整个嘴部的骨架，热熔螺母最多。黄点 = 热熔螺母孔，旁边写规格。从哪一面拧螺丝，就从哪一面压热熔螺母。',
    table=[('M2', 'Ø3.2', 10, '6 个 MG90S 的安装耳'), ('M3', 'Ø4.4', 8, '2 个 MG996R 的安装耳'),
           ('M4', 'Ø5.35', 10, '6 个挂到头骨竖板（M4×16）、2 个接颧骨（M4×6）、2 个台阶螺丝转轴')],
))
jb_ins = [(p, sp) for p, sp, _ in insert_points(113, M2_JAW + M4x8_JAW + [115, 140])]
STEPS.append(dict(
    key='ins_jaw', title='热熔螺母 ② 下颌座 JawBase', parts=[(113, C_RECV)], screws=[], letters={},
    inserts=jb_ins, dir=(0.6, 0.5, 0.62), size=(1000, 700),
    text='下颌座：3 个 MG90S（两侧是下唇 LLL / LLR，中间是舌头 TON）装在这里，下颌连杆也拧在这里。',
    table=[('M2', 'Ø3.2', 6, '3 个 MG90S 的安装耳'), ('M4', 'Ø5.35', 6, '4 个下颌连杆（M4×8）、2 个台阶螺丝转轴。另有第 7 个 M4 孔（图上没标，在下颌前部，Part_19 旁边），推测是舌头连杆转轴，不装舌头可以不压')],
))
ck_ins = [(p, sp) for p, sp, _ in insert_points(27, M3x8_CHEEK)]
sf_ins = [(p, sp) for p, sp, _ in insert_points(0, M3x10_SIDE)]
ey_ins = [(p, sp) for p, sp, _ in insert_points(44, M3x8_EYE)]
STEPS.append(dict(
    key='ins_other', title='热熔螺母 ③ 颧骨、眼部底板、头骨侧面', parts=[(27, C_RECV), (44, C_RECV), (0, (0.93, 0.92, 0.88))], screws=[], letters={},
    inserts=ck_ins + ey_ins + sf_ins, dir=(0.75, 0.55, -0.35), size=(1000, 820),
    text='颧骨下面 4 个、眼部机构底板 4 个、头骨框架左右两侧各 3 个，都是 M3。眉毛底板、风扇、外壳的孔见图下方。',
    table=[('M3', 'Ø4.4', 4, '颧骨 CheekBone'), ('M3', 'Ø4.3', 4, '眼部机构底板 SnapEyemech（后侧另有 2 个同样的孔，模型没画螺丝，可压可不压）'), ('M3', 'Ø4.4', 6, '头骨框架两侧外面（模型里没有对应零件，可能是装外皮用的；先只放热熔螺母）')],
))

STEPS.append(dict(
    key='servo_top', title='嘴部 MG90S ×6 → 上颌座', parts=[(188, C_RECV)] + [(g, C_SERVO) for g in MOUTH_SERVO_TOP],
    screws=M2_TOP + M2x8_TOP, letters=L('M2×6', 'M2×8'),
    text='6 个 MG90S 侧着装在上颌座左右两侧的舵机位（每侧 3 个，图是从正后方看）。螺丝<b>从外侧水平往里</b>（朝头的中线）拧：穿过舵机安装耳，拧进上颌座里的 M2 热熔螺母。有两处是两个舵机的安装耳叠在一起，用 M2×8。',
    rows=[('A', 'M2×6', 8, 'MG90S 安装耳', '上颌座 · M2 热熔螺母'), ('B', 'M2×8', 2, '两个叠在一起的安装耳', '上颌座 · M2 热熔螺母')],
))
STEPS.append(dict(
    key='servo_jaw', title='嘴部 MG90S ×3 → 下颌座', parts=[(113, C_RECV)] + [(g, C_SERVO) for g in MOUTH_SERVO_JAW],
    screws=M2_JAW, letters=L('M2×6'),
    text='下颌座上的 3 个 MG90S，同样是螺丝从外侧水平往里，穿过安装耳拧进 M2 热熔螺母。',
    rows=[('A', 'M2×6', 6, 'MG90S 安装耳', '下颌座 · M2 热熔螺母')],
))
STEPS.append(dict(
    key='mg996', title='MG996R ×2 → 上颌座', parts=[(188, C_RECV)] + [(g, C_MG996) for g in MG996] + [(g, C_SERVO) for g in MOUTH_SERVO_TOP],
    screws=M3x6_996, letters=L('M3×6'),
    text='两个 MG996R 装在上颌座左右两侧，输出轴朝外。每个 4 个安装耳，M3×6 从外侧往里拧进上颌座的 M3 热熔螺母（MG996R 自带的螺丝螺母用不上）。',
    rows=[('A', 'M3×6', 8, 'MG996R 安装耳', '上颌座 · M3 热熔螺母')],
))
STEPS.append(dict(
    key='jawlink', title='下颌连杆：接 MG996R 舵盘 + 接下颌座',
    parts=[(172, C_CLAMP), (111, C_CLAMP), (96, (0.95, 0.95, 0.95)), (113, C_RECV)] + [(g, C_MG996) for g in MG996],
    context=[188], screws=M2_HORN_R + M2_HORN_L + M4x8_JAW, letters=L('M2×6', 'M4×8'),
    dir=(0.95, 0.05, 0.3), explode=12,
    text='左右两根下颌连杆（JawLink 和镜像的 Part_33）：上端用 4 颗 M2×6 拧进 MG996R 的圆舵盘（直接拧进舵盘上的小孔，自攻），下端用 2 颗 M4×8 拧进下颌座的 M4 热熔螺母。<b>装之前 MG996R 先回中，下颌闭合时再拧舵盘。</b>模型里只画了右边的圆舵盘。',
    rows=[('A', 'M2×6', 8, '下颌连杆上端', 'MG996R 圆舵盘的孔（自攻）'), ('B', 'M4×8', 4, '下颌连杆下端', '下颌座 · M4 热熔螺母')],
))
STEPS.append(dict(
    key='m25', title='嘴唇连杆 → MG90S 输出轴',
    parts=[(g, C_CLAMP) for g in [106, 159, 83, 183, 148, 130, 157, 144]] + [(g, C_SERVO) for g in MOUTH_SERVO_TOP + MOUTH_SERVO_JAW],
    context=[188, 113], screws=M25, letters=L('M2.5×8'), dir=(0.0, -1.0, -0.25), explode=12,
    text='8 根短连杆直接套在 MG90S 的输出轴上（连杆就是舵盘），中间用 M2.5×8 拧进舵机输出轴的螺纹孔。舵机先回中再装。<b>如果你的舵机输出轴是 M2，换成 M2×8。</b>',
    rows=[('A', 'M2.5×8', 8, '连杆中心孔 Ø3', 'MG90S 输出轴')],
))
STEPS.append(dict(
    key='s3', title='嘴唇、嘴角转轴：M3 台阶螺丝 ×14',
    parts=[(g, C_CLAMP) for g in LIP_PARTS], context=[188, 113], screws=S3, letters=L('M3 台阶螺丝'),
    dir=(0.25, 1.0, 0.15), explode=10, size=(1000, 760),
    text='连杆之间、连杆和嘴唇之间的转动关节。台阶螺丝的光滑轴肩（Ø4）穿过前一个零件的 Ø4.3 孔，让它能转；螺纹（M3，4 mm）拧进后一个零件，背面有六角槽放一颗 <b>普通 M3 螺母</b>。拧到零件能自由转动、没有前后晃动就停，别拧死。<b>没有台阶螺丝时临时用 M3×8 普通螺丝 + 螺母代替</b>：只拧到连杆刚好能转，会有一点晃，最后加一滴螺纹胶。剖面对比和测试步骤见 <a href="#sub-shoulder">台阶螺丝替代</a>。',
    rows=[('A', 'M3 台阶螺丝', 14, '转动的连杆（孔 Ø4.3）', '嘴唇 / 连杆 · 背面 M3 螺母')],
))
STEPS.append(dict(
    key='s4', title='嘴唇大转轴：M4 台阶螺丝 ×4',
    parts=[(93, C_CLAMP), (146, C_CLAMP), (160, C_CLAMP), (177, C_CLAMP), (188, C_RECV), (113, C_RECV), (102, C_BRASS), (151, C_BRASS)],
    screws=S4, letters=L('M4 台阶螺丝'), dir=(1.0, -0.35, 0.25), explode=12,
    text='上唇、下唇的主转轴。M4 台阶螺丝的轴肩（Ø5）穿过连杆的 Ø5.3 孔，拧进上颌座 / 下颌座里的 M4 热熔螺母；模型里在两处加了 M4、M5 平垫。<b>临时替代：M4×10 普通螺丝</b>，同样只拧到连杆能转。下颌承重，正式装建议用台阶螺丝。详见 <a href="#sub-shoulder">台阶螺丝替代</a>。',
    rows=[('A', 'M4 台阶螺丝', 4, '连杆（孔 Ø5.3）+ 平垫', '上颌座 / 下颌座 · M4 热熔螺母')],
))
STEPS.append(dict(
    key='cheek', title='颧骨 → 上颌座', parts=[(27, C_CLAMP), (188, C_RECV)] + [(g, C_MG996) for g in MG996],
    screws=M4x6_CHEEK, letters=L('M4×6'), explode=14,
    text='颧骨从前面套在上颌座前端，2 颗 M4×6 <b>从颧骨正面往后、略向下</b>斜着拧，进上颌座前部的 M4 热熔螺母。',
    rows=[('A', 'M4×6', 2, '颧骨', '上颌座 · M4 热熔螺母')],
))
STEPS.append(dict(
    key='skull_mouth', title='嘴部模块 → 头骨框架', parts=[(0, C_CLAMP), (188, C_RECV), (27, (0.80, 0.80, 0.78))] + [(g, C_MG996) for g in MG996],
    screws=M4x16, letters=L('M4×16'), dir=(0.8, 0.35, 0.45), explode=16, size=(1000, 820),
    text='头骨框架下部左右各有一块竖板，嘴部模块（上颌座）塞在两块竖板中间。6 颗 M4×16（每侧 3 颗）<b>从竖板外侧水平往里</b>，穿过竖板拧进上颌座侧面的 M4 热熔螺母。先把嘴部模块整个装好、调好，再挂上去。',
    rows=[('A', 'M4×16', 6, '头骨框架（孔 Ø4.4）', '上颌座侧面 · M4 热熔螺母')],
))
STEPS.append(dict(
    key='skull_cheek_eye', title='头骨框架 → 颧骨、眼部机构', parts=[(0, C_CLAMP), (27, C_RECV), (44, C_RECV)] + [(g, C_SERVO) for g in EYE_SERVO],
    screws=M3x8_CHEEK + M3x8_EYE, letters=L('M3×8'), dir=(1.0, 0.3, 0.1), explode=14, size=(1000, 820),
    text='从头骨框架两侧往里拧：每侧 2 颗固定颧骨、2 颗固定眼部机构底板，都是 M3×8 拧进 M3 热熔螺母。<b>你手上的 M3×8 是外六角头，先试一颗看框架上的沉孔放不放得下。</b>',
    rows=[('A', 'M3×8', 8, '头骨框架（孔 Ø3.6）', '颧骨 4 颗 + 眼部底板 4 颗 · M3 热熔螺母')],
))

# 眼部、眉毛：模型没画螺丝，只给模块总图
STEPS.append(dict(
    key='eyes', title='眼部机构（模型里没画螺丝）', parts=[(g, (0.78, 0.80, 0.86)) for g in EYE] + [(g, C_SERVO) for g in EYE_SERVO] + [(g, (0.97, 0.97, 0.97)) for g in EYEBALL],
    screws=[], letters={}, dir=(0.55, 0.75, -0.45), size=(1000, 760),
    text='6 个舵机（眼球左右、上下，四片眼皮）装在底板上，连杆是卡扣式（snap-fit），基本不用螺丝。舵机用自带的自攻螺丝固定在底板的舵机座上。这部分照作者单独开源的眼睛机构教程装：<a href="https://www.instructables.com/Animatronic-Eye-Mechanism">Instructables: Animatronic Eye Mechanism</a>。',
    rows=[],
))
STEPS.append(dict(
    key='brows', title='眉毛机构（模型里没画螺丝）', parts=[(g, (0.86, 0.82, 0.74)) for g in BROW] + [(g, C_SERVO) for g in BROW_SERVO],
    screws=[], letters={}, dir=(0.3, 0.9, -0.5), size=(1000, 640),
    text='眉毛底板 Part_4 上装 4 个 MG90S（模型里只画了机器人右侧 2 个，左侧按镜像装），舵机带动 Part_3，Part_2 跟着转，两根连杆带动 4 个臂（Part_8 / 9 / 12 / 13），最外面是 TPU 软眉毛 Part_11 / Part_14。模型里没画螺丝，下面的表是按孔径和同轴关系推出来的。',
    rows=[],
))


# ---------- 嘴部上颚：不需要热熔螺母的部分（左右各一张，逐颗编号） ----------
def cen(g):
    return S.pts(g).mean(0)


UP_L = dict(m3=[(85, 159, 105), (104, 93, 105), (136, 171, 98), (143, 130, 171), (158, 157, 98)],
            m25=[(88, 159, 149), (147, 130, 95), (165, 157, 94)],
            parts=[105, 159, 93, 171, 98, 130, 157], servos=[149, 95, 94], side='左', sg=1)
UP_R = dict(m3=[(142, 146, 174), (152, 106, 174), (145, 83, 181), (175, 132, 181), (180, 144, 132)],
            m25=[(84, 106, 91), (90, 83, 123), (169, 144, 100)],
            parts=[174, 106, 146, 132, 181, 83, 144], servos=[91, 123, 100], side='右', sg=-1)
for U in (UP_L, UP_R):
    nums, rows = {}, []
    k = 1
    for sc_, rot, recv in U['m3']:
        nums[sc_] = str(k)
        rows.append((str(k), 'M3 台阶螺丝', 1, f'{cn(rot)}（孔 Ø4.3，转动）', f'{cn(recv)} · 背面 M3 螺母'))
        k += 1
    for sc_, link, servo in U['m25']:
        nums[sc_] = str(k)
        rows.append((str(k), 'M2.5×8', 1, f'{cn(link)}（中心孔 Ø3）', 'MG90S 输出轴（先回中）'))
        k += 1
    sg = U['sg']
    STEPS.append(dict(
        key='upper_' + ('l' if sg > 0 else 'r'), title=f'嘴部上颚 · 不用热熔螺母的部分（机器人{U["side"]}侧）',
        parts=[(g, C_CLAMP) for g in U['parts']] + [(g, C_SERVO) for g in U['servos']], context=[188],
        screws=[x[0] for x in U['m3']] + [x[0] for x in U['m25']], nums=nums, letters={},
        dir=(-0.8 * sg, 0.6, -0.25), explode=13, size=(1000, 820),
        notes_on_fig=[(cen(g) + np.array([0, -6, 0]), cn(g).split('（')[0]) for g in U['parts']],
        text=(f'上唇、嘴角的连杆组，机器人{U["side"]}侧（另一侧镜像）。'
              '<b>1 到 5</b>：转动关节，台阶螺丝穿过转动的零件，拧进后一个零件背面六角槽里的 M3 螺母（没有台阶螺丝就用 M3×8 + 螺母，见 <a href="#sub-shoulder">台阶螺丝替代</a>）。'
              '这 5 个关节可以<b>脱离上颌座，先在桌上把连杆组装好</b>。'
              '<b>6 到 8</b>：连杆当舵盘用，M2.5×8 拧进 MG90S 输出轴，<b>舵机要先回中</b>；建议舵机装进上颌座之后再拧，免得连杆挡住舵机塞不进去（Blender 里打开这一步先看一眼）。'
              '浅灰色的是上颌座，只作位置参考。'),
        rows=rows,
    ))


# ---------- 眼部机构：卡扣式，不用螺丝；分层累加（新装的上色，之前的灰色） ----------
EYE_L1 = [44, 45, 59, 34]                 # 底板 + 3 个舵机座
EYE_S1 = [40, 43, 51, 52, 61]             # 眼皮 4 个 + 上下 1 个
EYE_L2 = [33, 49, 36, 37, 39]             # 竖板 + 眼球支架
EYE_S2 = [35]                             # 左右（LR）
EYE_L3 = [28, 29, 30, 31, 54, 47, 56, 57, 60, 32, 42]
EYE_L4 = [41, 62, 46, 53, 38, 48, 50, 58]
C_PREV = (0.80, 0.80, 0.78)
C_HOLD = (0.60, 0.74, 0.92); C_BASE = (0.62, 0.85, 0.62); C_HORN = (0.96, 0.62, 0.25); C_LEV = (0.70, 0.55, 0.88)
C_LID = (0.93, 0.70, 0.72); C_BALL = (0.98, 0.98, 0.98)


def lab(g, txt, dz=0.0, dy=0.0):
    """标签锚在零件自身上：取离质心最近的顶点（长连杆的质心可能落在空中）"""
    P = S.pts(g); c = P.mean(0)
    return (P[np.argmin(np.linalg.norm(P - c, axis=1))] + np.array([0, dy, dz]), txt)


SV = {43: 'TL 舵机', 51: 'BL 舵机', 52: 'TR 舵机', 40: 'BR 舵机', 61: 'UD 舵机', 35: 'LR 舵机'}
STEPS.append(dict(
    key='eye1', title='眼部 ① 底板 + 舵机座 + 5 个舵机（卡进去，不用螺丝）',
    parts=[(44, C_HOLD), (45, C_BASE), (59, C_BASE), (34, C_BASE)] + [(g, C_SERVO) for g in EYE_S1],
    screws=[], letters={}, dir=(0.25, -0.75, -0.62), size=(1000, 760),
    notes_on_fig=[lab(44, 'SnapEyemech_v20（底板）', dz=-6, dy=30), lab(45, 'SnapEyemech_v20_v2', dz=22),
                  lab(59, 'SnapEyemech_v20_v2', dz=22), lab(34, 'SnapEyemech_v20_v3', dz=20)]
                 + [lab(g, SV[g], dz=-2) for g in EYE_S1],
    text='图是从<b>后上方</b>看（眼睛朝下方）。大底板上左右各一个舵机座 SnapEyemech_v20_v2，每个卡 2 个眼皮舵机；中间的小舵机座 SnapEyemech_v20_v3 卡眼球上下（UD）舵机。'
         '舵机直接按进座子的卡槽，<b>不用螺丝、不用热熔螺母</b>。卡得太紧别硬压，用锉刀稍微修一下卡槽；太松可以垫一层胶带。'
         '<b>这一步不用回中</b>，舵机还没接任何连杆。舵机线朝哪边出，照图里舵机的方向放，方便后面走线。',
    rows=[],
))
STEPS.append(dict(
    key='eye2', title='眼部 ② 竖板 + 眼球支架 + LR 舵机',
    parts=[(g, C_BASE) for g in [33, 49, 36, 37]] + [(39, C_HOLD), (35, C_SERVO)], context=EYE_L1 + EYE_S1,
    screws=[], letters={}, dir=(-0.45, 0.8, -0.5), size=(1000, 760),
    notes_on_fig=[lab(36, 'Base'), lab(37, 'Base'), lab(33, 'Base_v2'), lab(49, 'Base_v2'),
                  lab(39, 'EyeCorePivotHolder', dz=14), lab(35, 'LR 舵机', dz=-12)],
    text='图从<b>前上方</b>看。4 块竖板立在底板前部：外侧两块是 Base，内侧两块是 Base_v2。中间的 EyeCorePivotHolder 是眼球的转轴支架，眼球左右转（LR）的舵机在它前面。'
         '模型里没画 LR 舵机的固定件（打印包里有一个 LateralFrame，大概率就是它），装的时候对照作者的眼睛机构教程。灰色是上一步装好的。',
    rows=[],
))
STEPS.append(dict(
    key='eye3', title='眼部 ③ 舵盘和连杆（先回中再装）',
    parts=[(g, C_HORN) for g in [28, 29, 30, 31, 54, 47]] + [(g, C_LEV) for g in [56, 57, 60, 32, 42]],
    context=EYE_L1 + EYE_S1 + EYE_L2 + EYE_S2, screws=[], letters={}, dir=(-0.75, 0.45, -0.5), size=(1000, 760),
    notes_on_fig=[lab(30, 'TopLidHorn → TR', dz=10), lab(28, 'TopLidHorn → BR', dz=-10), lab(31, 'TopLidHorn → TL', dz=10),
                  lab(29, 'TopLidHorn → BL', dz=-10), lab(54, 'CentralServoHorn → LR', dz=10), lab(47, 'VerticalHorn → UD', dz=10),
                  lab(56, 'VerticalLever', dz=8), lab(57, 'TopLidLever', dz=8), lab(60, 'TopLidLever', dz=8),
                  lab(32, 'BottomLidLever', dz=-8), lab(42, 'BottomLidLever', dz=-8)],
    text='橙色 = 打印的舵盘，直接压到舵机输出轴的花键上（4 个 TopLidHorn、1 个 CentralServoHorn、1 个 VerticalHorn）；紫色 = 连杆，一头卡在舵盘上，一头卡在眼皮或眼球支架上。'
         '<b>装舵盘之前每个舵机都要先回中（90°）</b>，回中后按这个姿态装：眼球朝正前方；<b>四片眼皮都闭合</b>（固件里 TL/BL/TR/BR 的 90° 都是闭眼）。差一个齿就拔下来换个齿位，不要掰连杆。'
         '舵盘中心如果有孔，用舵机自带的舵盘螺丝固定。',
    rows=[],
))
STEPS.append(dict(
    key='eye4', title='眼部 ④ 眼球 + 眼皮',
    parts=[(41, C_HOLD), (62, C_HOLD), (46, C_BALL), (53, C_BALL)] + [(g, C_LID) for g in [38, 48, 50, 58]],
    context=EYE_L1 + EYE_S1 + EYE_L2 + EYE_S2 + EYE_L3, screws=[], letters={}, dir=(-0.4, 0.85, -0.3), size=(1000, 760),
    notes_on_fig=[lab(53, '眼球', dz=0, dy=-8), lab(46, '眼球', dz=0, dy=-8), lab(50, 'LidBR（上眼皮位置）', dz=14),
                  lab(58, 'LidBR（上眼皮位置）', dz=14), lab(48, 'LidTR / LidTR_v2（下眼皮位置）', dz=-14),
                  lab(38, 'LidTR / LidTR_v2（下眼皮位置）', dz=-14), lab(62, 'EyeAdaptor', dz=6, dy=10)],
    text='眼球通过 EyeAdaptor（每只眼一个 EyeAdaptor + 一个 EyeAdaptor_v2）卡到眼球支架上，眼皮卡到竖板和连杆上。'
         '注意 STL 名字和位置对不上：<b>名字叫 LidBR 的其实装在上面，LidTR / LidTR_v2 装在下面</b>（按模型里的位置）。模型只画了左眼的 EyeAdaptor，右眼照镜像装。'
         '装完通电前，先用手轻推每片眼皮和眼球，确认整个行程没有卡点。',
    rows=[],
))

# ---------- 重排：按真实装配顺序，模型没画的连接用 final_fig 补 ----------
BY = {s['key']: s for s in STEPS}
BASE_EYE = [44]
XA, XB = final_fig.pivot_a(), final_fig.lateral_frame()
RA = final_fig.right_adaptors(S)
GRAY = lambda *ts: [(t, C_PREV) for t in ts]
XMID = lambda T: T.reshape(-1, 3).mean(0)
s = BY['eye2']
s.update(key='eye_base', title='眼部 ② 眼球核心卡进底板', parts=[(44, C_PREV)] + [(g, C_BASE) for g in [33, 49]] + [(39, C_HOLD), (35, C_SERVO)], context=[],
         extra=[(XA, C_LEV), (XB, C_HORN)],
         notes_on_fig=[lab(33, 'Base_v2'), lab(49, 'Base_v2'), lab(39, 'Y 轴支架', dz=14), lab(35, 'LR 舵机', dz=-12), ((-30, -62, -14), 'X 轴件 A'), ((30, -44, 12), 'X 轴件 B（LateralFrame）')],
         text='把上一步的眼球核心从<b>底板下面</b>往上卡，两个 Base_v2 的卡脚扣进底板。灰色是底板。紫色是 X 轴件 A，橙色是 X 轴件 B，这时 B 还是松放的。')
s = BY['eye4']
s.update(key='eye_lid', title='眼部 ③ 眼球 + 眼皮 + 外侧枢轴座',
         parts=[(41, C_HOLD), (62, C_HOLD), (46, C_BALL), (53, C_BALL), (36, C_BASE), (37, C_BASE)] + [(g, C_LID) for g in [38, 48, 50, 58]],
         context=BASE_EYE + [33, 49, 39, 35], extra=[(RA[0], C_HOLD), (RA[1], C_HOLD)] + GRAY(XA, XB),
         text='每只眼球背面装一个 EyeAdaptor（上）和一个 EyeAdaptor_v2（下）。X 轴件 A 两端的销钉插进下面 EyeAdaptor_v2 的 Ø7 孔，这是眼球左右转的轴。眼皮先上下对齐，再一起插进中间枢轴：可以稍微掰一下机构，或者把眼球转到左右两边再插。'
              '最后把外侧的 Base 从底板下面卡上，眼皮就固定了。'
              '注意 STL 名字和位置对不上：<b>名字叫 LidBR 的其实装在上面，LidTR / LidTR_v2 装在下面</b>。模型只画了左眼的 EyeAdaptor，图里右眼是镜像补上的。')
s = BY['eye1']
s.update(key='eye_servo', title='眼部 ④ 其余 5 个舵机 + 压扣', context=BASE_EYE + [33, 49, 36, 37, 39, 35, 41, 62, 46, 53, 38, 48, 50, 58],
         parts=[(45, C_BASE), (59, C_BASE), (34, C_BASE)] + [(g, C_SERVO) for g in EYE_S1], extra=GRAY(XA, XB, *RA),
         notes_on_fig=[lab(45, 'SnapEyemech_v20_v2 压扣', dz=22), lab(59, 'SnapEyemech_v20_v2 压扣', dz=22), lab(34, 'SnapEyemech_v20_v3 压扣', dz=20)] + [lab(g, SV[g], dz=-2) for g in EYE_S1],
         text='图是从<b>后上方</b>看（眼睛朝下方）。先把 5 个舵机放到底板上，再把绿色压扣从上面扣下去压住：两个 SnapEyemech_v20_v2 各压 2 个眼皮舵机，SnapEyemech_v20_v3 压 UD 舵机。'
              '<b>不用螺丝、不用热熔螺母</b>。卡得太紧别硬压，用锉刀稍微修一下；太松就垫一层胶带。')
EYE_PRE = BASE_EYE + [33, 49, 36, 37, 45, 59, 34, 40, 43, 51, 52, 41, 62, 46, 53, 38, 48, 50, 58]
STEPS.append(dict(key='eye_lr', title='眼部 ⑤ 左右控制：LR 舵机 → 两只眼球', parts=[(35, C_SERVO), (54, C_HORN), (39, C_HOLD)], context=EYE_PRE + [61], extra=[(XB, C_LEV)] + GRAY(XA, *RA),
                  screws=[], letters={}, dir=(-0.45, 0.8, -0.5), size=(1000, 760),
                  notes_on_fig=[lab(54, 'CentralServoHorn', dz=8), lab(35, 'LR 舵机', dz=-12), lab(39, 'Y 轴支架', dz=14), ((22, -40, 13), 'LateralFrame')],
                  text='这一步让两只眼球一起左右转。传动路线：<b>LR 舵机 → CentralServoHorn 后端 → LateralFrame → 两只 EyeAdaptor 的尾部 → 两只眼球</b>。三个环中心距 37.5 mm，和 EyeAdaptor 尾部到转轴的臂长一样，所以舵盘一转，LateralFrame 横着平移，两只眼同步转。'
                       '<ol><li>取下图 @@eye_core@@ 松装的 LateralFrame。</li><li>LR 舵机回中（90°）。</li><li>两只眼球用手摆到朝正前方。</li>'
                       '<li>CentralServoHorn 压到 LR 舵机轴上，拧舵机自带的舵盘螺丝。</li><li>装回 LateralFrame：<b>中间的环卡到舵盘后端的卡柱，两端的环卡到两只 EyeAdaptor 尾部的卡柱</b>。有小圆点的一面朝上，直梁在环的后面。</li>'
                       '<li>用手轻轻左右拨，<b>两只眼要一起动，停下来时都朝正前方</b>。一只歪了就回到第 3 步。</li></ol>'
                       '模型没画 LateralFrame，图里的紫色件是按孔位放回去的，三个环都和卡柱同轴。',
                  rows=[]))
STEPS.append(dict(key='eye_ud', title='眼部 ⑥ 上下控制：UD 舵机 → Y 轴', parts=[(61, C_SERVO), (47, C_HORN), (56, C_LEV), (39, C_HOLD), (34, C_BASE)], context=EYE_PRE + [35, 54], extra=GRAY(XA, XB, *RA),
                  screws=[], letters={}, dir=(-0.75, 0.45, -0.5), size=(1000, 760),
                  notes_on_fig=[lab(47, 'VerticalHorn', dz=10), lab(56, 'VerticalLever', dz=10), lab(61, 'UD 舵机', dz=-4), lab(39, 'Y 轴支架', dz=-14)],
                  text='这一步让两只眼球一起上下转。传动路线：<b>UD 舵机 → VerticalHorn → VerticalLever（拱形）→ Y 轴支架 EyeCorePivotHolder → 整个眼球核心上下摆</b>。这三段的接触关系在模型里都能量到。'
                       '<ol><li>UD 舵机不好够，官方建议先取下压扣，把舵机拿出来，<b>记住原来的位置和朝向</b>。</li><li>UD 舵机回中（90°）。</li><li>在外面把 VerticalHorn 压到舵机轴上，拧舵盘螺丝，再把 VerticalLever 卡到舵盘上。</li>'
                       '<li>舵机放回原位，扣回压扣。</li><li>VerticalLever 另一头卡到 Y 轴支架上，这时眼球要朝正前方。</li><li>用手轻轻上下拨，确认两只眼一起动、没有卡点。</li></ol>',
                  rows=[]))
s = BY['eye3']
s.update(key='eye_horn', title='眼部 ⑦ 眼皮：舵盘和连杆（先回中再装）', context=EYE_PRE + [39, 35, 54, 61, 47, 56, 34], extra=GRAY(XA, XB, *RA),
         parts=[(g, C_HORN) for g in [28, 29, 30, 31]] + [(g, C_LEV) for g in [57, 60, 32, 42]],
         notes_on_fig=[lab(30, 'TopLidHorn → TR', dz=10), lab(28, 'TopLidHorn → BR', dz=-10), lab(31, 'TopLidHorn → TL', dz=10), lab(29, 'TopLidHorn → BL', dz=-10),
                       lab(57, 'TopLidLever', dz=8), lab(60, 'TopLidLever', dz=8), lab(32, 'BottomLidLever', dz=-8), lab(42, 'BottomLidLever', dz=-8)],
         text='橙色是舵盘，压到眼皮舵机轴上；紫色是连杆，一头卡舵盘，一头卡眼皮。<b>上眼皮用短连杆 TopLidLever，下眼皮用长连杆 BottomLidLever。</b>'
              '4 个舵机先回中（90°），四片眼皮摆到<b>闭合、在中间对齐</b>的位置再装，然后拧舵盘螺丝。固件里 TL/BL/TR/BR 的 90° 都是闭眼。差一个齿就拔下来换齿位，不要掰连杆。')
s = BY['eyes']
s.update(key='eye_done', title='眼部 ⑧ 装完后的样子', extra=[(XA, (0.78, 0.80, 0.86)), (XB, (0.78, 0.80, 0.86)), (RA[0], (0.78, 0.80, 0.86)), (RA[1], (0.78, 0.80, 0.86))], text='到这里眼部模块完成。用手轻推每片眼皮和眼球，确认整个行程没有卡点，<b>不要用力转</b>。接下来整块用 M3×8 装到框架上（图 @@skull_eye@@）。', rows=[])
BY['ins_other'].update(title='热熔螺母 ③ 颧骨、眼部底板、头骨框架', text='颧骨下面 4 个、眼部底板 6 个（后面 2 个模型没画螺丝，框架上有对应孔，也压上）。框架和其他零件的孔见图下方的表。',
                       table=[('M3', 'Ø4.4', 4, '颧骨 CheekBone'), ('M3', 'Ø4.3', 6, '眼部底板 SnapEyemech_v20')], after=final_fig.ins_all)
BY['brows']['title'] = '眉毛模块（模型里没画螺丝）'
STEPS.append(dict(key='eye_core', title='眼部 ① 先在桌上组眼球核心', custom=final_fig.eye_core,
                  text='<b>这一步模型里没有，之前的文档漏了。</b>两根横梁把两只眼球连在一起：<b>EyeCorePivotHolder_v2（X 轴件 A）</b>在下面，托住 LR 舵机和两只眼球的转轴；<b>LateralFrame（X 轴件 B，3 个圆环）</b>在上面，负责带动两只眼左右转。下面第一张图是它们的最终位置，是按孔位放回去的。', parts=[], screws=[], letters={}))
STEPS.append(dict(key='tongue', title='舌头 + 牙齿', custom=final_fig.tongue,
                  text='TON 舵机带 Part_20，Part_20 拉 Part_21，Part_19 是前面的转轴。模型没画这 4 颗螺丝，下面按同轴孔推出来。'
                       '<b>舌头和 4 块牙齿、牙龈都没有螺丝孔</b>，推断是胶粘：下牙龈贴下颌座，下牙贴下牙龈，上牙龈贴上颌座，上牙贴上牙龈，舌头粘到 Part_21 上面。先干装确认张嘴时不碰，再用胶。', parts=[], screws=[], letters={}))
STEPS.append(dict(key='skull_eye', title='眼部模块 → 头骨框架', parts=[(0, C_CLAMP), (44, C_RECV)] + [(g, C_SERVO) for g in EYE_SERVO],
                  screws=M3x8_EYE, letters=L('M3×8'), dir=(1.0, 0.3, 0.1), explode=14, size=(1000, 820),
                  text='眼部模块从框架<b>前面</b>送进去，稍微往后下方走。M3×8 从框架外侧往里，每侧 3 颗。图里画了每侧 2 颗，第 3 颗在它们后面（y=8），模型没画。<b>你手上的 M3×8 是外六角头，先试一颗看沉孔放不放得下。</b>',
                  rows=[('A', 'M3×8', 6, '头骨框架（孔 Ø3.6）', '眼部底板 · M3 热熔螺母')]))
STEPS.append(dict(key='brow_skull', title='眉毛模块 → 头骨框架', custom=final_fig.brow_skull,
                  text='眉毛模块从<b>前上方</b>送进框架，在眼部上面。8 颗 M4 从框架外侧往里拧进 Part_4：两侧各 3 颗，前面斜着各 1 颗。图上画的是机器人左侧 4 颗，右侧镜像。'
                       '<b>长度用 M4×12。</b>M4×8 只进螺母 1 mm，不够；M4×16 会顶到孔底。模型没画这些螺丝，孔位是实测同轴的。TPU 眉毛装之前先把这一步做完。',
                  rows=[('A', 'M4×12', 8, '头骨框架（孔 Ø4.6）', 'Part_4 · M4 热熔螺母')], parts=[], screws=[], letters=L('M4×12')))
BY['skull_mouth'].update(title='嘴部模块 + 颧骨 → 头骨框架',
                         text='嘴部模块带着颧骨，从<b>前下方</b>往上送，塞进框架下部左右两块竖板中间。6 颗 M4×16（每侧 3 颗）<b>从竖板外侧水平往里</b>，拧进上颌座侧面的 M4 热熔螺母。先把嘴部整个装好、调好，再挂上去。')
STEPS.append(dict(key='skull_cheek', title='颧骨 → 头骨框架', parts=[(0, C_CLAMP), (27, C_RECV)], screws=M3x8_CHEEK, letters=L('M3×8'), dir=(1.0, 0.3, 0.1), explode=14, size=(1000, 820),
                  text='颧骨两侧再各用 2 颗 M3×8 固定到框架上，从框架外侧往里。', rows=[('A', 'M3×8', 4, '头骨框架（孔 Ø3.6）', '颧骨 · M3 热熔螺母')]))
STEPS.append(dict(key='pcb', title='三块板 → 头骨框架', custom=final_fig.pcb,
                  text='框架里面有一块斜板，孔距和板子吻合：<b>中间 65×48 是嘴部板，两侧 29.6 是眼眉板</b>，两块眼眉板哪边都行。图是从斜板正上方看，绿色是板子占的位置，黑点是孔。'
                       '板子背面有引脚，要垫高：M3×10 穿板子和 5 mm 垫柱，拧进框架的 M3 热熔螺母。垫柱高度是我估的，确认引脚不碰框架。眼眉板只有 2 个孔。模型没画板子，安装方向以 Pico 的 USB 线和电源线好走为准。',
                  rows=[('A', 'M3×10', 8, '板子 + 5 mm 垫柱', '框架斜板 · M3 热熔螺母')], parts=[], screws=[], letters=L('M3×10')))
STEPS.append(dict(key='fan', title='风扇支架 + 风扇', custom=final_fig.fan,
                  text='支架贴在框架后面，A 从支架穿进框架。风扇从支架后面装，B 穿过风扇的 4 个角，拧进支架。孔距 40，对应 50×50×10 风扇。后盖封口后风扇抽不出去，可以先不装，等试运行发现发热再说。B 的长度：风扇 10 + 螺母 4，用 M3×14；用风扇自带的自攻螺丝也行，那支架上就不用压螺母。',
                  rows=[('A', 'M3×8', 6, 'FanBracket（孔 Ø3.4）', '框架 · M3 热熔螺母'), ('B', 'M3×14', 4, '风扇', 'FanBracket · M3 热熔螺母')], parts=[], screws=[], letters=L('M3×8', 'M3×14')))
STEPS.append(dict(key='shell', title='合外壳', custom=final_fig.shell,
                  text='标定、走线都做完再合壳。后盖 RearPlate 从后面套上，<b>11 颗</b> M3×6（A）：两侧各 3、上方斜着 2、下方后面 2、顶上 1。前上盖 FrontVent 从上面盖，4 颗 M3×6（B）。'
                       '两个盖子的孔都有 Ø6 沉孔，螺丝头埋进去。额头条 FrontPlate 没有螺丝孔，贴到开口上用胶。框架外侧的 M3×10 模型里有，但外壳上没有孔，<b>不用装</b>。'
                       '<b>后盖用封口版</b>（2026-11-05 改的，出风口已封上），所以不用 RearVent 后格栅。头里的风没有后出口，合壳后先跑 10 分钟，摸舵机和板子的温度。',
                  rows=[('A', 'M3×6', 11, 'RearPlate（沉孔）', '框架 · M3 热熔螺母'), ('B', 'M3×6', 4, 'FrontVent（沉孔）', '框架 · M3 热熔螺母')], parts=[], screws=[], letters=L('M3×6')))
STEPS.append(dict(key='neck', title='装到颈部支架', custom=final_fig.neck,
                  text='支架是自己画的，原版没有。头放到两根斜立柱上，用 2 根扎带穿过立柱上端的扎带孔，绑住框架底部横梁。整头约 870 g，重心偏前，支架底板要放稳。', parts=[], screws=[], letters={}))
ORDER = [('A 准备：先把所有热熔螺母压好', ['ins_top', 'ins_jaw', 'ins_other']),
         ('B 眼部模块（桌上组装）', ['eye_core', 'eye_base', 'eye_lid', 'eye_servo', 'eye_lr', 'eye_ud', 'eye_horn', 'eye_done']),
         ('C 眉毛模块（桌上组装）', ['brows']),
         ('D 嘴部模块（桌上组装）', ['servo_top', 'servo_jaw', 'mg996', 'jawlink', 'm25', 's3', 'upper_l', 'upper_r', 's4', 'tongue', 'cheek']),
         ('E 总装：模块装进头骨框架', ['skull_eye', 'brow_skull', 'skull_mouth', 'skull_cheek']),
         ('F 电子、风扇、外壳', ['pcb', 'fan', 'shell', 'neck'])]
BY = {s['key']: s for s in STEPS}
STEPS[:] = [dict(BY[k], stage=(t if i == 0 else None)) for t, ks in ORDER for i, k in enumerate(ks)]
FIGNO = {s['key']: i for i, s in enumerate(STEPS, 1)}


def build():
    out = []
    for i, st in enumerate(STEPS, 1):
        print('render', st['key'], flush=True)
        svg = None if 'custom' in st else figure(st)
        rows = ''
        if st.get('stage'):
            out.append(f'<h2 class="stage" id="stage-{st["stage"][0]}">{html.escape(st["stage"])}</h2>')
        if st.get('rows'):
            rows = ('<table class="sc"><thead><tr><th>标</th><th>螺丝</th><th>数量</th><th>穿过</th><th>拧进</th><th>扳手</th></tr></thead><tbody>'
                    + ''.join(f'<tr><td><span class="lb" style="background:{lb_col(st, r[1])}">{r[0]}</span></td><td><b>{r[1]}</b></td>'
                              f'<td>{r[2]}</td><td>{r[3]}</td><td>{r[4]}</td><td>{hex_of(r[1])}</td></tr>' for r in st['rows'])
                    + '</tbody></table>')
        if st.get('table'):
            rows = ('<table class="sc"><thead><tr><th>热熔螺母</th><th>孔径</th><th>数量</th><th>给谁用</th></tr></thead><tbody>'
                    + ''.join(f'<tr><td><b>{a}</b></td><td>{b}</td><td>{c}</td><td>{d}</td></tr>' for a, b, c, d in st['table'])
                    + '</tbody></table>')
        out.append(f'<section class="stp" id="{st["key"]}"><h3><input type="checkbox" data-k="fig-{st["key"]}"> 图 {i} · {html.escape(st["title"])}</h3>'
                   f'<p>{st["text"]}</p>{st["custom"](S) if "custom" in st else ins_other_fig.html(S) if st["key"] == "ins_other" else '<div class="fig3d">' + svg + '</div>'}{rows}{st["after"]() if "after" in st else ""}{jaw_m2_fig.html(S) if st["key"] == "ins_jaw" else ""}{servo_shaft_fig.html(S) if st["key"] == "mg996" else ""}{link_id_fig.html(S) if st["key"] == "m25" else ""}{lip_link_fig.html(S) if st["key"] == "m25" else ""}{s3_chain_fig.html(S) if st["key"] == "s3" else ""}{brow_fig.html(S) if st["key"] == "brows" else ""}</section>')
    frag = final_fig.overview_section(S) + '\n' + '\n'.join(out)
    frag = re.sub(r'@@(\w+)@@', lambda m: str(FIGNO[m.group(1)]), frag)
    json.dump(FIGNO, open(os.path.join(OUT, 'figmap.json'), 'w'))
    open(os.path.join(OUT, 'steps_fragment.html'), 'w').write(frag)
    print('fragment', len(frag) // 1024, 'KB')


def lb_col(st, label):
    sp = {'M2×6': 'M2', 'M2×8': 'M2', 'M2.5×8': 'M2.5', 'M3×6': 'M3', 'M3×8': 'M3', 'M4×6': 'M4', 'M4×8': 'M4', 'M4×16': 'M4',
          'M3×10': 'M3', 'M3×14': 'M3', 'M4×12': 'M4', 'M3 台阶螺丝': 'S3', 'M4 台阶螺丝': 'S4'}[label]
    return '#%02x%02x%02x' % tuple(int(c * 255) for c in SCREW_C[sp])


def hex_of(label):
    sp = {'M2': 1.5, 'M2.5': 2, 'M3': 2.5, 'M4': 3}
    if '台阶' in label:
        return '2.5 mm' if 'M3' in label else '3 mm'
    return f'{sp[label.split("×")[0]]} mm'


if __name__ == '__main__':
    only = sys.argv[1:]
    if only:
        STEPS[:] = [s for s in STEPS if s['key'] in only]
    build()
