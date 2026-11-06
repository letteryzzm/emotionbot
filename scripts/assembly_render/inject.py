"""把 steps_fragment.html 插进 docs/ 里的 组装流程.html（<!--STEPS-BEGIN--> 和 <!--STEPS-END--> 之间）"""
import os, re
HERE = os.path.dirname(os.path.abspath(__file__))
FRAG = os.path.join(HERE, '../../outputs/assembly/steps_fragment.html')
NOTE = os.path.join(os.path.dirname(os.path.abspath(__file__)), '../../docs/组装流程.html')
CSS = """
/*FIG3D*/
.fig3d{margin:8px 0;border-radius:10px;overflow:hidden;background:#fafaf7;border:1px solid var(--line)}
.fig3d svg{width:100%;height:auto;display:block}
.exl{stroke:#3a3a3a;stroke-width:1.4;stroke-dasharray:5 4;fill:none}.exd{fill:#3a3a3a}
.lbc{stroke:#fff;stroke-width:2}.lbt{fill:#fff!important;font-size:13px;font-weight:800;text-anchor:middle;dominant-baseline:central}
.ins{fill:#e0a526;stroke:#5a3d00;stroke-width:1.5}.inst{font-size:13px;font-weight:800;fill:#5a3d00!important;paint-order:stroke;stroke:#fff;stroke-width:3px}
.stp{border-left:4px solid var(--mech)}.stp h3{margin:0 0 6px;font-size:17px}.stp h3 input{width:18px;height:18px;vertical-align:-3px}
table.sc .lb{display:inline-block;width:20px;height:20px;border-radius:50%;color:#fff;text-align:center;font-weight:800;line-height:20px;font-size:12px}
.legend2{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:13.5px;margin:8px 0 0}.legend2 span{display:inline-flex;align-items:center;gap:6px}
"""
INTRO = """<section><h2>图解（按装配顺序）</h2>
<p>图都是从原作者的参考装配模型直接渲染的，零件位置和螺丝方向都是真实的。螺丝画成"拔出来"的样子：<b>虚线 = 螺丝要走的路径，虚线末端的小黑点 = 螺丝头最后停的位置</b>。被挡住的螺丝画成半透明。</p>
<div class="legend2">
<span><i class="sw" style="background:#99bdeb"></i>螺丝拧进去的零件（里面有热熔螺母）</span>
<span><i class="sw" style="background:#9ed99e"></i>被压住 / 转动的零件</span>
<span><i class="sw" style="background:#545966"></i>舵机</span>
<span><i class="sw" style="background:#e0e0db"></i>只作参照的零件</span>
<span><i class="sw" style="background:#e0a526;border-radius:50%"></i>热熔螺母孔</span>
</div>
<p class="muted">左右是对称的；有些零件模型里只画了一边（比如左下颌的圆舵盘、右眉毛），装另一边时照镜像。所有尺寸、方向来自 <code>scripts/assembly_render/</code> 对装配模型的测量。</p></section>
"""
s = open(NOTE).read()
frag = open(FRAG).read()
if '/*FIG3D*/' not in s:
    s = s.replace('</style>', CSS + '</style>', 1)
if '/*FNOTE*/' not in s:
    s = s.replace('</style>', '/*FNOTE*/\n.fnote{font-size:12px;font-weight:700;fill:#1d1d1f!important;paint-order:stroke;stroke:#fff;stroke-width:3.5px}\n</style>', 1)
block = '<!--STEPS-BEGIN-->\n' + INTRO + frag + '\n<!--STEPS-END-->'
if '<!--STEPS-BEGIN-->' in s:
    s = re.sub(r'<!--STEPS-BEGIN-->.*?<!--STEPS-END-->', lambda m: block, s, flags=re.S)
else:
    anchor = '<section>\n<h2>逐步清单</h2>'
    assert anchor in s
    s = s.replace(anchor, block + '\n\n' + anchor, 1)
import json, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
FM = json.load(open(os.path.join(HERE, '../../outputs/assembly/figmap.json')))
if '/*STAGE*/' not in s:
    s = s.replace('</style>', '/*STAGE*/\na.fl{white-space:nowrap;color:inherit;text-decoration:underline}\nh2.stage{margin:34px 0 10px;padding:8px 12px;background:var(--mech);color:#fff;border-radius:8px;font-size:19px}\n</style>', 1)
# NOW 块：只换开头到“舵机回中”之前，回中步骤保留
import final_fig
now = re.sub(r'@@(\w+)@@', lambda m: str(FM[m.group(1)]), final_fig.NOW)
s = re.sub(r'<!--NOW-BEGIN-->.*?(?=<h3>舵机回中怎么做)', lambda m: '<!--NOW-BEGIN-->\n' + now, s, flags=re.S)
s = re.sub(r'<p class="muted">上颚那部分（图[^<]*</p>\n(</section>\n<!--NOW-END-->)', r'\1', s)
s = re.sub(r'台阶螺丝怎么用普通螺丝代替（图 [0-9]+、图 [0-9]+ 的替代做法）', f'台阶螺丝怎么用普通螺丝代替（图 {FM["s3"]}、图 {FM["s4"]} 的替代做法）', s)
s = re.sub(r'嘴唇、嘴角转轴 ×14（图 [0-9]+）', f'嘴唇、嘴角转轴 ×14（图 {FM["s3"]}）', s)
s = re.sub(r'上唇、下唇大转轴 ×4（图 [0-9]+）', f'上唇、下唇大转轴 ×4（图 {FM["s4"]}）', s)
s = s.replace("document.querySelectorAll('.step input')", "document.querySelectorAll('input[data-k]')")
open(NOTE, 'w').write(s)
print('ok', len(s) // 1024, 'KB')
