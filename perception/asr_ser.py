"""SenseVoiceSmall：一次推理同时出 ASR 文本和情感标签。

注意两个坑（见 docs/情感识别模块/06-实验报告.md）：
- 默认设置下大部分句子输出 EMO_UNKNOWN，必须 ban_emo_unk=True；
- 情感是硬标签，所以这里按 fast_layer.py 的做法平滑成 0.7 / 0.3 的概率。
"""
from __future__ import annotations

import os
import re

import numpy as np

from .types import LABEL7, normalize_probs

SV_MAP = {"HAPPY": "happy", "SAD": "sad", "ANGRY": "angry", "NEUTRAL": "neutral",
          "FEARFUL": "fear", "DISGUSTED": "disgust", "SURPRISED": "surprise",
          "EMO_UNKNOWN": "neutral"}
_TAG = re.compile(r"<\|[^|]*\|>")


def _auto_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _default_model_dir(env_key: str, name: str) -> str:
    """优先显式环境变量，其次 EMOBOT_MODEL_DIR 下的本地目录，最后让 FunASR 自己下。"""
    explicit = os.environ.get(env_key)
    if explicit:
        return explicit
    root = os.environ.get("EMOBOT_MODEL_DIR")
    if root:
        p = os.path.join(root, name)
        if os.path.isdir(p):
            return p
    return f"iic/{name}"


def _hard_probs(tag: str, peak: float = 0.7) -> dict[str, float]:
    label = SV_MAP.get(str(tag).upper(), "neutral")
    p = {k: (1.0 - peak) / (len(LABEL7) - 1) for k in LABEL7}
    p[label] = peak
    return normalize_probs(p)


def clean_text(raw: str) -> str:
    """去掉 <|zh|><|NEUTRAL|>... 标签，只留正文。"""
    try:
        from funasr.utils.postprocess_utils import rich_transcription_postprocess

        return rich_transcription_postprocess(raw).strip()
    except Exception:
        return _TAG.sub("", raw).strip()


class SenseVoice:
    def __init__(self, model_dir: str | None = None, device: str | None = None,
                 ban_emo_unk: bool = True):
        from funasr import AutoModel

        path = model_dir or _default_model_dir("EMOBOT_SENSEVOICE", "SenseVoiceSmall")
        self.model = AutoModel(model=path, disable_update=True, device=device or _auto_device())
        self.ban_emo_unk = ban_emo_unk

    def transcribe(self, wav: np.ndarray, language: str = "zh") -> tuple[str, dict[str, float]]:
        """wav: float32 mono 16k。返回 (文本, 7 类概率)。"""
        res = self.model.generate(input=np.asarray(wav, dtype=np.float32), language=language,
                                  use_itn=True, ban_emo_unk=self.ban_emo_unk,
                                  disable_pbar=True)[0]
        raw = res.get("text", "")
        tags = [t[2:-2] for t in _TAG.findall(raw)]  # <|X|> -> X
        emo = next((t for t in tags if t.upper() in SV_MAP), "NEUTRAL")
        return clean_text(raw), _hard_probs(emo)
