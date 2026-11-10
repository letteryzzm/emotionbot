"""生成机器人回应的中文句子。

3 天里 LLM 是可选项：模板句零延迟、零网络依赖，答辩现场最稳。
以后接 LLM 只要换掉 reply() 的实现，调用方不用动。

设计原则（docs/情感识别模块/05-后续优化.md）：不要对着用户复述他的情绪
（"你看起来很生气"），只做陪伴和回应。
"""
from __future__ import annotations

import random

from perception.types import FusionResult

TEMPLATES: dict[str, list[str]] = {
    "conflict": ["听起来你并不轻松，我陪你一会儿。",
                 "嘴上说没事，其实挺累的吧？"],
    "happy": ["看你这么开心，我也高兴。", "真不错，我都感受到了。"],
    "sad": ["我在听，慢慢说。", "别一个人扛着，我陪着你。"],
    "angry": ["别急，我们一起想办法。", "先缓缓，我在这儿。"],
    "surprise": ["哇，发生了什么？", "真的吗？快说说。"],
    "fear": ["别怕，我在呢。", "没事的，先深呼吸。"],
    "disgust": ["确实有点让人不舒服。", "嗯，我明白你的意思。"],
    "neutral": ["嗯，我在听。", "好，我听着呢。"],
}


def pick_style(fusion: FusionResult) -> str:
    if fusion.conflict:
        return "conflict"
    return fusion.label if fusion.label in TEMPLATES else "neutral"


def reply(fusion: FusionResult, rng: random.Random | None = None) -> str:
    """按融合结果给一句短回复。句长控制在 25 字以内，保证 TTS 首字延迟。"""
    rng = rng or random
    return rng.choice(TEMPLATES[pick_style(fusion)])
