"""EasyEDA Pro (.epro) PCB -> 几何数据 + SVG 片段。

只用标准库。.epro 是 zip，里面 PCB/*.epcb 和 FOOTPRINT/*.efoo 都是 JSON Lines。
坐标单位 mil，Y 轴向上；输出 SVG 时翻转成 Y 向下。

用法: python -I epro_geom.py <xxx.epro> <out.json>
"""
import json, math, sys, zipfile, collections

def jl(text):
    out = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            a = json.loads(line)
        except Exception:
            continue
        if a:
            out.append(a)
    return out

# ---------- 路径解析 ----------
def parse_path(p):
    """EasyEDA 路径 -> 若干条折线(点列表, closed)。ARC 按逆时针为正角度采样。"""
    if not p:
        return []
    if isinstance(p[0], list):           # FILL: 多个子路径
        res = []
        for sub in p:
            res += parse_path(sub)
        return res
    if isinstance(p[0], str):
        kind = p[0]
        if kind == "CIRCLE":
            cx, cy, r = p[1:4]
            return [([(cx + r * math.cos(t), cy + r * math.sin(t))
                      for t in [i * 2 * math.pi / 36 for i in range(36)]], True, ("circle", cx, cy, r))]
        if kind == "R":
            x, y, w, h = p[1:5]
            return [([(x, y), (x + w, y), (x + w, y - h), (x, y - h)], True, None)]
        raise ValueError(p)
    pts = [(p[0], p[1])]
    i, mode = 2, None
    while i < len(p):
        t = p[i]
        if isinstance(t, str):
            mode = t
            i += 1
            continue
        if mode == "L":
            pts.append((p[i], p[i + 1])); i += 2
        elif mode == "ARC":
            ang, x2, y2 = p[i], p[i + 1], p[i + 2]; i += 3
            x1, y1 = pts[-1]
            pts += arc_pts(x1, y1, x2, y2, ang)
        else:
            raise ValueError(f"unknown token {mode}")
    closed = len(pts) > 2 and abs(pts[0][0] - pts[-1][0]) < 1e-6 and abs(pts[0][1] - pts[-1][1]) < 1e-6
    return [(pts, closed, None)]

def arc_pts(x1, y1, x2, y2, ang):
    th = math.radians(ang)
    if abs(th) < 1e-9:
        return [(x2, y2)]
    c = math.hypot(x2 - x1, y2 - y1)
    r = c / (2 * math.sin(abs(th) / 2))
    mx, my = (x1 + x2) / 2, (y1 + y2) / 2
    d = math.sqrt(max(r * r - (c / 2) ** 2, 0))
    ux, uy = (x2 - x1) / c, (y2 - y1) / c
    s = 1 if th > 0 else -1
    if abs(th) > math.pi:
        s = -s
    cx, cy = mx - s * uy * d, my + s * ux * d
    a0 = math.atan2(y1 - cy, x1 - cx)
    n = max(4, int(abs(ang) / 10))
    return [(cx + r * math.cos(a0 + th * k / n), cy + r * math.sin(a0 + th * k / n)) for k in range(1, n + 1)]

# ---------- 变换 ----------
def make_tf(cx, cy, rot, mirror):
    a = math.radians(rot)
    ca, sa = math.cos(a), math.sin(a)
    def tf(x, y):
        if mirror:          # 底层元件：上下翻转（由 XH 座的焊盘网络和外壳朝向验证）
            y = -y
        return (cx + x * ca - y * sa, cy + x * sa + y * ca)
    return tf

def pad_outline(shape, w, h, rr=0):
    """焊盘本地外形(以焊盘中心为原点)"""
    if shape == "RECT":
        return [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    # ELLIPSE / OVAL: 跑道形
    pts = []
    if abs(w - h) < 1e-6 or shape == "ELLIPSE":
        rx, ry = w / 2, h / 2
        return [(rx * math.cos(t), ry * math.sin(t)) for t in [i * 2 * math.pi / 32 for i in range(32)]]
    if w > h:
        r = h / 2; l = w / 2 - r
        for k in range(17):
            t = -math.pi / 2 + math.pi * k / 16; pts.append((l + r * math.cos(t), r * math.sin(t)))
        for k in range(17):
            t = math.pi / 2 + math.pi * k / 16; pts.append((-l + r * math.cos(t), r * math.sin(t)))
    else:
        r = w / 2; l = h / 2 - r
        for k in range(17):
            t = math.pi * k / 16; pts.append((r * math.cos(t), l + r * math.sin(t)))
        for k in range(17):
            t = math.pi + math.pi * k / 16; pts.append((r * math.cos(t), -l + r * math.sin(t)))
    return pts

FLIP_LAYER = {1: 2, 2: 1, 3: 4, 4: 3, 5: 6, 6: 5, 7: 8, 8: 7, 9: 10, 10: 9}

def r2(v):
    return round(v, 2)

def poly_out(pts):
    return [[r2(x), r2(y)] for x, y in pts]

# ---------- 主流程 ----------
def load(epro):
    z = zipfile.ZipFile(epro)
    names = z.namelist()
    proj = json.loads(z.read("project.json"))
    pcb_name = [n for n in names if n.startswith("PCB/") and n.endswith(".epcb")][0]
    pcb = jl(z.read(pcb_name).decode("utf-8"))
    foots = {}
    for n in names:
        if n.startswith("FOOTPRINT/") and n.endswith(".efoo"):
            foots[n.split("/")[1][:-5]] = jl(z.read(n).decode("utf-8"))
    return proj, pcb, foots

def build(epro):
    proj, pcb, foots = load(epro)
    devices = proj.get("devices", {})
    fp_title = {k: v.get("title") for k, v in proj.get("footprints", {}).items()}

    comps, attrs, padnet = {}, collections.defaultdict(dict), collections.defaultdict(dict)
    attr_pos = collections.defaultdict(dict)
    tracks, vias, outline, silk_polys, silk_text = [], [], [], [], []
    for a in pcb:
        k = a[0]
        if k == "COMPONENT":
            comps[a[1]] = dict(layer=a[3], x=a[4], y=a[5], rot=a[6])
        elif k == "ATTR":
            attrs[a[3]][a[7]] = a[8]
            if a[7] == "Designator":
                attr_pos[a[3]] = dict(layer=a[4], x=a[5], y=a[6], size=a[12], rot=a[17], show=a[10])
        elif k == "PAD_NET":
            padnet[a[1]][a[2]] = a[3]
        elif k == "LINE":
            tracks.append(dict(net=a[3], layer=a[4], p=[r2(a[5]), r2(a[6]), r2(a[7]), r2(a[8])], w=r2(a[9])))
        elif k == "VIA":
            vias.append(dict(net=a[3], x=r2(a[5]), y=r2(a[6]), d=r2(a[8]) if isinstance(a[8], (int, float)) else 24,
                             raw=a[:12]))
        elif k == "POLY":
            for pts, closed, circ in parse_path(a[6]):
                if a[4] == 11:
                    outline.append(dict(pts=poly_out(pts), closed=closed, circle=circ))
                elif a[4] in (3, 4):
                    silk_polys.append(dict(layer=a[4], pts=poly_out(pts), closed=closed, w=a[5]))
        elif k == "STRING" and a[3] in (3, 4):
            silk_text.append(dict(layer=a[3], x=r2(a[4]), y=r2(a[5]), text=a[6], size=a[8], rot=a[13]))

    out_comps = []
    for cid, c in comps.items():
        at = attrs[cid]
        dev = devices.get(at.get("Device"), {})
        da = dev.get("attributes", {})
        fpid = at.get("Footprint") or da.get("Footprint")
        prims = foots.get(fpid, [])
        mirror = c["layer"] == 2
        tf = make_tf(c["x"], c["y"], c["rot"], mirror)
        L = (lambda l: FLIP_LAYER.get(l, l)) if mirror else (lambda l: l)
        pads, silk, body, marks = [], [], [], []
        for p in prims:
            if p[0] == "PAD":
                num, px, py, prot, hole, shape = p[5], p[6], p[7], p[8] or 0, p[9], p[10]
                w, h = shape[1], shape[2]
                ptf = make_tf(px, py, prot, False)
                outl = [tf(*ptf(x, y)) for x, y in pad_outline(shape[0], w, h)]
                cx, cy = tf(px, py)
                hd = None
                if hole:
                    hd = dict(kind=hole[0], w=hole[1], h=hole[2])
                pads.append(dict(num=num, net=padnet[cid].get(num, ""), x=r2(cx), y=r2(cy), pts=poly_out(outl),
                                 layer=L(p[4]), th=bool(hole), hole=hd, shape=shape[0], size=[w, h]))
            elif p[0] in ("POLY", "FILL"):
                lay = p[4]
                for pts, closed, circ in parse_path(p[6]):
                    tp = poly_out([tf(x, y) for x, y in pts])
                    item = dict(layer=L(lay), pts=tp, closed=closed or p[0] == "FILL", fill=p[0] == "FILL", w=p[5])
                    if lay in (3, 4):
                        silk.append(item)
                    elif lay == 48:
                        body.append(item)
                    elif lay == 49:
                        marks.append(item)
        allx = [x for pd in pads for x, _ in pd["pts"]] + [x for b in body for x, _ in b["pts"]]
        ally = [y for pd in pads for _, y in pd["pts"]] + [y for b in body for _, y in b["pts"]]
        bbox = [r2(min(allx)), r2(min(ally)), r2(max(allx)), r2(max(ally))] if allx else [c["x"] - 30, c["y"] - 30, c["x"] + 30, c["y"] + 30]
        out_comps.append(dict(
            ref=at.get("Designator"), layer=c["layer"], x=r2(c["x"]), y=r2(c["y"]), rot=c["rot"],
            footprint=fp_title.get(fpid), part=da.get("Manufacturer Part") or dev.get("title"),
            lcsc=da.get("Supplier Part"), pads=pads, silk=silk, body=body, marks=marks, bbox=bbox,
            label=attr_pos.get(cid)))
    return dict(outline=outline, tracks=tracks, vias=vias, silk=silk_polys, text=silk_text,
                comps=sorted(out_comps, key=lambda c: str(c["ref"])))

def check(board):
    """自检：每条走线端点应落在同网络的焊盘或过孔、或另一条走线端点上。"""
    pads = [(p["x"], p["y"], p["net"], c["ref"], p["num"], max(p["size"]) / 2) for c in board["comps"] for p in c["pads"]]
    ends = collections.defaultdict(list)
    for t in board["tracks"]:
        ends[t["net"]] += [(t["p"][0], t["p"][1]), (t["p"][2], t["p"][3])]
    hit = miss = 0
    for net, pts in ends.items():
        if not net:
            continue
        for x, y in pts:
            ok = any(n == net and math.hypot(px - x, py - y) <= r + 2 for px, py, n, *_r, r in
                     [(p[0], p[1], p[2], p[3], p[4], p[5]) for p in pads])
            hit += ok; miss += not ok
    return hit, miss

if __name__ == "__main__":
    b = build(sys.argv[1])
    h, m = check(b)
    print(f"{sys.argv[1]}: {len(b['comps'])} comps, track ends on same-net pad: {h}, elsewhere: {m}")
    json.dump(b, open(sys.argv[2], "w"), ensure_ascii=False)
