"""零样本评测（不在目标数据上训练）：emotion2vec+ 9 类头、SenseVoice 情感标签、EmotiEffLib（AffectNet 头）、
audeering / EmotiEffLib 的 V/A 维度检验。

python zeroshot.py <ds>
约定：概率模型只在该数据集出现的 7 类子集里取 argmax（标签受限的零样本）；SenseVoice 是硬标签，EMO_UNKNOWN 记为 neutral。
"""
import os
import sys

import numpy as np
from sklearn.metrics import roc_auc_score

from common import LABEL7, WORK, load_meta, log_result, metrics

E2V = {"angry": "angry", "disgusted": "disgust", "fearful": "fear", "happy": "happy", "neutral": "neutral",
       "sad": "sad", "surprised": "surprise"}
SV = {"HAPPY": "happy", "SAD": "sad", "ANGRY": "angry", "NEUTRAL": "neutral", "FEARFUL": "fear",
      "DISGUSTED": "disgust", "SURPRISED": "surprise", "EMO_UNKNOWN": "neutral"}
EFF = {"Anger": "angry", "Disgust": "disgust", "Fear": "fear", "Happiness": "happy", "Neutral": "neutral",
       "Sadness": "sad", "Surprise": "surprise"}
HIGH_A, LOW_A = {"angry", "happy", "fear", "surprise"}, {"sad", "neutral"}
POS_V, NEG_V = {"happy"}, {"angry", "sad", "disgust", "fear"}


def to7(P, names, mapping):
    out = np.zeros((len(P), 7), np.float32)
    for j, n in enumerate(names):
        n = str(n).split("/")[-1]
        if n in mapping:
            out[:, LABEL7.index(mapping[n])] += P[:, j]
    return out


def evaluate(ds, meta, P7, name, test_mask):
    present = [c for c in LABEL7 if c in set(meta.label7)]
    idx = [LABEL7.index(c) for c in present]
    m = test_mask & meta.label7.isin(present).values
    pred = np.array(present)[P7[m][:, idx].argmax(-1)]
    log_result(task="zeroshot", ds=ds, feat=name, space="label7", **metrics(meta.label7.values[m], pred))
    np.savez(f"{WORK}/{ds}/pred_{name}_zs.npz", keys=meta.key.values, probs=P7, classes=np.array(LABEL7))


def dim_check(ds, meta, val, aro, name, test_mask):
    lab = meta.label7.values
    r = {}
    m = test_mask & np.isin(lab, list(HIGH_A | LOW_A))
    r["arousal_AUC_high_vs_low"] = 100 * roc_auc_score(np.isin(lab[m], list(HIGH_A)), aro[m])
    m = test_mask & np.isin(lab, list(POS_V | NEG_V))
    r["valence_AUC_pos_vs_neg"] = 100 * roc_auc_score(np.isin(lab[m], list(POS_V)), val[m])
    if "intensity" in meta:  # RAVDESS: strong(2) vs normal(1)，排除 neutral
        m = test_mask & (lab != "neutral") & (lab != "other")
        r["arousal_AUC_strong_vs_normal"] = 100 * roc_auc_score(meta.intensity.values[m] == 2, aro[m])
    log_result(task="dimension", ds=ds, feat=name, n=int(test_mask.sum()), **r)


if __name__ == "__main__":
    ds = sys.argv[1]
    meta = load_meta(ds)
    # RAVDESS 全部样本都在某个测试折里；CREMA-D / MELD 只用测试集
    test = np.ones(len(meta), bool) if ds == "ravdess" else (meta.split == "test").values
    f = lambda n: f"{WORK}/{ds}/feat_{n}.npz"
    if os.path.exists(f("e2v_plus")):
        d = np.load(f("e2v_plus"), allow_pickle=True)
        evaluate(ds, meta, to7(d["probs"], d["labels"], E2V), "e2v_plus", test)
    for sv in ["sensevoice", "sensevoice_ban"]:
        if os.path.exists(f(sv)):
            d = np.load(f(sv), allow_pickle=True)
            P = np.zeros((len(meta), 7), np.float32)
            for i, t in enumerate(d["tag"]):
                if t in SV:
                    P[i, LABEL7.index(SV[t])] = 1
            evaluate(ds, meta, P, sv, test)
    for n in ["enet_b0_8_va_mtl", "enet_b2_8"]:
        if os.path.exists(f(n)):
            d = np.load(f(n), allow_pickle=True)
            mk = d["mask"]
            Pm = (d["frame_probs"] * mk[..., None]).sum(1) / np.maximum(mk.sum(1, keepdims=True), 1)
            evaluate(ds, meta, to7(Pm, d["classes"], EFF), n, test & (mk.sum(1) > 0))
            if "va" in d:
                va = (d["va"] * mk[..., None]).sum(1) / np.maximum(mk.sum(1, keepdims=True), 1)
                dim_check(ds, meta, va[:, 0], va[:, 1], n, test & (mk.sum(1) > 0))
    if os.path.exists(f("audeering")):
        adv = np.load(f("audeering"))["adv"]
        dim_check(ds, meta, adv[:, 2], adv[:, 0], "audeering", test)
