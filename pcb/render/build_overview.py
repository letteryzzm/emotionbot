"""生成「元件焊接一览图」：每块板一张静态俯视图，标出所有要焊/不焊的元件、焊接顺序和极性。

python3 -I build_overview.py
"""
import html, math, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from epro_geom import build  # noqa: E402

PCB = os.path.dirname(HERE)
OUT = os.path.expanduser("~/Documents/zzm/note/inbound/learningnote/robotic/复现项目/head/焊接一览图.html")

# 顺序号, 位号, 名称, 型号/编号, 备注, 类别(smd/th/bridge)
EYE = dict(
    title="眼眉板（做 2 块：眼睛 + 眉毛/脖子）", file="ProDoc_Eyes_Brow_Neck_2025-04-16.epro",
    items=[
        (1, ["C12"], "焊锡短接", "或 0805 0Ω", "5V Select，必须短接", "bridge"),
        (2, ["D2"], "SS34 二极管", "SMA · C8678", "色环 → V+（朝下）", "smd"),
        (3, ["C14"], "100nF 钽电容", "A 型 3216 · C7173", "色条 = 正极 → 5V", "smd"),
        (4, ["C10"], "220µF 16V 电解", "6.3mm · C2887273", "＋ 朝上（V+）", "smd"),
        (5, ["SW1"], "拨动开关", "C136719", "眉毛板可不焊", "th"),
        (6, ["J1", "J2", "J3"], "2x3 排针", "C32713276", "每竖列一个舵机：S ＋ −", "th"),
        (7, ["U1"], "XH2.54 2P 弯插座", "C493111", "装在背面！正面焊", "bottom"),
        (8, ["H1", "H2"], "1x20 排母", "淘宝", "USB 朝上，插 Pico H", "th"),
    ],
    skip=["C11", "U2", "C13", "CN1", "CN2", "H3", "12VLED", "5VLED", "R1", "R2"],
    pol=[("D2.1", "K 色环"), ("C14.1", "＋"), ("C10.1", "＋"), ("U1.2", "VIN"), ("U1.1", "GND"), ("H1.1", "USB 端")],
    rows=[("J1.1", "S"), ("J1.3", "＋"), ("J1.5", "−")],
)
MOUTH = dict(
    title="嘴部板（做 1 块）", file="ProDoc_Mouth Board_2025-04-16.epro",
    items=[
        (1, ["D1", "D2"], "SS1045 二极管", "SMB · C2903947", "色环朝下（远离 5V）", "smd"),
        (2, ["U2"], "AMS1117-5.0", "SOT-223 · C18212701", "散热片也要焊", "smd"),
        (3, ["C2", "C3", "C5", "C7", "C8"], "220µF 10V 电解", "6.3mm · C72494", "＋ 朝左，C8 朝右！", "smd"),
        (4, ["C1"], "1000µF 16V 电解", "10mm · C3359", "＋ 朝左（V+）", "smd"),
        (5, ["SW1"], "拨动开关", "C136719", "GP28", "th"),
        (6, ["BOARD POWER"], "2P 排针 + 跳线帽", "C157909", "插帽才给 Pico 供电", "th"),
        (7, ["U3", "U4", "U5", "U6", "U7", "U8"], "2x3 排针", "C7501274", "每竖列一个舵机：S ＋ −", "th"),
        (8, ["U1"], "XT60 母座", "C428722", "380–400°C，大烙铁头", "th"),
        (9, ["U9", "U10"], "2x20 排母", "C2977589", "Pico 插里侧两排", "th"),
    ],
    skip=["H1", "CN1", "CN2", "LED1", "R1"],
    pol=[("D1.1", "K 色环"), ("D2.1", "K 色环"), ("C1.1", "＋"), ("C2.1", "＋"), ("C3.1", "＋"), ("C5.1", "＋"),
         ("C7.1", "＋"), ("C8.1", "＋"), ("U1.3", "＋5V"), ("U1.4", "−")],
    rows=[("U3.1", "S"), ("U3.3", "＋"), ("U3.5", "−")],
)
CIRC = "①②③④⑤⑥⑦⑧⑨⑩"
KIND_NAME = {"smd": "贴片", "th": "插件", "bridge": "短接", "bottom": "插件 · 背面"}

def esc(s):
    return html.escape(str(s))

def pts_d(pts, closed=True):
    s = "M" + "L".join(f"{x:.1f},{-y:.1f}" for x, y in pts)
    return s + ("Z" if closed else "")

def render(cfg):
    b = build(os.path.join(PCB, cfg["file"]))
    comps = {c["ref"]: c for c in b["comps"]}
    kind_of, num_of = {}, {}
    for n, refs, *_r, k in cfg["items"]:
        for r in refs:
            kind_of[r], num_of[r] = k, n
    for r in cfg["skip"]:
        kind_of[r] = "skip"

    xs = [p[0] for o in b["outline"] for p in o["pts"]]
    ys = [-p[1] for o in b["outline"] for p in o["pts"]]
    bx0, bx1, by0, by1 = min(xs), max(xs), min(ys), max(ys)
    cxm = (bx0 + bx1) / 2
    g = []  # svg 片段

    # 板子：外框 + 圆孔（evenodd）
    d = " ".join(pts_d(o["pts"]) for o in b["outline"])
    g.append(f'<path d="{d}" class="board" fill-rule="evenodd"/>')
    for t in b["tracks"]:
        if t["layer"] in (1, 2):
            x1, y1, x2, y2 = t["p"]
            g.append(f'<line x1="{x1}" y1="{-y1}" x2="{x2}" y2="{-y2}" class="trk{t["layer"]}" stroke-width="{t["w"]}"/>')
    for s in b["silk"]:
        if s["layer"] == 3:
            g.append(f'<path d="{pts_d(s["pts"], s["closed"])}" class="silk"/>')

    # 元件
    for c in b["comps"]:
        k = kind_of.get(c["ref"], "other")
        cls = f"k-{k}"
        if c["layer"] == 1:
            for s in c["silk"]:
                g.append(f'<path d="{pts_d(s["pts"], s["closed"])}" class="silk"/>')
        for bd in c["body"]:
            g.append(f'<path d="{pts_d(bd["pts"], True)}" class="body {cls}{" back" if c["layer"] == 2 else ""}"/>')
        for p in c["pads"]:
            g.append(f'<path d="{pts_d(p["pts"])}" class="pad {cls}"><title>{esc(c["ref"])}.{esc(p["num"])} {esc(p["net"])}</title></path>')
            if p["hole"]:
                r = min(p["hole"]["w"], p["hole"]["h"]) / 2
                g.append(f'<circle cx="{p["x"]}" cy="{-p["y"]}" r="{r}" class="hole"/>')
        if k == "skip":
            x0, y0, x1, y1 = c["bbox"]
            g.append(f'<rect x="{x0 - 10}" y="{-y1 - 10}" width="{x1 - x0 + 20}" height="{y1 - y0 + 20}" class="skipbox"/>'
                     f'<path d="M{x0},{-y1}L{x1},{-y0}M{x1},{-y1}L{x0},{-y0}" class="skipx"/>')

    pad = {f'{c["ref"]}.{p["num"]}': (c, p) for c in b["comps"] for p in c["pads"]}
    # 极性标记：沿“元件中心 → 焊盘”方向往外放文字
    for key, txt in cfg["pol"]:
        c, p = pad[key]
        px, py = p["x"], -p["y"]
        g.append(f'<path d="{pts_d(p["pts"])}" class="polring"/>')
    # 排针行标
    for key, txt in cfg["rows"]:
        c, p = pad[key]
        g.append(f'<text x="{p["x"] - 62}" y="{-p["y"] + 16}" class="rowtag" text-anchor="end">{esc(txt)}</text>')

    # 引线标注：左右两栏
    labels = []
    info = {r: it for it in cfg["items"] for r in it[1]}
    for ref, k in kind_of.items():
        c = comps[ref]
        x0, y0, x1, y1 = c["bbox"]
        ax, ay = (x0 + x1) / 2, -(y0 + y1) / 2
        side = -1 if ax < cxm else 1
        edge_x = x0 if side < 0 else x1
        labels.append(dict(ref=ref, k=k, cx=ax, ax=edge_x, ay=ay, side=side, h=78 if k == "skip" else 150, bb=(x0, x1)))
    # 一侧标注太多时按 x 中位数重新分左右，让两栏高度接近
    hl = sum(l["h"] for l in labels if l["side"] < 0)
    hr = sum(l["h"] for l in labels if l["side"] > 0)
    if max(hl, hr) > 1.5 * max(min(hl, hr), 1):
        srt = sorted(labels, key=lambda l: l["cx"])
        half, acc = sum(l["h"] for l in labels) / 2, 0
        for l in srt:
            l["side"] = -1 if acc < half else 1
            acc += l["h"]
            l["ax"] = l["bb"][0] if l["side"] < 0 else l["bb"][1]
    # 极性文字也放进标注（跟在元件标注里）
    poltxt = {}
    for key, txt in cfg["pol"]:
        poltxt.setdefault(key.split(".")[0], []).append(f'{key.split(".")[1]} 脚 = {txt}')

    colx = {-1: bx0 - 170, 1: bx1 + 170}
    LW = 1150
    ext0, ext1 = by0, by1
    for side in (-1, 1):
        col = sorted([l for l in labels if l["side"] == side], key=lambda l: l["ay"])
        if not col:
            continue
        tot = sum(l["h"] for l in col)
        # 先按锚点排，再往下推开；整体超出时上移
        y = None
        for l in col:
            want = l["ay"] - l["h"] / 2
            y = want if y is None else max(want, y)
            l["y"] = y
            y += l["h"]
        over = col[-1]["y"] + col[-1]["h"] - (by1 + 60)
        if over > 0:
            for l in reversed(col):
                l["y"] -= over
                nxt = l
            for i in range(len(col) - 1, 0, -1):
                if col[i - 1]["y"] + col[i - 1]["h"] > col[i]["y"]:
                    col[i - 1]["y"] = col[i]["y"] - col[i - 1]["h"]
        ext0 = min(ext0, col[0]["y"] - 20)
        ext1 = max(ext1, col[-1]["y"] + col[-1]["h"])

    for l in labels:
        side, k, ref = l["side"], l["k"], l["ref"]
        lx = colx[side]
        ty = l["y"] + 50
        anchor = "end" if side < 0 else "start"
        ly = l["y"] + (28 if k == "skip" else 40)
        g.append(f'<path d="M{l["ax"]},{l["ay"]}L{lx - side * 60},{ly}L{lx - side * 10},{ly}" class="lead lead-{k}"/>'
                 f'<circle cx="{l["ax"]}" cy="{l["ay"]}" r="14" class="dot dot-{k}"/>')
        if k == "skip":
            g.append(f'<text x="{lx}" y="{ty - 10}" text-anchor="{anchor}" class="lbl-skip">{esc(ref)} 不焊</text>')
            continue
        n, refs, name, part, note, _ = info[ref]
        extra = "；".join(poltxt.get(ref, []))
        g.append(f'<text x="{lx}" y="{ty}" text-anchor="{anchor}" class="lbl"><tspan class="num n-{k}">{CIRC[n - 1]}</tspan> '
                 f'<tspan class="ref">{esc(ref)}</tspan> {esc(name)}</text>'
                 f'<text x="{lx}" y="{ty + 58}" text-anchor="{anchor}" class="sub{" warnt" if k == "bottom" else ""}">'
                 f'{esc(extra or note)}</text>')

    vx0 = colx[-1] - LW
    vx1 = colx[1] + LW
    vy0, vy1 = ext0 - 60, ext1 + 60
    svg = (f'<svg viewBox="{vx0:.0f} {vy0:.0f} {vx1 - vx0:.0f} {vy1 - vy0:.0f}" xmlns="http://www.w3.org/2000/svg" '
           f'role="img" aria-label="{esc(cfg["title"])} 焊接一览图">' + "".join(g) + "</svg>")

    # 清单表
    rows = []
    for n, refs, name, part, note, k in cfg["items"]:
        rows.append(f'<tr><td><span class="badge n-{k}">{CIRC[n - 1]}</span></td><td><b>{esc(" ".join(refs))}</b></td>'
                    f'<td>{esc(name)}<div class="muted">{esc(part)}</div></td><td><span class="tag t-{k}">{KIND_NAME[k]}</span></td>'
                    f'<td class="num">{len(refs)}</td><td>{esc(note)}</td><td><input type="checkbox" aria-label="已清点"></td></tr>')
    rows.append(f'<tr class="skiprow"><td>✕</td><td colspan="6"><b>不焊：</b>{esc("、".join(cfg["skip"]))}</td></tr>')
    table = ('<table><thead><tr><th>序</th><th>位号</th><th>元件</th><th>类型</th><th>每块</th><th>注意</th><th>✓</th></tr></thead>'
             f'<tbody>{"".join(rows)}</tbody></table>')
    return f'<section><h2>{esc(cfg["title"])}</h2><div class="fig">{svg}</div>{table}</section>'

PAGE = """<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>元件焊接一览</title>
<style>
:root{--bg:#f6f5f1;--fg:#1d1d1f;--muted:#6b6b70;--card:#fff;--line:#e2e0da;
 --board:#1f5f3f;--trk1:#2f8a5a;--trk2:#2a6e7c;--silk:#f3f3ee;--pad:#b9b3a3;--hole:#f6f5f1;
 --smd:#2f7de1;--th:#1f9d55;--bridge:#e8890c;--bottom:#9b51e0;--skip:#d64545;--pol:#ff3b30}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#141416;--fg:#ececec;--muted:#9a9aa0;--card:#1e1e22;--line:#2e2e34;
 --board:#173f2c;--trk1:#24694a;--trk2:#22566a;--silk:#d9d9d2;--pad:#8a8576;--hole:#141416;--smd:#5aa0ff;--th:#3ccf7f;--bridge:#ffad3b;--bottom:#c08cff;--skip:#ff6b6b;--pol:#ff6159}}
:root[data-theme=dark]{--bg:#141416;--fg:#ececec;--muted:#9a9aa0;--card:#1e1e22;--line:#2e2e34;
 --board:#173f2c;--trk1:#24694a;--trk2:#22566a;--silk:#d9d9d2;--pad:#8a8576;--hole:#141416;--smd:#5aa0ff;--th:#3ccf7f;--bridge:#ffad3b;--bottom:#c08cff;--skip:#ff6b6b;--pol:#ff6159}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 -apple-system,"PingFang SC","Hiragino Sans GB",sans-serif}
main{max-width:1180px;margin:0 auto;padding:24px 16px 60px}
h1{font-size:24px;margin:0 0 4px}h2{font-size:19px;margin:0 0 12px}
.lead-p{color:var(--muted);margin:0 0 16px}
.legend{display:flex;flex-wrap:wrap;gap:8px 18px;margin:0 0 20px;font-size:14px}
.legend span{display:inline-flex;align-items:center;gap:6px}
.sw{width:14px;height:14px;border-radius:3px;display:inline-block}
section{background:var(--card);border:1px solid var(--line);border-radius:14px;padding:18px;margin:0 0 22px}
.fig svg{width:100%;height:auto;display:block;max-height:92vh}
.board{fill:var(--board)}
.trk1{stroke:var(--trk1);stroke-linecap:round;opacity:.55}.trk2{stroke:var(--trk2);stroke-linecap:round;opacity:.25}
.silk{fill:none;stroke:var(--silk);stroke-width:7;opacity:.55}
.pad{fill:var(--pad)}.hole{fill:var(--hole)}
.pad.k-smd{fill:var(--smd)}.pad.k-th{fill:var(--th)}.pad.k-bridge{fill:var(--bridge)}.pad.k-bottom{fill:var(--bottom)}.pad.k-skip{fill:var(--pad);opacity:.6}
.body{fill:none;stroke-width:8}.body.k-smd{stroke:var(--smd);fill:color-mix(in srgb,var(--smd) 22%,transparent)}
.body.k-th{stroke:var(--th);fill:color-mix(in srgb,var(--th) 18%,transparent)}
.body.k-bottom{stroke:var(--bottom);stroke-dasharray:24 14;fill:color-mix(in srgb,var(--bottom) 15%,transparent)}
.body.k-skip,.body.k-other{stroke:var(--pad);opacity:.35}
.skipbox{fill:none;stroke:var(--skip);stroke-width:8;stroke-dasharray:18 12}.skipx{stroke:var(--skip);stroke-width:7;opacity:.8}
.polring{fill:none;stroke:var(--pol);stroke-width:14}
.rowtag{font-size:58px;font-weight:700;fill:#fff;paint-order:stroke;stroke:#000;stroke-width:8px}
.lead{fill:none;stroke-width:6;opacity:.8}.lead-smd{stroke:var(--smd)}.lead-th{stroke:var(--th)}.lead-bridge{stroke:var(--bridge)}.lead-bottom{stroke:var(--bottom)}.lead-skip{stroke:var(--skip);stroke-dasharray:14 10;opacity:.6}
.dot-smd{fill:var(--smd)}.dot-th{fill:var(--th)}.dot-bridge{fill:var(--bridge)}.dot-bottom{fill:var(--bottom)}.dot-skip{fill:var(--skip)}
.lbl{font-size:64px;font-weight:600;fill:var(--fg)}.lbl .ref{font-weight:800}
.num{font-weight:800}.n-smd{fill:var(--smd);color:var(--smd)}.n-th{fill:var(--th);color:var(--th)}.n-bridge{fill:var(--bridge);color:var(--bridge)}.n-bottom{fill:var(--bottom);color:var(--bottom)}
.sub{font-size:50px;fill:var(--muted)}.warnt{fill:var(--bottom);font-weight:700}
.lbl-skip{font-size:48px;fill:var(--skip)}
table{width:100%;border-collapse:collapse;margin-top:14px;font-size:14px}
th,td{border-bottom:1px solid var(--line);padding:7px 6px;text-align:left;vertical-align:top}
th{color:var(--muted);font-weight:600}td.num{text-align:center}
.muted{color:var(--muted);font-size:12.5px}
.badge{font-size:20px;font-weight:800}
.tag{font-size:12px;padding:1px 7px;border-radius:99px;color:#fff;white-space:nowrap}
.t-smd{background:var(--smd)}.t-th{background:var(--th)}.t-bridge{background:var(--bridge)}.t-bottom{background:var(--bottom)}
.skiprow td{color:var(--skip)}
input[type=checkbox]{width:18px;height:18px}
.notes{font-size:14px;color:var(--muted)}.notes b{color:var(--fg)}
@media (max-width:640px){th:nth-child(4),td:nth-child(4){display:none}section{padding:12px}}
@media print{body{background:#fff}section{break-inside:avoid;border:none}}
</style></head><body><main>
<h1>元件焊接一览图</h1>
<p class="lead-p">正面俯视图，比例 1:1，取自嘉立创工程文件里的焊盘坐标。圈号 = 建议焊接顺序：先贴片后插件，先矮后高。分步动画见 <code>焊接流程.html</code>。</p>
<div class="legend">
<span><i class="sw" style="background:var(--smd)"></i>贴片</span>
<span><i class="sw" style="background:var(--th)"></i>插件（正面插、背面焊）</span>
<span><i class="sw" style="background:var(--bridge)"></i>焊锡短接</span>
<span><i class="sw" style="background:var(--bottom)"></i>装在背面（正面焊）</span>
<span><i class="sw" style="border:2px dashed var(--skip)"></i>不焊</span>
<span><i class="sw" style="border:3px solid var(--pol)"></i>极性 / 关键脚</span>
</div>
__BOARDS__
<p class="notes"><b>极性口诀：</b>二极管色环 = 负极（K）；铝电解电容罐顶黑色半月 = 负极，底座切角 = 正极；<b>钽电容色条 = 正极</b>（和电解电容相反）。<br>
<b>电源：</b>只能接 5.0–5.1V，超过 5.5V 会烧 Pico。</p>
</main></body></html>"""

if __name__ == "__main__":
    body = render(EYE) + render(MOUTH)
    open(OUT, "w", encoding="utf-8").write(PAGE.replace("__BOARDS__", body))
    print(OUT, f"{os.path.getsize(OUT) / 1024:.0f} KB")
