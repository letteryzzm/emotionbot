"""第三代 / 端到端：Qwen2.5-Omni-7B（只用 Thinker）零样本。

python omni.py <ds> audio|video|av|avt [--n 700] [--api_n 56]
  audio  只给语音（SER 零样本）
  video  只给无声视频（FER 零样本）
  av     视频 + 视频里的音频
  avt    视频 + 音频 + 文本转写（仅 MELD，用标注文本）
打分：回答第一个 token 在 7 个标签词上的 logits softmax。分层抽样 n 条测试样本（固定 seed）。
"""
import argparse

import numpy as np
import torch
from qwen_omni_utils import process_mm_info
from transformers import Qwen2_5OmniProcessor, Qwen2_5OmniThinkerForConditionalGeneration

from common import LABEL7, MODELS, WORK, load_meta, log_result, metrics

PATH = f"{MODELS}/Qwen2.5-Omni-7B"
SYS = ("You are Qwen, a virtual human developed by the Qwen Team, Alibaba Group, capable of perceiving auditory "
       "and visual inputs, as well as generating text and speech.")
Q = {
    "audio": "Listen to the speaker's voice (tone, pitch, energy), not just the words.",
    "video": "Look at the person's facial expression in this silent video.",
    "av": "Use both the speaker's facial expression and tone of voice.",
    "avt": "Use the speaker's facial expression, tone of voice and the transcript.",
}
TAIL = (" What emotion is the speaker expressing? Choose exactly one of: neutral, happy, sad, angry, surprise, fear, "
        "disgust. Answer with the single label word only.")


def sample(meta, test_idx, n):
    rng = np.random.RandomState(0)
    lab = meta.label7.values[test_idx]
    cls = [c for c in LABEL7 if (lab == c).any()]
    per = n // len(cls)
    pick = []
    for c in cls:
        ids = test_idx[lab == c]
        pick += list(rng.choice(ids, min(per, len(ids)), replace=False))
    return np.array(sorted(pick))


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("mode")
    ap.add_argument("--n", type=int, default=700)
    ap.add_argument("--api_n", type=int, default=0, help="改用闭源 API 评测的同一批样本（api_eval.py --n 同值）")
    a = ap.parse_args()
    meta = load_meta(a.ds).reset_index(drop=True)
    ok = meta.label7.isin(LABEL7).values
    test = np.where(ok & ((meta.split == "test").values if "split" in meta else True))[0]
    idx = sample(meta, test, a.n)
    if a.api_n:
        import pandas as pd
        sub = pd.read_csv(f"{WORK}/api_subset/{a.ds}/subset.csv")
        sub = sub.groupby("label7").head(max(1, a.api_n // sub.label7.nunique()))
        idx = np.sort(np.where(meta.key.isin(set(sub.key)))[0])

    proc = Qwen2_5OmniProcessor.from_pretrained(PATH)
    model = Qwen2_5OmniThinkerForConditionalGeneration.from_pretrained(
        PATH, dtype=torch.bfloat16, device_map="cuda", attn_implementation="sdpa").eval()
    tok = proc.tokenizer
    lids = [tok.encode(l, add_special_tokens=False)[0] for l in LABEL7]
    assert len(set(lids)) == 7

    P = np.full((len(meta), 7), np.nan, np.float32)
    for c, i in enumerate(idx):
        wav = f"{WORK}/{a.ds}/wav/{meta.key[i]}.wav"
        content = []
        if a.mode == "audio":
            content.append({"type": "audio", "audio": wav})
        else:
            content.append({"type": "video", "video": meta.video[i], "min_pixels": 32 * 28 * 28, "max_pixels": 64 * 28 * 28, "fps": 2.0,
                            "max_frames": 16})
            if a.mode in ("av", "avt"):
                content.append({"type": "audio", "audio": wav})
        text = Q[a.mode] + TAIL
        if a.mode == "avt":
            text += f'\nTranscript: "{meta.text[i]}"'
        content.append({"type": "text", "text": text})
        conv = [{"role": "system", "content": [{"type": "text", "text": SYS}]}, {"role": "user", "content": content}]
        prompt = proc.apply_chat_template(conv, add_generation_prompt=True, tokenize=False)
        audios, images, videos = process_mm_info(conv, use_audio_in_video=False)
        inp = proc(text=prompt, audio=audios, images=images, videos=videos, return_tensors="pt", padding=True,
                   use_audio_in_video=False).to("cuda").to(torch.bfloat16)
        with torch.no_grad():
            logits = model(**inp).logits[0, -1].float()
        P[i] = torch.softmax(logits[lids], -1).cpu().numpy()
        if c % 50 == 0:
            print(c, len(idx), flush=True)
    present = [c for c in LABEL7 if c in set(meta.label7.values[idx])]
    pi = [LABEL7.index(c) for c in present]
    pred = np.array(present)[P[idx][:, pi].argmax(-1)]
    log_result(task="omni", ds=a.ds, feat=f"qwen2.5_omni_7b_{a.mode}", space="label7", sampled=True, api_n=a.api_n,
               **metrics(meta.label7.values[idx], pred))
    np.savez(f"{WORK}/{a.ds}/pred_omni_{a.mode}{'_api' if a.api_n else ''}.npz", keys=meta.key.values, probs=P, idx=idx, classes=np.array(LABEL7))
