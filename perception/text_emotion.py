"""文本情感（TER）。

主路径：DashScope 兼容接口，只让它输出一个标签词。
兜底：中文关键词规则。现场断网、没配 key、或者超时都会自动落到兜底，
保证文本这一路永远不会阻塞整条管线。

注意：关键词兜底会按字面判断，"太好了，又要加班" 会判成 happy ——
这正好是矛盾 demo 需要的行为，不要"修"它。
"""
from __future__ import annotations

import json
import os
import re
import urllib.request

from .types import LABEL7, normalize_probs

SYNONYMS = {
    "开心的": "happy", "高兴": "happy", "快乐": "happy", "幸福": "happy",
    "开心": "happy", "happy": "happy", "joy": "happy",
    "难过": "sad", "伤心": "sad", "悲伤": "sad", "失落": "sad", "sad": "sad",
    "生气": "angry", "愤怒": "angry", "烦": "angry", "气死": "angry", "angry": "angry",
    "惊讶": "surprise", "吃惊": "surprise", "没想到": "surprise", "surprise": "surprise",
    "害怕": "fear", "恐惧": "fear", "担心": "fear", "fear": "fear",
    "恶心": "disgust", "厌恶": "disgust", "disgust": "disgust",
    "平静": "neutral", "中性": "neutral", "neutral": "neutral", "一般": "neutral",
}

KEYWORDS = {
    "happy": ["开心", "高兴", "太好了", "棒", "喜欢", "哈哈", "爽", "幸福", "谢谢"],
    "sad": ["难过", "伤心", "累", "失望", "想哭", "孤独", "没意思", "算了"],
    "angry": ["烦", "生气", "气死", "讨厌", "滚", "凭什么", "无语", "过分"],
    "surprise": ["没想到", "居然", "真的吗", "天啊", "哇", "不会吧"],
    "fear": ["害怕", "担心", "紧张", "恐怖", "吓"],
    "disgust": ["恶心", "厌恶", "受不了", "膈应"],
}

# 注意：这里刻意只判「字面」情绪。反讽留给融合层去和语气对照，
# 如果让 LLM 推断言外之意，"太好了，又要加班" 会被判成 sad，矛盾 demo 就没了。
PROMPT = ("你是情感分类器。只输出下面 7 个英文标签中的一个，不要解释、不要标点：\n"
          "neutral, happy, sad, angry, surprise, fear, disgust\n"
          "只根据句子里字面出现的情感词判断，不要推断反讽或言外之意。\n句子：{text}")


def keyword_probs(text: str, peak: float = 0.62) -> dict[str, float]:
    hits: dict[str, int] = {}
    for label, words in KEYWORDS.items():
        n = sum(text.count(w) for w in words)
        if n:
            hits[label] = n
    if not hits:
        p = {k: 0.02 for k in LABEL7}
        p["neutral"] = 1.0 - 0.02 * 6
        return normalize_probs(p)
    label = max(hits, key=hits.get)
    p = {k: (1.0 - peak) / (len(LABEL7) - 1) for k in LABEL7}
    p[label] = peak
    return normalize_probs(p)


def _parse(answer: str) -> str | None:
    a = answer.strip().lower()
    for key in LABEL7:
        if key in a:
            return key
    for k, v in SYNONYMS.items():
        if k in a:
            return v
    return None


class TextEmotion:
    def __init__(self, model: str | None = None, timeout: float = 2.0,
                 base_url: str | None = None, api_key: str | None = None):
        self.model = model or os.environ.get("EMOBOT_TEXT_MODEL", "qwen3.5-plus")
        self.timeout = timeout
        self.base_url = (base_url or os.environ.get("DASHSCOPE_BASE_URL")
                         or "https://dashscope.aliyuncs.com/compatible-mode/v1").rstrip("/")
        self.api_key = api_key or os.environ.get("DASHSCOPE_API_KEY")

    @property
    def online(self) -> bool:
        return bool(self.api_key)

    def _call(self, text: str) -> str:
        body = json.dumps({
            "model": self.model,
            "messages": [{"role": "user", "content": PROMPT.format(text=text)}],
            "temperature": 0, "max_tokens": 8,
        }).encode()
        req = urllib.request.Request(
            f"{self.base_url}/chat/completions", data=body,
            headers={"Authorization": f"Bearer {self.api_key}",
                     "Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            data = json.loads(r.read())
        return data["choices"][0]["message"]["content"]

    def infer(self, text: str) -> tuple[dict[str, float], str]:
        """返回 (7 类概率, 来源)，来源是 api / keyword。"""
        text = (text or "").strip()
        if not text:
            return normalize_probs({}), "empty"
        if self.online:
            try:
                label = _parse(self._call(text))
                if label:
                    p = {k: (1.0 - 0.7) / (len(LABEL7) - 1) for k in LABEL7}
                    p[label] = 0.7
                    return normalize_probs(p), "api"
            except Exception:
                pass
        return keyword_probs(text), "keyword"
