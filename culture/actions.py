"""京剧和动漫的表情动作库。

每个动作是一串关键帧。关键帧写语义量，sample() 转成舵机 u。side 后缀 _l/_r 指观众看到的左右，
由 head/actuators.py 的接线标记换算成舵机名，所以这里不用关心 L/R 在眼部和嘴部含义不同。

  lid/low  上/下眼皮睁开程度 0 闭 1 全睁        bi/bo  眉内侧/外侧 0 压低 1 抬起
  smile    -1 嘴角下撇 0 平时 1 上扬             wide   嘴角宽度 0~1
  jaw      张嘴 0~1    lu/ll 上唇/下唇抬起 0~1   ton    舌头 0~1
  gx/gy    视线 -1~1，gx 正 = 观众右侧，gy 正 = 上

这些只是头部能做的部分。京剧的身段、水袖、翎子功这个头做不了，文案里不声称做到了。
"""
from dataclasses import dataclass, field

from head.actuators import (BY_NAME, EYE_BROW_L_IS_ROBOT_LEFT, LR_UP_IS_ROBOT_LEFT, MOUTH_L_IS_ROBOT_LEFT, NAMES,
                            rest_vector)

SNAP_S = 0.09
EXCLUDE = {"EXA"}
REST = dict(zip(NAMES, (float(x) for x in rest_vector())))


def _eye(side):
    """观众左右 -> 眼眉舵机名里的 L/R"""
    left_is_l = not EYE_BROW_L_IS_ROBOT_LEFT
    return ("L" if left_is_l else "R") if side == "l" else ("R" if left_is_l else "L")


def _mouth(side):
    left_is_l = not MOUTH_L_IS_ROBOT_LEFT
    return ("L" if left_is_l else "R") if side == "l" else ("R" if left_is_l else "L")


def _smile(rest, s):
    return rest + s * (1 - rest) if s >= 0 else rest * (1 + s)


def semantic_to_u(k):
    """语义量 -> {舵机: u}，没写到的舵机用 rest。"""
    u = {n: v for n, v in REST.items() if n not in EXCLUDE}
    for side in "lr":
        e, m = _eye(side), _mouth(side)
        for key, name in (("lid", f"T{e}"), ("low", f"B{e}"), ("bi", f"{e}I"), ("bo", f"{e}O"),
                          ("lu", f"LU{m}"), ("ll", f"LL{m}")):
            v = k.get(f"{key}_{side}", k.get(key))
            if v is not None:
                u[name] = v
        s = k.get(f"smile_{side}", k.get("smile"))
        if s is not None:
            u[f"CU{m}"] = _smile(REST[f"CU{m}"], s)
        w = k.get(f"wide_{side}", k.get("wide"))
        if w is not None:
            u[f"CL{m}"] = w
    if "jaw" in k:
        u["JL"] = u["JR"] = k["jaw"]
    if "ton" in k:
        u["TON"] = k["ton"]
    if "gx" in k:
        u["LR"] = 0.5 + 0.5 * k["gx"] * (1 if LR_UP_IS_ROBOT_LEFT else -1)
    if "gy" in k:
        # UD 的正前方不在 0.5：rest 带装配补偿，上下行程也不一样
        r = REST["UD"]
        u["UD"] = r + k["gy"] * ((1 - r) if k["gy"] > 0 else r)
    return {n: min(1.0, max(0.0, x)) for n, x in u.items()}


@dataclass(frozen=True)
class Frame:
    t: float
    pose: dict
    beat: str = ""
    snap: bool = False


def F(t, beat="", snap=False, **pose):
    return Frame(t, pose, beat, snap)


@dataclass(frozen=True)
class Action:
    id: str
    group: str          # opera / anime
    name: str
    use: str            # 给模型和用户看：什么图用这个动作
    note: str           # 文化说明
    skin: str           # 2D 脸的画法
    frames: tuple = field(default_factory=tuple)

    @property
    def duration(self):
        return self.frames[-1].t


def _ease(x):
    return x * x * (3 - 2 * x)


def sample(action, t, intensity=1.0):
    """返回 ({舵机: u}, 当前节拍文字)。"""
    fr = action.frames
    t = min(max(t, 0.0), action.duration)
    beat = ""
    for f in fr:
        if f.t <= t and f.beat:
            beat = f.beat
    i = max(j for j, f in enumerate(fr) if f.t <= t)
    if i == len(fr) - 1:
        cur = semantic_to_u(fr[-1].pose)
    else:
        a, b = fr[i], fr[i + 1]
        start = max(a.t, b.t - SNAP_S) if b.snap else a.t
        x = 0.0 if t <= start else (t - start) / (b.t - start)
        ua, ub = semantic_to_u(a.pose), semantic_to_u(b.pose)
        e = _ease(x)
        cur = {n: ua[n] + e * (ub[n] - ua[n]) for n in ua}
    k = min(1.0, max(0.0, float(intensity)))
    return {n: REST[n] + k * (v - REST[n]) for n, v in cur.items()}, beat


OPEN = dict(lid=1, low=1)
_A = [
    # ---- 京剧 ----
    Action("liangxiang", "opera", "威严亮相", "红脸、武生、老生，忠勇威严的人物",
           "亮相是人物上下场或一段动作结束时的短暂定格，配合锣鼓点把人物的精神集中地亮给观众。红脸常表示忠勇。", "red", (
        F(0), F(0.9, "垂目蓄势", lid=.45, low=.8, bi=.42, bo=.42, gy=-.5, smile=0),
        F(1.7, "缓缓抬眼", lid=.75, low=.9, bi=.5, bo=.55, gy=0),
        F(2.0, "亮相！", snap=True, lid=1, low=1, bi=.25, bo=1, gy=.1, smile=-.1, wide=.2),
        F(3.6, "定住", lid=1, low=1, bi=.25, bo=1, gy=.1, smile=-.1, wide=.2),
        F(4.5, "收势"))),
    Action("numu", "opera", "怒目圆睁", "黑脸等花脸，刚直勇猛、怒气外放的人物",
           "净行也叫花脸，表演讲究气势。黑脸常表示刚直勇猛，比如包拯、张飞。", "black", (
        F(0), F(.5, "压眉", lid=.8, bi=.1, bo=.75, smile=-.3),
        F(.8, "瞪目", snap=True, lid=1, low=1, bi=0, bo=.9, gx=-.7, smile=-.4, wide=.3, jaw=.12),
        F(1.4, "左扫", lid=1, low=1, bi=0, bo=.9, gx=-.7, smile=-.4, wide=.3, jaw=.12),
        F(1.75, "右扫", snap=True, lid=1, low=1, bi=0, bo=.9, gx=.7, smile=-.4, wide=.3, jaw=.12),
        F(2.3, lid=1, low=1, bi=0, bo=.9, gx=.7, smile=-.4, wide=.3, jaw=.12),
        F(2.6, "正视定住", snap=True, lid=1, low=1, bi=0, bo=1, gx=0, smile=-.5, wide=.5, jaw=.3),
        F(3.8, lid=1, low=1, bi=0, bo=1, gx=0, smile=-.5, wide=.5, jaw=.3),
        F(4.6, "收势"))),
    Action("lengxiao", "opera", "斜眼冷笑", "白脸，奸诈多疑的人物，比如曹操",
           "白脸常表示奸诈多疑，曹操是最常见的例子。这里用单侧挑眉和斜视表现心思深、笑意冷。", "white", (
        F(0), F(.8, "眯眼", lid=.6, low=.65, bi=.42, bo=.5, gx=.5),
        F(1.8, "斜睨", lid=.55, low=.6, bi_l=.4, bo_l=.45, bi_r=.55, bo_r=1, gx=.85, smile_l=0, smile_r=.35),
        F(2.6, "冷笑", lid=.55, low=.55, bi_l=.4, bo_l=.45, bi_r=.55, bo_r=1, gx=.2, smile_l=.1, smile_r=.75, wide=.4),
        F(3.8, lid=.55, low=.55, bi_l=.4, bo_l=.45, bi_r=.55, bo_r=1, gx=.2, smile_l=.1, smile_r=.75, wide=.4),
        F(4.6, "收势"))),
    Action("gangzheng", "opera", "横眉瞪视", "蓝脸、绿脸，刚强桀骜或勇猛鲁莽的人物",
           "蓝脸常表示刚强桀骜，绿脸常表示勇猛暴躁，比如窦尔敦这类绿林人物。", "blue", (
        F(0), F(.7, "横眉", lid=.9, bi=.2, bo=.45, smile=-.2),
        F(1.0, "瞪视", snap=True, lid=1, low=.9, bi=.1, bo=.35, gy=.15, smile=-.3, lu=.7),
        F(2.6, lid=1, low=.9, bi=.1, bo=.35, gy=.15, smile=-.3, lu=.7),
        F(3.4, "收势"))),
    Action("zhuangyan", "opera", "庄严垂目", "金脸、银脸，神佛仙怪；或端庄持重的人物",
           "金脸、银脸多用于神佛仙怪，表现庄严和超凡。", "gold", (
        F(0), F(1.6, "徐徐垂目", lid=.35, low=.8, bi=.55, bo=.5, gy=-.55, smile=.2),
        F(3.0, "静观", lid=.35, low=.8, bi=.55, bo=.5, gy=-.55, smile=.25),
        F(4.2, "抬目", lid=.8, low=1, bi=.6, bo=.6, gy=.1, smile=.2),
        F(5.0, "收势"))),
    Action("yanbo", "opera", "眼波流转", "旦角，闺门旦、花旦，婉约含情的女性人物",
           "旦行重眼神和神韵。这里只做得出眼神和眉眼，兰花指、水袖等身段这个头表现不了。", "dan", (
        F(0), F(.8, "低眉", lid=.65, low=.9, bi=.6, bo=.45, gx=-.3, gy=-.4, smile=.2),
        F(1.8, "眼波右送", lid=.8, low=.9, bi=.65, bo=.55, gx=.65, gy=.05, smile=.35),
        F(2.7, "流转回望", lid=.8, low=.9, bi=.65, bo=.55, gx=-.65, gy=.05, smile=.35),
        F(3.4, "含笑定睛", lid=.9, low=.85, bi=.6, bo=.55, gx=0, gy=0, smile=.5, wide=.15),
        F(4.4, lid=.9, low=.85, bi=.6, bo=.55, gx=0, gy=0, smile=.5, wide=.15),
        F(5.2, "收势"))),
    Action("choujue", "opera", "挤眉弄眼", "丑角，鼻梁上有白色豆腐块的诙谐人物",
           "丑行常在鼻梁上画一块白粉，俗称小花脸，表演诙谐灵活。", "chou", (
        F(0), F(.35, "挑左眉", snap=True, bi_l=1, bo_l=1, bi_r=.3, bo_r=.3, gx=-.5, smile=.5),
        F(.8, "挑右眉", snap=True, bi_r=1, bo_r=1, bi_l=.3, bo_l=.3, gx=.5, smile=.5),
        F(1.25, "挤左眼", snap=True, lid_l=0, low_l=.3, bi_l=.2, bo_l=.2, bi_r=1, bo_r=1, gx=.3, smile_l=.9, smile_r=.4),
        F(1.8, lid_l=0, low_l=.3, bi_l=.2, bo_l=.2, bi_r=1, bo_r=1, gx=.3, smile_l=.9, smile_r=.4),
        F(2.1, "吐舌", snap=True, jaw=.4, ton=.9, smile=.7, wide=.5, bi=.8, bo=.8),
        F(3.0, jaw=.4, ton=.9, smile=.7, wide=.5, bi=.8, bo=.8),
        F(3.7, "收势"))),
    # ---- 动漫 ----
    Action("happy", "anime", "元气大笑", "开怀大笑、张嘴笑、眼睛弯起的角色",
           "动漫常把笑容画得夸张，闭眼弯成弧线或张大嘴，让情绪一眼可读。", "anime", (
        F(0), F(.35, "弯眼", snap=True, lid=.3, low=.3, bi=.8, bo=.7, smile=1, wide=.7, jaw=.5),
        F(.7, "哈", lid=.3, low=.3, bi=.8, bo=.7, smile=1, wide=.7, jaw=.25),
        F(1.0, "哈", lid=.3, low=.3, bi=.8, bo=.7, smile=1, wide=.7, jaw=.6),
        F(1.3, "哈", lid=.3, low=.3, bi=.8, bo=.7, smile=1, wide=.7, jaw=.25),
        F(1.6, lid=.3, low=.3, bi=.8, bo=.7, smile=1, wide=.7, jaw=.6),
        F(2.4, "笑完", lid=.85, low=.9, bi=.7, bo=.6, smile=.7, wide=.4),
        F(3.2, "收势"))),
    Action("shock", "anime", "夸张震惊", "眼睛瞪圆、下巴掉下来的震惊角色",
           "搞笑场面常用夸张到变形的震惊表情，这里用最大张嘴和最快抬眉模仿。", "anime", (
        F(0), F(.6, "愣住", lid=.9, gx=0),
        F(.8, "！！", snap=True, lid=1, low=1, bi=1, bo=1, jaw=.95, wide=.3, smile=-.2),
        F(2.2, lid=1, low=1, bi=1, bo=1, jaw=.95, wide=.3, smile=-.2),
        F(3.0, "回神"))),
    Action("jitome", "anime", "半眼吐槽", "半闭眼、嘴平、无语或鄙视的角色（ジト目）",
           "ジト目指半闭着眼、带冷淡或鄙视意味的目光，是常见的吐槽表情。", "anime", (
        F(0), F(.7, "半闭眼", lid=.4, low=.75, bi=.4, bo=.4, smile=-.1),
        F(1.7, "慢慢看向一边", lid=.4, low=.75, bi=.4, bo=.4, gx=.75, smile=-.15),
        F(2.7, "再看回来", lid=.4, low=.75, bi=.4, bo=.4, gx=0, smile=-.2),
        F(3.5, lid=.4, low=.75, bi=.4, bo=.4, gx=0, smile=-.2),
        F(4.2, "收势"))),
    Action("angry", "anime", "炸毛生气", "鼓腮、怒吼、青筋的生气角色",
           "动漫生气常把眉头压成尖角，再加上露牙怒吼。", "anime", (
        F(0), F(.4, "皱眉", snap=True, lid=.9, bi=0, bo=1, smile=-.5, lu=.7),
        F(1.0, "吼", snap=True, lid=1, low=.8, bi=0, bo=1, jaw=.6, lu=1, wide=.8, smile=-.5),
        F(2.2, lid=1, low=.8, bi=0, bo=1, jaw=.6, lu=1, wide=.8, smile=-.5),
        F(2.9, "收势"))),
    Action("cry", "anime", "泪眼汪汪", "含泪、伤心、委屈的角色",
           "委屈时眉头内侧上抬、嘴角下撇。这个头没有眼泪，只靠眉眼和颤动的嘴表现。", "anime", (
        F(0), F(.9, "委屈", lid=.75, low=.75, bi=1, bo=.25, gy=-.3, smile=-.6),
        F(1.3, "抽泣", lid=.7, low=.7, bi=1, bo=.25, gy=-.35, smile=-.8, jaw=.15),
        F(1.6, lid=.7, low=.7, bi=1, bo=.25, gy=-.35, smile=-.8, jaw=.02),
        F(1.9, lid=.7, low=.7, bi=1, bo=.25, gy=-.35, smile=-.8, jaw=.15),
        F(2.2, lid=.7, low=.7, bi=1, bo=.25, gy=-.35, smile=-.8, jaw=.02),
        F(3.0, lid=.65, low=.7, bi=.95, bo=.25, gy=-.4, smile=-.7),
        F(3.8, "收势"))),
    Action("shy", "anime", "害羞躲闪", "脸红、视线躲开、害羞的角色",
           "脸红是动漫里最常见的害羞信号。这个头不会脸红，靠躲开视线和快速眨眼表现。", "anime", (
        F(0), F(.5, "偷看", lid=.85, bi=.7, bo=.55, gx=.3, smile=.2),
        F(.8, "躲开", snap=True, lid=.75, bi=.75, bo=.5, gx=-.8, gy=-.5, smile=.35),
        F(1.2, "眨眼", lid=.05, low=.6, gx=-.8, gy=-.5, bi=.75, bo=.5, smile=.35),
        F(1.4, lid=.8, gx=-.8, gy=-.5, bi=.75, bo=.5, smile=.35),
        F(1.6, lid=.05, low=.6, gx=-.8, gy=-.5, bi=.75, bo=.5, smile=.35),
        F(1.8, lid=.8, gx=-.8, gy=-.5, bi=.75, bo=.5, smile=.35),
        F(2.8, "又看回来", lid=.85, bi=.7, bo=.55, gx=.1, gy=-.1, smile=.5),
        F(3.6, "收势"))),
    Action("wink", "anime", "俏皮眨眼", "单眼 wink、比耶、卖萌的角色",
           "单眼 wink 配吐舌是偶像和元气角色的常见动作。", "anime", (
        F(0), F(.5, "看过来", lid=1, bi=.7, bo=.7, smile=.6),
        F(.85, "Wink", snap=True, lid_r=0, low_r=.4, lid_l=1, bi_r=.5, bo_r=.5, bi_l=.8, bo_l=.85, smile=.9, wide=.4, jaw=.2, ton=.6),
        F(1.9, lid_r=0, low_r=.4, lid_l=1, bi_r=.5, bo_r=.5, bi_l=.8, bo_l=.85, smile=.9, wide=.4, jaw=.2, ton=.6),
        F(2.7, "收势"))),
    Action("resolve", "anime", "热血决意", "眼神坚定、咬牙、准备战斗的角色",
           "热血番常用压低的眉毛和直视前方的眼神，表现下定决心。", "anime", (
        F(0), F(.8, "低头蓄力", lid=.6, low=.9, bi=.3, bo=.45, gy=-.4, smile=-.1),
        F(1.1, "抬眼", snap=True, lid=1, low=.85, bi=.15, bo=.7, gy=.1, lu=.7, wide=.7, smile=-.1),
        F(2.6, "决意", lid=1, low=.85, bi=.15, bo=.7, gy=.1, lu=.7, wide=.7, smile=.1),
        F(3.4, "收势"))),
    Action("calm", "anime", "温柔微笑", "表情平静、轻轻微笑的角色",
           "平静的角色不需要大动作，慢眨眼和淡淡的笑就够了。", "anime", (
        F(0), F(1.0, "微笑", lid=.9, low=.9, bi=.6, bo=.55, smile=.45),
        F(1.8, "慢眨眼", lid=.05, low=.6, bi=.6, bo=.55, smile=.45),
        F(2.4, lid=.9, low=.9, bi=.6, bo=.55, smile=.5),
        F(3.4, lid=.9, low=.9, bi=.6, bo=.55, smile=.5),
        F(4.2, "收势"))),
]
ACTIONS = {a.id: a for a in _A}
assert all(a.frames[0].t == 0 and not a.frames[-1].pose for a in _A)
assert set(semantic_to_u({})) == set(BY_NAME) - EXCLUDE
