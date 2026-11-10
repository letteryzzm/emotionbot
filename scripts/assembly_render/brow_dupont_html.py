"""眉毛板 Pico 插座位焊成公排针时的杜邦线接线图 -> docs/眉毛板杜邦线接线图.html
孔位读 pcb/render/eye.json，Pico 和板子同比例，所以 5 根线都是水平线。"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
d = json.loads((ROOT / "pcb/render/eye.json").read_text())
C = {c["ref"]: c for c in d["comps"]}
S = 0.34
X0, Y0 = 1000, 1640                 # mil -> px 的原点
px = lambda x: (x + X0) * S
py = lambda y: (Y0 - y) * S
PX_L, PX_R = 400, 1100              # Pico 两列的 x（mil）
pin_y = lambda n: 1319 - (n - 1) * 100

WIRES = [  # 名字, Pico 脚, GPIO, 板上排针, 孔序号, 颜色
    ("LO", 11, "GP8", "H2", "10", "#e8590c"),
    ("LI", 12, "GP9", "H2", "9", "#f0a500"),
    ("RO", 16, "GP12", "H2", "5", "#2f9e44"),
    ("RI", 17, "GP13", "H2", "4", "#1c7ed6"),
    ("GND", 3, "GND", "H1", "3", "#222222"),
]
pad = lambda ref, num: next(p for p in C[ref]["pads"] if p["num"] == num)
o = []
for loop in d["outline"]:
    pts = " ".join(f"{px(x):.1f},{py(y):.1f}" for x, y in loop["pts"])
    o.append(f'<polygon points="{pts}" fill="#1f6f54" stroke="#0d3b2c" stroke-width="2"/>')
for ref in ("H1", "H2"):
    for p in C[ref]["pads"]:
        o.append(f'<circle cx="{px(p["x"]):.1f}" cy="{py(p["y"]):.1f}" r="7" fill="#d9c27a" stroke="#6b5a1e"/>'
                 f'<circle cx="{px(p["x"]):.1f}" cy="{py(p["y"]):.1f}" r="3" fill="#123"/>')
o.append(f'<text x="{px(-290):.0f}" y="{py(1250):.0f}" class="w" text-anchor="middle">↑ USB 这一头</text>')
o.append(f'<text x="{px(-290):.0f}" y="{py(650):.0f}" class="w" text-anchor="middle">Pico 插座位（公排针）</text>')
o.append(f'<text x="{px(-290):.0f}" y="{py(590):.0f}" class="ws" text-anchor="middle">左列 H2 · 右列 H1</text>')
# 舵机排针和舵机名
for ref, cols in (("J1", (("1", "LO"), ("2", "LI"))), ("J2", (("1", "RI"), ("2", "RO"))), ("J3", ())):
    for p in C[ref]["pads"]:
        o.append(f'<rect x="{px(p["x"]) - 7:.1f}" y="{py(p["y"]) - 7:.1f}" width="14" height="14" fill="#c9ccd1" stroke="#444"/>')
    for num, name in cols:
        p = pad(ref, num)
        if ref == "J2":
            p = {"x": p["x"]}
        ch = {"LO": ("J1", "1"), "LI": ("J1", "2"), "RI": ("J2", "1"), "RO": ("J2", "2")}[name]
        x = pad(*ch)["x"]
        o.append(f'<text x="{px(x):.1f}" y="{py(-1020):.1f}" class="w b" text-anchor="middle">{name}</text>')
for t, y in (("S", -721), ("+", -821), ("−", -921)):
    o.append(f'<text x="{px(-835):.1f}" y="{py(y) + 5:.1f}" class="ws" text-anchor="middle">{t}</text>')
for ref in ("J1", "J2", "J3"):
    o.append(f'<text x="{px(C[ref]["x"]):.1f}" y="{py(-640):.1f}" class="ws" text-anchor="middle">{ref}</text>')
o.append(f'<text x="{px(-260):.1f}" y="{py(-1020):.1f}" class="ws" text-anchor="middle">J3 不用</text>')
# 5V 入口在背面
x, y = px(-285), py(1020)
o.append(f'<rect x="{x - 56:.1f}" y="{y - 16:.1f}" width="112" height="32" rx="3" fill="none" stroke="#ffd43b" stroke-width="2" stroke-dasharray="5 3"/>'
         f'<text x="{x:.1f}" y="{y + 5:.1f}" class="ws" text-anchor="middle" fill="#ffd43b">XH 5V（背面）</text>')
# Pico
top, bot = 1319 + 130, pin_y(20) - 130
o.append(f'<rect x="{px(PX_L - 75):.1f}" y="{py(top):.1f}" width="{(PX_R - PX_L + 150) * S:.1f}" height="{(top - bot) * S:.1f}" rx="6" fill="#2f8f4e" stroke="#14532d" stroke-width="2"/>')
o.append(f'<rect x="{px(750 - 95):.1f}" y="{py(top + 45):.1f}" width="{190 * S:.1f}" height="{105 * S:.1f}" rx="3" fill="#c9ccd1" stroke="#555"/>')
o.append(f'<text x="{px(750):.1f}" y="{py(top + 75):.1f}" class="k" text-anchor="middle">USB → ROG</text>')
o.append(f'<text x="{px(750):.1f}" y="{py(900):.1f}" class="w b" text-anchor="middle">Pico</text>')
o.append(f'<text x="{px(750):.1f}" y="{py(840):.1f}" class="ws" text-anchor="middle">e6616407e3689e2a</text>')
used = {w[1] for w in WIRES}
for n in range(1, 21):
    for x, pn in ((PX_L, n), (PX_R, 41 - n)):
        hot = x == PX_L and n in used
        o.append(f'<circle cx="{px(x):.1f}" cy="{py(pin_y(n)):.1f}" r="{7 if hot else 5}" fill="{"#fff" if hot else "#d9c27a"}" stroke="#6b5a1e"/>')
# 导线
for name, pin, gp, ref, num, col in WIRES:
    p = pad(ref, num)
    x1, y1, x2, y2 = px(p["x"]), py(p["y"]), px(PX_L), py(pin_y(pin))
    o.append(f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="#fff" stroke-width="6.5"/>'
             f'<line x1="{x1:.1f}" y1="{y1:.1f}" x2="{x2:.1f}" y2="{y2:.1f}" stroke="{col}" stroke-width="4"/>'
             f'<circle cx="{x1:.1f}" cy="{y1:.1f}" r="8" fill="{col}" stroke="#fff" stroke-width="2"/>'
             f'<circle cx="{x2:.1f}" cy="{y2:.1f}" r="8" fill="{col}" stroke="#fff" stroke-width="2"/>')
    o.append(f'<text x="{px(PX_L + 55):.1f}" y="{py(pin_y(pin)) + 5:.1f}" class="k b">{pin} 脚 {gp}</text>')
# 不要接
p = (px(PX_R), py(pin_y(1)))
o.append(f'<text x="{px(PX_R + 110):.1f}" y="{p[1] + 5:.1f}" class="k" fill="#c92a2a">40 VBUS ✕ 不接</text>')
o.append(f'<text x="{px(PX_R + 110):.1f}" y="{py(pin_y(2)) + 5:.1f}" class="k" fill="#c92a2a">39 VSYS ✕ 不接</text>')
W, H = px(1900), py(-1120)
rows = "".join(
    f'<tr><td><i style="background:{c}"></i>{n}</td><td>{"左列" if r == "H2" else "右列"}第 {21 - int(k) if r == "H2" else k} 针（{r}.{k}）</td><td>第 {p} 脚 {g}</td></tr>'
    for n, p, g, r, k, c in WIRES)
html = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>眉毛板杜邦线接线图</title>
<style>body{{font:15px/1.6 -apple-system,"PingFang SC","Hiragino Sans GB",sans-serif;max-width:900px;margin:24px auto;padding:0 16px;color:#222;background:#fff}}
svg{{width:100%;height:auto;display:block}}.w{{fill:#fff;font-size:15px}}.ws{{fill:#e6f2ec;font-size:12px}}.k{{fill:#222;font-size:13px}}.b{{font-weight:700}}
table{{border-collapse:collapse;width:100%;margin:12px 0}}td,th{{border:1px solid #ccc;padding:6px 10px;text-align:left}}th{{background:#f1f3f5}}
i{{display:inline-block;width:12px;height:12px;margin-right:6px;border-radius:2px}}.n{{background:#fff4e6;border-left:4px solid #e8590c;padding:8px 12px}}</style></head><body>
<h1>眉毛板杜邦线接线图</h1>
<p>从 PCB 正面看，USB 朝上。Pico 和板子按同一比例画。Pico 插座位焊成了公排针，Pico 插不上去，用 5 根<b>母对母</b>杜邦线连接。舵机继续插 J1、J2。</p>
<svg viewBox="0 0 {W:.0f} {H:.0f}" role="img" aria-label="眉毛板和 Pico 的五根接线">{''.join(o)}</svg>
<table><tr><th>线</th><th>眉毛板排针（从 USB 这头数）</th><th>Pico</th></tr>{rows}</table>
<div class="n"><b>注意</b>
<ul><li>GND 只能接板子<b>右列第 3 针</b>。左列第 3、8、13、18 针虽然对应 Pico 的 GND 脚，但在这块板上不是地，不要用。</li>
<li>Pico 的 VBUS、VSYS 不接板子。Pico 只用 USB 供电，舵机 5V 走背面 XH 口。</li>
<li>两头都是公针，用母对母杜邦线，不用焊。插到底，线别互相拉扯。</li>
<li>接线时断开 5V。</li></ul></div>
</body></html>"""
(ROOT / "docs/眉毛板杜邦线接线图.html").write_text(html, encoding="utf-8")
