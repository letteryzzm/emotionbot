"""TER 第三代：Qwen3-8B 零样本（单句 / 带上下文）与 QLoRA 微调（InstructERC 风格，带上下文）。

python ter_llm.py <ds> zs|zs_ctx|lora_ctx [--text gold|asr] [--train_n 20000]
打分方式：回答第一个 token 在 7 个标签词上的 logits 做 softmax（不做自由生成，避免格式问题）。
"""
import argparse
import os

import numpy as np
import torch
import torch.nn.functional as F
from transformers import AutoModelForCausalLM, AutoTokenizer, BitsAndBytesConfig

from common import LABEL7, MODELS, WORK, load_meta, log_result, metrics

CTX = 8
QWEN = f"{MODELS}/Qwen3-8B"

SYS = {
    "en": "You are an expert in emotion recognition in conversation.",
    "zh": "你是对话情绪识别专家。",
}
INSTR = {
    "en": ("Classify the emotion of the TARGET utterance into exactly one of: neutral, happy, sad, angry, surprise, "
           "fear, disgust. Answer with the single label word only."),
    "zh": ("判断【目标句】说话人的情绪，只能从以下英文标签中选一个：neutral, happy, sad, angry, surprise, fear, disgust。"
           "只回答一个标签词。"),
}


def contexts(meta):
    texts = meta.text.fillna("").astype(str).values
    ctx = [""] * len(meta)
    for _, g in meta.groupby("dialogue", sort=False):
        idx = g.sort_values("utt").index.values
        for j, i in enumerate(idx):
            ctx[i] = "\n".join(f"{meta.speaker[k]}: {texts[k]}" for k in idx[max(0, j - CTX):j])
    return ctx


def make_prompt(tok, lang, spk, text, ctx):
    if ctx is None:
        user = f"{INSTR[lang]}\n\nTARGET — {spk}: {text}" if lang == "en" else f"{INSTR[lang]}\n\n【目标句】{spk}：{text}"
    else:
        c = ctx if ctx else ("(no previous turns)" if lang == "en" else "（无上文）")
        user = (f"{INSTR[lang]}\n\nConversation so far:\n{c}\n\nTARGET — {spk}: {text}" if lang == "en"
                else f"{INSTR[lang]}\n\n对话上文：\n{c}\n\n【目标句】{spk}：{text}")
    msgs = [{"role": "system", "content": SYS[lang]}, {"role": "user", "content": user}]
    return tok.apply_chat_template(msgs, tokenize=False, add_generation_prompt=True, enable_thinking=False)


def label_ids(tok):
    ids = [tok.encode(l, add_special_tokens=False)[0] for l in LABEL7]
    assert len(set(ids)) == 7, ids
    return ids


@torch.no_grad()
def score(model, tok, prompts, lids, bs=16):
    tok.padding_side = "left"
    out = []
    for i in range(0, len(prompts), bs):
        enc = tok(prompts[i:i + bs], return_tensors="pt", padding=True).to("cuda")
        logits = model(**enc).logits[:, -1, :].float()
        out.append(torch.softmax(logits[:, lids], -1).cpu().numpy())
        if i % (bs * 100) == 0:
            print(i, len(prompts), flush=True)
    return np.concatenate(out)


def train_lora(model, tok, prompts, labels, lids, steps_bs=16, micro=4, lr=1e-4):
    from peft import LoraConfig, get_peft_model, prepare_model_for_kbit_training
    model = prepare_model_for_kbit_training(model, use_gradient_checkpointing=True)
    model = get_peft_model(model, LoraConfig(r=16, lora_alpha=32, lora_dropout=0.05, task_type="CAUSAL_LM",
                                             target_modules=["q_proj", "k_proj", "v_proj", "o_proj", "gate_proj",
                                                             "up_proj", "down_proj"]))
    opt = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=lr)
    n = len(prompts)
    total = n // steps_bs
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, lr, total_steps=total + 1, pct_start=0.05)
    tok.padding_side = "left"
    perm = np.random.RandomState(0).permutation(n)
    lid_t = torch.tensor(lids, device="cuda")
    model.train()
    for s in range(total):
        for m in range(steps_bs // micro):
            j = perm[s * steps_bs + m * micro: s * steps_bs + (m + 1) * micro]
            enc = tok([prompts[k] for k in j], return_tensors="pt", padding=True, truncation=True,
                      max_length=768).to("cuda")
            logits = model(**enc).logits[:, -1, :].float()
            # 只在 7 个标签 token 上算交叉熵（和推理打分方式一致）
            loss = F.cross_entropy(logits[:, lid_t], torch.tensor(labels[j], device="cuda")) / (steps_bs // micro)
            loss.backward()
        opt.step()
        sched.step()
        opt.zero_grad()
        if s % 50 == 0:
            print(f"step {s}/{total} loss {loss.item() * (steps_bs // micro):.3f}", flush=True)
    model.eval()
    return model


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("mode")
    ap.add_argument("--train_n", type=int, default=20000)
    a = ap.parse_args()
    lang = "zh" if a.ds == "cped" else "en"
    meta = load_meta(a.ds).reset_index(drop=True)
    ok = meta.label7.isin(LABEL7).values
    sp = meta.split.values
    tr, te = np.where((sp == "train") & ok)[0], np.where((sp == "test") & ok)[0]
    tok = AutoTokenizer.from_pretrained(QWEN)
    lids = label_ids(tok)
    use_ctx = a.mode != "zs"
    ctx = contexts(meta) if use_ctx else [None] * len(meta)
    texts = meta.text.fillna("").astype(str).values
    variants = {"gold": texts}
    if a.ds == "meld":
        sv = np.load(f"{WORK}/meld/feat_sensevoice.npz", allow_pickle=True)
        asr = texts.copy()
        asr[te] = sv["text"][te]
        variants["asr"] = asr

    if a.mode == "lora_ctx":
        q = BitsAndBytesConfig(load_in_4bit=True, bnb_4bit_quant_type="nf4", bnb_4bit_compute_dtype=torch.bfloat16,
                               bnb_4bit_use_double_quant=True)
        model = AutoModelForCausalLM.from_pretrained(QWEN, quantization_config=q, device_map="cuda",
                                                     dtype=torch.bfloat16)
        sub = np.random.RandomState(0).permutation(tr)[: a.train_n]
        prompts = [make_prompt(tok, lang, meta.speaker[i], texts[i], ctx[i]) for i in sub]
        labels = np.array([LABEL7.index(l) for l in meta.label7.values[sub]])
        model = train_lora(model, tok, prompts, labels, lids)
        model.save_pretrained(f"{WORK}/{a.ds}/lora_qwen3_8b")
    else:
        model = AutoModelForCausalLM.from_pretrained(QWEN, dtype=torch.bfloat16, device_map="cuda").eval()

    for name, tx in variants.items():
        prompts = [make_prompt(tok, lang, meta.speaker[i], tx[i], ctx[i]) for i in te]
        P = np.zeros((len(meta), 7), np.float32)
        P[te] = score(model, tok, prompts, lids)
        pred = np.array(LABEL7)[P[te].argmax(-1)]
        log_result(task="ter", ds=a.ds, feat=f"qwen3_8b_{a.mode}", text=name, space="label7",
                   **metrics(meta.label7.values[te], pred))
        np.savez(f"{WORK}/{a.ds}/pred_ter_qwen3_8b_{a.mode}_{name}.npz", keys=meta.key.values, probs=P,
                 classes=np.array(LABEL7))
