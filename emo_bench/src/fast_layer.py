"""推荐方案的离线验证：快层 = 零样本 SenseVoice / emotion2vec+（语音）+ EmotiEffNet-B0 AffectNet 头（人脸），
不在目标数据上训练任何东西；慢层 = qwen3.8-omni-flash（百炼）；混合 = 快层概率 + 慢层标签一起做 log 平均。

python src/fast_layer.py > results/fast_layer.md
快层在完整测试集和 56 条子集上都算；慢层 / 混合只有 56 条子集（闭源只跑了这些）。
"""
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

from api_eval import LABEL7, parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # emo_bench/
PRED = f"{ROOT}/results/preds"
HARD = 0.7  # 硬标签（SenseVoice、闭源回答）转概率：预测类 0.7，其余平分

SV, E2V, ENET = "sensevoice_ban_zs", "e2v_plus_zs", "enet_b0_8_va_mtl_zs"
CONFIGS = {  # 展示名 -> pred 文件；⚠ = 含 emotion2vec+（训练数据含 RAVDESS / CREMA-D / MELD 训练集）
    "A: SenseVoice": [SV],
    "A: emotion2vec+ ⚠": [E2V],
    "V: EmotiEffNet-B0 零样本": [ENET],
    "快层 SenseVoice + EmotiEffNet": [SV, ENET],
    "快层 emotion2vec+ + EmotiEffNet ⚠": [E2V, ENET],
    "快层 三个都用 ⚠": [SV, E2V, ENET],
}
SLOW = {"ravdess": "av", "cremad": "av", "meld": "avt"}  # 慢层用该数据集上最好的输入方式


def hard_to_prob(P):
    """one-hot（或近似 one-hot）→ 平滑概率，避免 log(0) 一票否决其他模态。"""
    out = np.full_like(P, (1 - HARD) / (P.shape[1] - 1))
    out[np.arange(len(P)), P.argmax(1)] = HARD
    return np.where(np.isnan(P).any(1, keepdims=True), np.nan, out)


def load(ds, f, labels):
    d = np.load(f"{PRED}/{ds}/pred_{f}.npz", allow_pickle=True)
    P = d["probs"][:, [list(d["classes"]).index(c) for c in labels]]
    return hard_to_prob(P) if f == SV else P


def fuse(Ps):
    L = np.mean([np.log(np.clip(P, 1e-6, 1)) for P in Ps], 0)
    return L


def score(y, P, labels):
    ok = ~np.isnan(P).any(1)
    pred = np.array(labels)[np.nan_to_num(P, nan=-np.inf)[ok].argmax(1)]
    return (100 * balanced_accuracy_score(y[ok], pred),
            100 * f1_score(y[ok], pred, labels=labels, average="macro"), int(ok.sum()))


def slow_probs(ds, keys, labels):
    """qwen3.8-omni-flash 每条的回答 → 平滑概率；没有回答的是 NaN。"""
    ans = {}
    for line in open(f"{ROOT}/results/api_cache/dashscope__qwen3.8-omni-flash__{ds}__{SLOW[ds]}.jsonl"):
        r = json.loads(line)
        if "answer" in r:
            ans[r["key"]] = r["answer"]
    P = np.full((len(keys), len(labels)), np.nan)
    for i, k in enumerate(keys):
        lab = parse(ans[k]) if k in ans else None
        if lab in labels:
            P[i] = (1 - HARD) / (len(labels) - 1)
            P[i, labels.index(lab)] = HARD
    return P


def main():
    out = []
    for ds in ["ravdess", "cremad", "meld"]:
        meta = pd.read_csv(f"{PRED}/{ds}/meta.csv")
        test = np.ones(len(meta), bool) if ds == "ravdess" else (meta.split == "test").values.copy()
        sub = pd.read_csv(f"{ROOT}/data/api_subset/{ds}/subset.csv")
        sub = sub.groupby("label7").head(56 // sub.label7.nunique())
        labels = [c for c in LABEL7 if c in set(meta.label7[test]) | set(sub.label7)]
        test &= meta.label7.isin(labels).values
        pos = {k: i for i, k in enumerate(meta.key)}
        idx = np.array([pos[k] for k in sub.key])
        y_full, y_sub = meta.label7.values[test], sub.label7.values

        rows = []
        for name, fs in CONFIGS.items():
            Ps = [load(ds, f, labels) for f in fs]
            P = Ps[0] if len(Ps) == 1 else fuse(Ps)
            rows.append((name, *score(y_full, P[test], labels), *score(y_sub, P[idx], labels)))
        S = slow_probs(ds, list(sub.key), labels)
        rows.append((f"慢层 qwen3.8-omni-flash {SLOW[ds]}", None, None, None, *score(y_sub, S, labels)))
        for name, fs in [("混合 = 快层(SV+ENet) + 慢层", [SV, ENET]), ("混合 = 快层(三个) + 慢层 ⚠", [SV, E2V, ENET])]:
            P = fuse([load(ds, f, labels)[idx] for f in fs] + [S])
            rows.append((name, None, None, None, *score(y_sub, P, labels)))

        out.append(f"\n### {ds}（完整测试 {test.sum()} 条 / 子集 {len(sub)} 条，{len(labels)} 类，随机 UA {100 / len(labels):.1f}）\n")
        out.append("| 方案 | 完整 UA | 完整 macro-F1 | 子集 UA | 子集 macro-F1 | 子集 n |\n|---|---|---|---|---|---|")
        for r in rows:
            full = "| – | –" if r[1] is None else f"| {r[1]:.1f} | {r[2]:.1f}"
            out.append(f"| {r[0]} {full} | {r[4]:.1f} | {r[5]:.1f} | {r[6]} |")
    print("\n".join(out))


if __name__ == "__main__":
    main()
