"""把 ROG 上的调试日志生成 docs/表情调试日志.html。

  .venv/bin/python scripts/build_tune_log.py

日志来自 scripts/tune.py，这里只负责展示，不编内容。
"""
import html
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from tune_server import expression_steps  # noqa: E402
from head.expressions import EXPRESSIONS  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
LOG = ROOT / "outputs" / "tune_log.jsonl"
OUT = ROOT / "docs" / "表情调试日志.html"

# 从下到上的测试顺序，和 docs/舵机接线与上电检查.html 的嘴部图一致
ORDER = [
    ("TON", "舌头"), ("LLL", "下唇"), ("LLR", "下唇"), ("CLL", "嘴角前后"), ("CLR", "嘴角前后"),
    ("JL", "下巴"), ("JR", "下巴"), ("CUL", "嘴角上下"), ("CUR", "嘴角上下"),
    ("LUL", "上唇"), ("LUR", "上唇"),
    ("LO", "眉外侧"), ("RO", "眉外侧"), ("LI", "眉内侧"), ("RI", "眉内侧"),
    ("BL", "下眼皮"), ("BR", "下眼皮"), ("TL", "上眼皮"), ("TR", "上眼皮"),
    ("LR", "眼球左右"), ("UD", "眼球上下"),
]

CSS = """
:root{--bg:#f7f6f2;--card:#fff;--ink:#1f2328;--dim:#667;--line:#e2e0d8;--ok:#1a7f4b;--bad:#c0392b;--info:#2f6fb0}
@media (prefers-color-scheme:dark){:root{--bg:#16181c;--card:#1f2228;--ink:#e8e8e6;--dim:#99a;--line:#33363d;--ok:#4cc38a;--bad:#ff7b6b;--info:#6fb1f0}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--ink);font:15px/1.6 -apple-system,"PingFang SC",sans-serif}
main{max-width:860px;margin:0 auto;padding:24px 16px 64px}h1{font-size:24px;margin:0 0 4px}h2{font-size:18px;margin:32px 0 10px}
.dim{color:var(--dim)}.card{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:12px 14px;margin:8px 0;overflow-x:auto}
table{border-collapse:collapse;width:100%}th,td{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);white-space:nowrap}
td.wrap{white-space:normal}code{font:13px ui-monospace,Menlo,monospace}
.ok{color:var(--ok)}.bad{color:var(--bad)}.info{color:var(--info)}
.row{display:flex;gap:10px;padding:5px 0;border-bottom:1px solid var(--line)}.row:last-child{border:0}.t{color:var(--dim);font-size:12px;flex:none;width:62px;padding-top:2px}
ol{margin:6px 0;padding-left:22px}
"""


def fetch():
    LOG.parent.mkdir(exist_ok=True)
    subprocess.run(["scp", "-q", "rog:/srv/robot-head/outputs/tune_log.jsonl", str(LOG)], check=True)
    return [json.loads(x) for x in LOG.read_text().splitlines() if x.strip()]


def esc(x):
    return html.escape(str(x))


def status_table(rows):
    state = {n: {"status": "", "text": "", "range": ""} for n, _ in ORDER}
    for r in rows:
        if r["type"] == "note" and r["servo"] in state:
            state[r["servo"]].update(status=r["status"], text=r["text"])
        if r["type"] == "range" and r["servo"] in state:
            state[r["servo"]]["range"] = f'{r["lo"]:g}–{r["hi"]:g}'
    mark = {"ok": '<span class="ok">通过</span>', "bad": '<span class="bad">有问题</span>',
            "info": '<span class="info">测试中</span>', "": '<span class="dim">未测</span>'}
    body = "".join(
        f'<tr><td><code>{n}</code></td><td>{part}</td><td>{mark[state[n]["status"]]}</td>'
        f'<td>{state[n]["range"] or "—"}</td><td class="wrap">{esc(state[n]["text"])}</td></tr>'
        for n, part in ORDER)
    return f"<table><tr><th>舵机</th><th>部位</th><th>状态</th><th>实测范围</th><th>最新观察</th></tr>{body}</table>"


def timeline(rows):
    out = []
    for r in rows:
        t = r["t"][11:19]
        if r["type"] == "cmd":
            out.append(f'<div class="row"><span class="t">{t}</span><span><code>{esc(r["cmd"])}</code> '
                       f'<span class="dim">→ {esc(r["reply"])}</span></span></div>')
        elif r["type"] == "note":
            out.append(f'<div class="row"><span class="t">{t}</span><span class="{r["status"]}">'
                       f'{esc(r["servo"])}：{esc(r["text"])}</span></div>')
        elif r["type"] == "range":
            out.append(f'<div class="row"><span class="t">{t}</span><span>{esc(r["servo"])} 实测范围 '
                       f'{r["lo"]:g}–{r["hi"]:g}</span></div>')
    return "".join(out)


def recipes(rows):
    items = [r for r in rows if r["type"] == "recipe"]
    if not items:
        return '<p class="dim">还没有验证过的表情。舵机逐个通过后，这里按步骤记录表情是怎么做出来的。</p>'
    return "".join(
        f'<div class="card"><b>{esc(r["name"])}</b> <span class="dim">{esc(r["text"])}</span><ol>'
        + "".join(f"<li><code>{esc(s)}</code></li>" for s in r["steps"]) + "</ol></div>"
        for r in items)


def presets():
    head = "<tr><th>表情</th><th>舵机转动，按顺序一组一组走（强度 1.0）</th></tr>"
    body = "".join(
        f'<tr><td><code>{esc(n)}</code></td><td class="wrap">'
        + "<br>".join(f'{esc(s["label"])}：' + "，".join(f"{k} {v:g}°" for k, v in s["goal"].items())
                      for s in expression_steps(n, 1.0))
        + "</td></tr>" for n in EXPRESSIONS)
    return f"<table>{head}{body}</table>"


rows = fetch()
done = sum(1 for n, _ in ORDER if any(r["type"] == "note" and r["servo"] == n and r["status"] == "ok" for r in rows))
page = f"""<!doctype html><html lang="zh"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>表情调试日志</title><style>{CSS}</style></head>
<body><main><h1>表情调试日志</h1>
<p class="dim">机器人头逐个舵机的实测过程，从下到上。已通过 {done} / {len(ORDER)} 个舵机。最后记录：{esc(rows[-1]["t"])}</p>
<h2>表情是怎么做出来的</h2>{recipes(rows)}
<h2>表情预设</h2><p class="dim">角度已含 UD 补偿。数值是手估的，要对着实物调。</p><div class="card">{presets()}</div>
<h2>舵机进度</h2><div class="card">{status_table(rows)}</div>
<h2>过程记录</h2><div class="card">{timeline(rows)}</div>
</main></body></html>"""
OUT.write_text(page)
print(OUT)
