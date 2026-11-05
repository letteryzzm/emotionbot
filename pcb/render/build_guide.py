"""生成焊接指南 HTML：解析两个 .epro → 注入模板 → 写到笔记目录。

python3 -I build_guide.py
"""
import json, os, sys
HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
from epro_geom import build  # noqa: E402

PCB = os.path.dirname(HERE)
OUT = os.path.expanduser("~/Documents/zzm/note/inbound/learningnote/robotic/复现项目/head/焊接流程.html")

boards = {
    "eye": build(os.path.join(PCB, "ProDoc_Eyes_Brow_Neck_2025-04-16.epro")),
    "mouth": build(os.path.join(PCB, "ProDoc_Mouth Board_2025-04-16.epro")),
}
for b in boards.values():
    for v in b["vias"]:
        v.pop("raw", None)
tpl = open(os.path.join(HERE, "guide_template.html"), encoding="utf-8").read()
html = tpl.replace("/*__DATA__*/", json.dumps(boards, ensure_ascii=False, separators=(",", ":")))
open(OUT, "w", encoding="utf-8").write(html)
print(OUT, f"{len(html) / 1024:.0f} KB")
