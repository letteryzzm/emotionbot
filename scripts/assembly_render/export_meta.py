"""导出每个 group 实例的元数据（名字、质心 mm、模块、中文名、螺丝方向、属于哪些步骤）给 Blender 脚本用。"""
import json, os, sys
import numpy as np
HERE = os.path.dirname(os.path.abspath(__file__)); sys.path.insert(0, HERE)
import build_steps as B  # noqa: E402

S = B.S
MOD = {}
for g in [0, 7, 9, 10, 26, 27, 63]: MOD[g] = '00 头骨 外壳 颧骨'
for g in B.EYE + B.EYE_SERVO + B.EYEBALL: MOD[g] = '01 眼部机构'
for g in B.BROW + B.BROW_SERVO: MOD[g] = '02 眉毛机构'
for g in [188, 113, 172, 111, 96, 161] + B.MG996 + B.MOUTH_SERVO_TOP + B.MOUTH_SERVO_JAW + [102, 151, 129, 162]: MOD[g] = '03 嘴部 结构'
for g in B.LIP_PARTS: MOD[g] = '04 嘴部 嘴唇连杆'
for g in B.TEETH: MOD[g] = '05 牙齿 舌头'
CN = {'SkullFrame': '头骨框架', 'RearPlate': '后盖', 'RearVent': '后格栅', 'FrontVent': '前格栅', 'FrontPlate': '额头装饰条',
      'FanBracket': '风扇支架', 'CheekBone': '颧骨', 'TopBase': '上颌座', 'JawBase': '下颌座', 'JawLink': '右下颌连杆',
      'Part 33': '左下颌连杆', 'Component1': 'MG996R圆舵盘', 'Component2': 'MG996R', 'MG996R v6': 'MG996R输出轴',
      'MG90s_servo_FIX v1(Mirror)': 'MG90S', 'SG90': 'MG90S(眼)', 'Component74': '眼球', 'M4Insert': 'M4热熔螺母',
      'Chamfered plain washer normal M5': 'M5平垫', 'Chamfered plain washer normal M4': 'M4平垫', 'Part 1': '牙齿/牙龈/舌头',
      'Part 4': '眉毛底板', 'Part 11': '软眉毛TPU', 'Part 14': '软眉毛TPU'}
steps = {}
for i, st in enumerate(B.STEPS, 1):
    name = f'图{i:02d} {st["title"]}'
    mem = [g for g, _ in st['parts']] + list(st.get('context', [])) + list(st['screws'])
    for g in mem: steps.setdefault(g, []).append(name)
out = []
for gi, n in enumerate(S.names):
    if gi not in S.faces: continue
    c = S.pts(gi).mean(0)
    rec = dict(gi=gi, name=n, c=c.round(3).tolist(), steps=steps.get(gi, []))
    if n.startswith('Hex') or 'Shoulder' in n:
        h, t, a, _ = S.screw_axis(gi)
        rec.update(screw=B.spec_label(gi), spec=B.spec_of(gi), axis=a.round(5).tolist(), module='06 螺丝')
        rec['cn'] = f'{B.spec_label(gi)} #{gi}'
    else:
        rec['module'] = MOD.get(gi, '07 其他')
        rec['cn'] = f'{CN.get(n, n.replace("Part ", "Part_"))} #{gi}'
    out.append(rec)
json.dump(dict(objs=out, step_order=[f'图{i:02d} {st["title"]}' for i, st in enumerate(B.STEPS, 1)]),
          open(os.path.join(B.OUT, 'meta.json'), 'w'), ensure_ascii=False)
print(len(out), 'objs')
