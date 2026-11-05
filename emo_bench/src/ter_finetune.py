"""TER 第一代 / 第二代：TF-IDF+LR，RoBERTa 微调（单句 vs 带上下文），j-hartmann 现成模型零样本。

python ter_finetune.py <ds> tfidf|roberta|roberta_ctx|jhartmann [--text gold|asr]
- label7 空间（other 排除）。MELD 用 roberta-base，CPED 用 chinese-roberta-wwm-ext
- --text asr：测试集文本换成 SenseVoice 转写（只对 MELD），训练仍用标注文本
"""
import argparse

import numpy as np
import pandas as pd
import torch
import torch.nn.functional as F
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from common import LABEL7, MODELS, WORK, load_meta, log_result, metrics

CTX = 3  # 上文句数


def build_inputs(meta, ctx):
    texts = meta.text.fillna("").astype(str).values
    if not ctx:
        return list(texts), None
    prev = []
    for d, g in meta.groupby("dialogue", sort=False):
        g = g.sort_values("utt")
        idx = g.index.values
        for j, i in enumerate(idx):
            c = [f"{meta.speaker[k]}: {texts[k]}" for k in idx[max(0, j - CTX):j]]
            prev.append((i, " ".join(c)))
    prev = dict(prev)
    return [f"{meta.speaker[i]}: {texts[i]}" for i in range(len(meta))], [prev.get(i, "") for i in range(len(meta))]


def run_tfidf(meta, tr, te, ds):
    vec = TfidfVectorizer(analyzer="char_wb" if ds == "cped" else "word", ngram_range=(1, 3) if ds == "cped" else (1, 2),
                          min_df=2, sublinear_tf=True, max_features=200000)
    X = vec.fit_transform(meta.text.fillna(""))
    y = meta.label7.values
    clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=2.0).fit(X[tr], y[tr])
    P = np.zeros((len(meta), 7), np.float32)
    pp = clf.predict_proba(X[te])
    for j, c in enumerate(clf.classes_):
        P[te, LABEL7.index(c)] = pp[:, j]
    return P


@torch.no_grad()
def predict(model, tok, a, b, idx, bs=64):
    out = []
    for i in range(0, len(idx), bs):
        j = idx[i:i + bs]
        enc = tok([a[k] for k in j], [b[k] for k in j] if b else None, truncation="only_first" if not b else "longest_first",
                  max_length=256, padding=True, return_tensors="pt").to("cuda")
        with torch.autocast("cuda", dtype=torch.bfloat16):
            out.append(torch.softmax(model(**enc).logits.float(), -1).cpu().numpy())
    return np.concatenate(out)


def run_roberta(meta, tr, va, te, ds, ctx, test_texts=None):
    torch.manual_seed(0)
    path = f"{MODELS}/{'chinese-roberta-wwm-ext' if ds == 'cped' else 'roberta-base'}"
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path, num_labels=7).cuda()
    a, b = build_inputs(meta, ctx)
    # 句子对：第一段是目标句，第二段是上文（截断优先截上文）
    if b is not None:
        a, b = a, b
    y = torch.tensor([LABEL7.index(l) if l in LABEL7 else -100 for l in meta.label7])
    opt = torch.optim.AdamW(model.parameters(), lr=2e-5, weight_decay=0.01)
    epochs, bs = 4, 32
    steps = epochs * (len(tr) // bs + 1)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, 2e-5, total_steps=steps, pct_start=0.1, anneal_strategy="linear")
    best, best_state = -1, None
    for ep in range(epochs):
        model.train()
        perm = np.random.RandomState(ep).permutation(tr)
        for i in range(0, len(perm), bs):
            j = perm[i:i + bs]
            enc = tok([a[k] for k in j], [b[k] for k in j] if b else None, truncation=True, max_length=256,
                      padding=True, return_tensors="pt").to("cuda")
            with torch.autocast("cuda", dtype=torch.bfloat16):
                loss = F.cross_entropy(model(**enc).logits.float(), y[j].cuda())
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            opt.zero_grad()
        model.eval()
        pv = predict(model, tok, a, b, va)
        f1 = metrics(meta.label7.values[va], np.array(LABEL7)[pv.argmax(-1)])["macroF1"]
        print(f"epoch {ep} val macroF1 {f1:.2f}", flush=True)
        if f1 > best:
            best, best_state = f1, {k: v.detach().clone() for k, v in model.state_dict().items()}
    model.load_state_dict(best_state)
    model.eval()
    res = {}
    for name, texts in [("gold", None)] + ([("asr", test_texts)] if test_texts is not None else []):
        aa = list(a)
        if texts is not None:
            for k in te:
                aa[k] = f"{meta.speaker[k]}: {texts[k]}" if ctx else texts[k]
        P = np.zeros((len(meta), 7), np.float32)
        P[te] = predict(model, tok, aa, b, te)
        res[name] = P
    return res


@torch.no_grad()
def run_jhartmann(meta, te):
    path = f"{MODELS}/emotion-english-distilroberta-base"
    tok = AutoTokenizer.from_pretrained(path)
    model = AutoModelForSequenceClassification.from_pretrained(path).cuda().eval()
    names = [model.config.id2label[i] for i in range(model.config.num_labels)]
    mp = {"anger": "angry", "disgust": "disgust", "fear": "fear", "joy": "happy", "neutral": "neutral",
          "sadness": "sad", "surprise": "surprise"}
    texts = meta.text.fillna("").tolist()
    P = np.zeros((len(meta), 7), np.float32)
    pp = predict(model, tok, texts, None, te)
    for j, n in enumerate(names):
        P[te, LABEL7.index(mp[n])] = pp[:, j]
    return P


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("method")
    a = ap.parse_args()
    meta = load_meta(a.ds).reset_index(drop=True)
    ok = meta.label7.isin(LABEL7).values
    sp = meta.split.values
    tr, va, te = [np.where((sp == s) & ok)[0] for s in ["train", "valid", "test"]]
    asr = None
    if a.ds == "meld":
        sv = np.load(f"{WORK}/meld/feat_sensevoice.npz", allow_pickle=True)
        assert (sv["keys"] == meta.key.values).all()
        asr = sv["text"]
    if a.method == "tfidf":
        outs = {"gold": run_tfidf(meta, tr, te, a.ds)}
    elif a.method == "jhartmann":
        outs = {"gold": run_jhartmann(meta, te)}
    else:
        outs = run_roberta(meta, tr, va, te, a.ds, a.method == "roberta_ctx", asr)
    for name, P in outs.items():
        pred = np.array(LABEL7)[P[te].argmax(-1)]
        log_result(task="ter", ds=a.ds, feat=a.method, text=name, space="label7", **metrics(meta.label7.values[te], pred))
        np.savez(f"{WORK}/{a.ds}/pred_ter_{a.method}_{name}.npz", keys=meta.key.values, probs=P, classes=np.array(LABEL7))
