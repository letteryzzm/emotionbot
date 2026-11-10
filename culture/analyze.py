"""看图选动作：图片发给千问全模态模型，返回校验过的结果。

MediaPipe 在 47 张京剧和动漫测试图上只检出 11 张，所以这里不用人脸关键点。
结果按图片 SHA-256 存进 outputs/culture_cache/，同一张图不再上传，断网时也能用。
密钥只在这个进程里读取，不进日志，不发给网页。
"""
import base64
import hashlib
import json
import math
import os
import urllib.error
import urllib.request
from pathlib import Path


from .actions import ACTIONS

ROOT = Path(__file__).resolve().parent.parent
ENV = ROOT / "emo_bench" / ".env"
CACHE = ROOT / "outputs" / "culture_cache"
# 千问全模态。魔搭 API-Inference 目前没有开放 Omni 模型，所以默认走 emo_bench 配好的百炼接口。
# 接口是 OpenAI 兼容的，要换服务时设 CULTURE_API_BASE、CULTURE_API_KEY、CULTURE_MODEL
MODEL = os.environ.get("CULTURE_MODEL", "qwen3.8-omni-flash")
MAX_SIDE = 768
MAX_UPLOAD = 12 * 1024 * 1024
CATEGORIES = ("opera", "anime", "other")
EMOTIONS = ("neutral", "happy", "sad", "angry", "surprise", "fear", "disgust")


class AnalyzeError(Exception):
    """消息直接显示给用户。"""


def env_file():
    try:
        return dict(line.strip().split("=", 1) for line in ENV.read_text().splitlines() if "=" in line)
    except FileNotFoundError:
        return {}


def endpoint():
    """返回 (接口地址, 密钥)。"""
    env = env_file()
    base = os.environ.get("CULTURE_API_BASE") or env.get("DASHSCOPE_BASE_URL")
    key = os.environ.get("CULTURE_API_KEY") or env.get("DASHSCOPE_API_KEY")
    if not base or not key:
        raise AnalyzeError("没有配置千问接口。可以直接从右边选动作")
    return base.rstrip("/") + "/chat/completions", key


def prepare(data):
    """解码并缩小，同时去掉原图的 EXIF 等元数据。只接受真的图片。"""
    if not data or len(data) > MAX_UPLOAD:
        raise AnalyzeError("图片为空或超过 12 MB")
    try:
        import cv2   # 只有识图用到，ROG 上的戏台只放预设，不装 opencv
        import numpy as np
    except ImportError as e:
        raise AnalyzeError("这台机器没装 opencv，不能识图") from e
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        raise AnalyzeError("读不出这张图片，请换 JPG 或 PNG")
    h, w = img.shape[:2]
    s = MAX_SIDE / max(h, w)
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])
    if not ok:
        raise AnalyzeError("图片编码失败")
    return buf.tobytes()


def prompt():
    rows = "\n".join(f"- {a.id}（{'京剧' if a.group == 'opera' else '动漫'}）{a.name}：{a.use}" for a in ACTIONS.values())
    return f"""你在给一个机器人头选表情动作。看图片里的主要人物，只能从下面选一个动作：
{rows}

先判断类别：opera 是京剧或京剧风格的脸谱、戏装、戏画；anime 是动漫或二次元插画；都不是就 other，action 填 null。
京剧图按下面的顺序决定，脸谱颜色优先于神态：
1. 鼻梁或眼周有一小块白粉：choujue
2. 有大面积勾脸或整脸涂色时看脸的主色：白 lengxiao，红 liangxiang，黑 numu，蓝或绿 gangzheng，金或银 zhuangyan
3. 没有勾脸的女性角色：yanbo
4. 没有勾脸的男性角色：liangxiang
动漫图看此刻的表情。
只描述画面。不要猜测或说出真实演员、真实人物的姓名；subject 写角色类型，比如“红脸老生”“笑着的短发少女”。
只有图上有文字或脸谱特征非常明确时，才写戏曲角色名。

只输出一个 JSON，字段：
category: opera/anime/other
subject: 不超过 16 字
evidence: 看到了什么，不超过 40 字
emotion: 人物此刻的情绪，只能是 {"/".join(EMOTIONS)} 之一
action: 动作 id 或 null
intensity: 0.4~1，表情越夸张越大
confidence: 0~1，你对选择的把握"""


def parse(text):
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end < start:
        raise AnalyzeError("模型没有返回结果，请重试或手动选动作")
    try:
        d = json.loads(text[start:end + 1])
    except ValueError as e:
        raise AnalyzeError("模型返回的格式不对，请重试或手动选动作") from e
    if not isinstance(d, dict):
        raise AnalyzeError("模型返回的格式不对，请重试或手动选动作")
    category = d.get("category")
    if category not in CATEGORIES:
        category = "other"
    action = d.get("action")
    if action not in ACTIONS or ACTIONS[action].group != category:
        action = None     # 模型选了不存在或类别不符的动作，不硬放
    def number(key, default, lo, hi):
        try:
            x = float(d.get(key, default))
        except (TypeError, ValueError):
            x = default
        return min(hi, max(lo, x if math.isfinite(x) else default))
    return {
        "category": category,
        "subject": str(d.get("subject") or "")[:24],
        "evidence": str(d.get("evidence") or "")[:80],
        "emotion": d.get("emotion") if d.get("emotion") in EMOTIONS else "neutral",
        "action": action,
        "intensity": number("intensity", 0.8, 0.4, 1.0),
        "confidence": number("confidence", 0.5, 0.0, 1.0),
    }


def cached(digest):
    try:
        return json.loads((CACHE / f"{digest}.json").read_text())
    except (FileNotFoundError, ValueError):
        return None


def http_post(body):
    """全模态模型只支持流式。返回 (状态码, 拼好的回答)。网络失败抛 OSError。"""
    url, key = endpoint()
    req = urllib.request.Request(url, json.dumps(body).encode(),
                                 {"Authorization": f"Bearer {key}", "Content-Type": "application/json"})
    out = []
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            for line in r:
                if not line.startswith(b"data:") or b"[DONE]" in line:
                    continue
                for choice in json.loads(line[5:]).get("choices", []):
                    out.append(choice.get("delta", {}).get("content") or "")
            return r.status, "".join(out)
    except urllib.error.HTTPError as e:
        return e.code, ""
    except ValueError:
        return 200, ""


def analyze(data, post=http_post):
    jpeg = prepare(data)
    digest = hashlib.sha256(jpeg + (MODEL + prompt()).encode()).hexdigest()   # 换模型或提示词后不用旧结果
    hit = cached(digest)
    if hit:
        return {**hit, "cached": True}
    body = {
        "model": MODEL,
        "stream": True,
        "temperature": 0,
        "max_tokens": 400,
        "modalities": ["text"],
        "enable_thinking": False,
        "messages": [{"role": "user", "content": [
            {"type": "image_url", "image_url": {"url": "data:image/jpeg;base64," + base64.b64encode(jpeg).decode()}},
            {"type": "text", "text": prompt()},
        ]}],
    }
    try:
        status, text = post(body)
    except OSError as e:
        raise AnalyzeError("连不上识图服务，可以直接从右边选动作") from e
    if status == 429 or status >= 500:
        raise AnalyzeError("识图服务现在太忙，等一分钟再试，或者直接从右边选动作")
    if status != 200:
        raise AnalyzeError(f"识图服务返回 {status}，可以直接从右边选动作")
    result = parse(text or "")
    CACHE.mkdir(parents=True, exist_ok=True)
    (CACHE / f"{digest}.json").write_text(json.dumps(result, ensure_ascii=False))
    return {**result, "cached": False}
