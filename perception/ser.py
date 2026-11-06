"""emotion2vec+ 零样本语音情感。

注意：训练数据里包含 EmoBox 学术集，所以它在 RAVDESS / CREMA-D 上的"零样本"分数
被污染过（06-实验报告 2.1）。这只影响拿它去报 benchmark 数字；实时 demo 不在那些
数据集上，直接用它自带的 9 类头是最省事、效果也最好的做法。
"""
from __future__ import annotations

import os

import numpy as np

from .types import LABEL7, normalize_probs

E2V_MAP = {"angry": "angry", "disgusted": "disgust", "fearful": "fear",
           "happy": "happy", "neutral": "neutral", "sad": "sad", "surprised": "surprise"}


def _auto_device() -> str:
    try:
        import torch

        return "cuda" if torch.cuda.is_available() else "cpu"
    except Exception:
        return "cpu"


def _default_model_dir() -> str:
    explicit = os.environ.get("EMOBOT_E2V")
    if explicit:
        return explicit
    root = os.environ.get("EMOBOT_MODEL_DIR")
    if root:
        for name in ("emotion2vec_plus_large", "emotion2vec_plus_base", "emotion2vec_base"):
            p = os.path.join(root, name)
            if os.path.isdir(p):
                return p
    return "iic/emotion2vec_plus_large"


class Emotion2Vec:
    def __init__(self, model_dir: str | None = None, device: str | None = None):
        from funasr import AutoModel

        path = model_dir or _default_model_dir()
        self.model = AutoModel(model=path, disable_update=True, device=device or _auto_device())

    def infer(self, wav: np.ndarray) -> dict[str, float] | None:
        """返回 7 类概率；模型没给分类头时返回 None（融合层会当成缺失模态）。"""
        r = self.model.generate(np.asarray(wav, dtype=np.float32), granularity="utterance",
                                extract_embedding=False, disable_pbar=True)[0]
        scores, labels = r.get("scores"), r.get("labels")
        if scores is None or labels is None:
            return None
        probs = {k: 0.0 for k in LABEL7}
        for score, name in zip(np.asarray(scores).reshape(-1), labels):
            key = E2V_MAP.get(str(name).split("/")[-1].lower())
            if key:
                probs[key] += float(score)
        return normalize_probs(probs)
