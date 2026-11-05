"""闭源 / 云端 API 零样本评测（和 omni.py 同一子集、同一提示词）。

python api_eval.py <provider> <model> <ds> <mode> [--n N] [--workers 8]
  provider: dashscope（OpenAI 兼容，服务器上跑） | gemini（REST，Mac 上跑） | minimax（OpenAI 兼容，只有视觉）
  ds:   ravdess | cremad | meld    （mode = audio / video / av / avt）
        ter_cped | ter_meld       （mode = text_ctx，带上文）
结果：每条原始回答缓存在 results/api_cache/<provider>__<model>__<ds>__<mode>.jsonl（可断点续跑），
      指标写入 results.jsonl（task=api）。解析不到标签的回答记为错，并单独报告 invalid 比例。
"""
import argparse
import base64
import json
import os
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import numpy as np
import pandas as pd
import requests

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # emo_bench/
LABEL7 = ["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"]
SYN = {"neutral": "neutral", "happy": "happy", "happiness": "happy", "joy": "happy", "sad": "sad", "sadness": "sad",
       "angry": "angry", "anger": "angry", "surprise": "surprise", "surprised": "surprise", "fear": "fear",
       "fearful": "fear", "disgust": "disgust", "disgusted": "disgust"}
Q = {
    "audio": "Listen to the speaker's voice (tone, pitch, energy), not just the words.",
    "video": "Look at the person's facial expression in this silent video.",
    "av": "Use both the speaker's facial expression and tone of voice.",
    "avt": "Use the speaker's facial expression, tone of voice and the transcript.",
}
INSTR_ZH = "判断【目标句】说话人的情绪，只能从以下英文标签中选一个：{labels}。只回答一个标签词。"
INSTR_EN = "Classify the emotion of the TARGET utterance into exactly one of: {labels}. Answer with the single label word only."


def load_env():
    for line in open(f"{ROOT}/.env"):
        if "=" in line:
            k, v = line.strip().split("=", 1)
            os.environ.setdefault(k, v)


def b64(path):
    return base64.b64encode(open(path, "rb").read()).decode()


def build_prompt(row, ds, mode, labels):
    lab = ", ".join(labels)
    if mode == "text_ctx":
        zh = ds == "ter_cped"
        ctx = row.context if isinstance(row.context, str) and row.context else ("（无上文）" if zh else "(no previous turns)")
        if zh:
            return f"{INSTR_ZH.format(labels=lab)}\n\n对话上文：\n{ctx}\n\n【目标句】{row.speaker}：{row.text}"
        return f"{INSTR_EN.format(labels=lab)}\n\nConversation so far:\n{ctx}\n\nTARGET — {row.speaker}: {row.text}"
    t = (Q[mode] + f" What emotion is the speaker expressing? Choose exactly one of: {lab}. "
         "Answer with the single label word only.")
    if mode == "avt":
        t += f'\nTranscript: "{row.text}"'
    return t


model_hint = {}  # main() 里写入当前模型名，用于判断是否走"带音轨视频"


def media(row, root, mode, provider):
    """返回 [(kind, path)]，kind in audio/video"""
    wav, sil, av = f"{root}/wav/{row.key}.wav", f"{root}/vid_silent/{row.key}.mp4", f"{root}/vid_av/{row.key}.mp4"
    if mode == "audio":
        return [("audio", wav)]
    if mode == "video":
        return [("video", sil)]
    # Gemini、Qwen-Omni 原生读取视频音轨（Qwen-Omni 不接受"视频 + 单独音频"混合输入）
    if provider == "gemini" or any(k in model_hint.get("m", "") for k in ["gemini", "omni"]):
        return [("video", av)]
    return [("video", sil), ("audio", wav)]


# ---------------- providers ----------------
def call_dashscope(model, items, prompt, max_tokens=20):
    content = []
    for kind, p in items:
        if kind == "audio":
            content.append({"type": "input_audio", "input_audio": {"data": f"data:;base64,{b64(p)}", "format": "wav"}})
        else:
            content.append({"type": "video_url", "video_url": {"url": f"data:;base64,{b64(p)}"}})
    content.append({"type": "text", "text": prompt})
    body = {"model": model, "messages": [{"role": "user", "content": content}], "stream": True,
            "temperature": 0, "max_tokens": max_tokens}
    if "omni" in model:
        body["modalities"] = ["text"]
    body["enable_thinking"] = False  # 只要一个标签词，关掉思考（qwen3.x / omni / kimi 都支持）
    r = requests.post(f"{os.environ['DASHSCOPE_BASE_URL']}/chat/completions", json=body, stream=True, timeout=180,
                      headers={"Authorization": f"Bearer {os.environ['DASHSCOPE_API_KEY']}"})
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    out = []
    for line in r.iter_lines():
        if line.startswith(b"data:") and b"[DONE]" not in line:
            d = json.loads(line[5:])
            for ch in d.get("choices", []):
                out.append(ch.get("delta", {}).get("content") or "")
    return "".join(out)


_gem_thinking = {"ok": True}


def call_gemini(model, items, prompt):
    parts = []
    for kind, p in items:
        parts.append({"inline_data": {"mime_type": "audio/wav" if kind == "audio" else "video/mp4", "data": b64(p)}})
    parts.append({"text": prompt})
    cfg = {"temperature": 0, "maxOutputTokens": 1024}
    if _gem_thinking["ok"]:
        cfg["thinkingConfig"] = {"thinkingLevel": "low"}
    body = {"contents": [{"role": "user", "parts": parts}], "generationConfig": cfg}
    r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                      json=body, timeout=180, headers={"x-goog-api-key": os.environ["GEMINI_API_KEY"]})
    if r.status_code == 400 and "thinking" in r.text.lower() and _gem_thinking["ok"]:
        _gem_thinking["ok"] = False
        return call_gemini(model, items, prompt)
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    d = r.json()
    cand = d.get("candidates", [{}])[0]
    return "".join(p.get("text", "") for p in cand.get("content", {}).get("parts", []) if not p.get("thought"))


def call_minimax(model, items, prompt):
    content = [{"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(p)}"}} for k, p in items
               if k == "video"]
    content.append({"type": "text", "text": prompt})
    r = requests.post("https://api.minimaxi.com/v1/chat/completions", timeout=180,
                      headers={"Authorization": f"Bearer {os.environ['MINIMAX_API_KEY']}"},
                      json={"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0.01})
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    return r.json()["choices"][0]["message"]["content"]


def call_openrouter(model, items, prompt):
    """OpenRouter（OpenAI 兼容）：音频走 input_audio（裸 base64），视频走 video_url（data URL）。"""
    content = []
    for kind, p in items:
        if kind == "audio":
            content.append({"type": "input_audio", "input_audio": {"data": b64(p), "format": "wav"}})
        else:
            content.append({"type": "video_url", "video_url": {"url": f"data:video/mp4;base64,{b64(p)}"}})
    content.append({"type": "text", "text": prompt})
    body = {"model": model, "messages": [{"role": "user", "content": content}], "temperature": 0,
            "max_tokens": 2048, "reasoning": {"effort": "low"}, "usage": {"include": True}}
    r = requests.post("https://openrouter.ai/api/v1/chat/completions", json=body, timeout=240,
                      headers={"Authorization": f"Bearer {os.environ['OPENROUTER_API_KEY']}"})
    if r.status_code != 200:
        raise RuntimeError(f"{r.status_code} {r.text[:300]}")
    d = r.json()
    if "choices" not in d:
        raise RuntimeError(str(d)[:300])
    _cost.v = d.get("usage", {}).get("cost")
    return d["choices"][0]["message"].get("content") or ""


_cost = threading.local()  # OpenRouter 每次调用的美元花费（usage accounting）


CALL = {"dashscope": call_dashscope, "gemini": call_gemini, "minimax": call_minimax, "openrouter": call_openrouter}


def parse(ans):
    a = re.sub(r"<think>.*?</think>", "", ans or "", flags=re.S).lower()
    for w in re.findall(r"[a-z]+", a):
        if w in SYN:
            return SYN[w]
    return "invalid"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("provider")
    ap.add_argument("model")
    ap.add_argument("ds")
    ap.add_argument("mode")
    ap.add_argument("--n", type=int, default=0, help="只跑前 n 条（0 = 全部子集）")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--root", default=os.environ.get("API_SUBSET", os.path.expanduser("~/emo/work/api_subset")))
    a = ap.parse_args()
    load_env()
    model_hint["m"] = a.model
    root = f"{a.root}/{a.ds}"
    sub = pd.read_csv(f"{root}/subset.csv")
    if a.n:
        sub = sub.groupby("label7").head(max(1, a.n // sub.label7.nunique()))
    labels = [c for c in LABEL7 if c in set(sub.label7)]
    os.makedirs(f"{ROOT}/results/api_cache", exist_ok=True)
    cache_f = f"{ROOT}/results/api_cache/{a.provider}__{a.model.replace('/', '_')}__{a.ds}__{a.mode}.jsonl"
    done = {}
    if os.path.exists(cache_f):
        for line in open(cache_f):
            d = json.loads(line)
            if "answer" in d:
                done[d["key"]] = d
    lock = threading.Lock()

    def work(row):
        if row.key in done:
            return
        items = [] if a.mode == "text_ctx" else media(row, root, a.mode, a.provider)
        prompt = build_prompt(row, a.ds, a.mode, labels)
        for attempt in range(5):
            try:
                t0 = time.time()
                ans = CALL[a.provider](a.model, items, prompt)
                rec = {"key": row.key, "answer": ans, "sec": round(time.time() - t0, 2)}
                if getattr(_cost, "v", None) is not None:
                    rec["cost"] = _cost.v
                break
            except Exception as e:
                rec = {"key": row.key, "error": str(e)[:300]}
                time.sleep(3 * 2 ** attempt)
        with lock:
            with open(cache_f, "a") as f:
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            if "answer" in rec:
                done[row.key] = rec

    with ThreadPoolExecutor(a.workers) as ex:
        list(ex.map(work, sub.itertuples()))

    sub = sub[sub.key.isin(done)]
    pred = [parse(done[k]["answer"]) for k in sub.key]
    from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
    y = sub.label7.values
    res = dict(task="api", provider=a.provider, feat=a.model, ds=a.ds, mode=a.mode, space="label7", sampled=True,
               UA=100 * balanced_accuracy_score(y, pred), WA=100 * accuracy_score(y, pred),
               macroF1=100 * f1_score(y, pred, labels=labels, average="macro"),
               wF1=100 * f1_score(y, pred, labels=labels, average="weighted"),
               invalid=100 * float(np.mean(np.array(pred) == "invalid")), n=int(len(sub)),
               sec_median=float(np.median([done[k]["sec"] for k in sub.key])),
               cost_usd=round(sum(done[k].get("cost", 0) or 0 for k in sub.key), 4),
               time=time.strftime("%Y-%m-%d %H:%M:%S"))
    out = os.environ.get("RESULTS", os.path.expanduser("~/work/emo_results/results.jsonl"))
    os.makedirs(os.path.dirname(out), exist_ok=True)
    with open(out, "a") as f:
        f.write(json.dumps(res, ensure_ascii=False) + "\n")
    print(json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in res.items()}, ensure_ascii=False))
    errs = sum(1 for _ in open(cache_f)) - len(done)
    if errs:
        print("errors logged:", errs)


if __name__ == "__main__":
    main()
