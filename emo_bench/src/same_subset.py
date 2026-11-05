"""闭源 API vs 本地模型：在同一批分层抽样（每个数据集 56 条）上算 UA / macro-F1。

python src/same_subset.py [--n 56] > results/same_subset.md
本地模型读 results/preds/<ds>/pred_*.npz，闭源读 results/api_cache/*.jsonl（每个 key 取最后一条成功回答）。
"""
import argparse
import glob
import json
import os

import numpy as np
import pandas as pd
from sklearn.metrics import balanced_accuracy_score, f1_score

from api_eval import LABEL7, parse

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # emo_bench/
PRED = f"{ROOT}/results/preds"
DS = {"ravdess": "ravdess", "cremad": "cremad", "meld": "meld", "ter_cped": "cped"}
LOCAL = {  # 展示名 -> pred 文件（不含 pred_ 和 .npz）
    "ravdess": {"WavLM 探针 (A)": "wavlm_label7", "emotion2vec+ 零样本 (A)⚠": "e2v_plus_zs",
                "EmotiEffNet 探针 (V)": "enet_b0_8_va_mtl_label7", "DFER-CLIP 零样本 (V)": "dfer_clip_dfew_zs",
                "Qwen2.5-Omni-7B audio": "omni_audio_api", "Qwen2.5-Omni-7B video": "omni_video_api",
                "Qwen2.5-Omni-7B av": "omni_av_api"},
    "meld": {"WavLM 探针 (A)": "wavlm_label7", "EmotiEffNet 探针 (V)": "enet_b0_8_va_mtl_label7",
             "RoBERTa 微调 (T)": "ter_roberta_gold", "Qwen3-8B LoRA+ctx (T)": "ter_qwen3_8b_lora_ctx_gold",
             "Qwen3-8B LoRA+ctx (T, ASR 文本)": "ter_qwen3_8b_lora_ctx_asr",
             "Qwen2.5-Omni-7B audio": "omni_audio_api", "Qwen2.5-Omni-7B av": "omni_av_api",
             "Qwen2.5-Omni-7B avt": "omni_avt_api"},
    "cped": {"RoBERTa 微调+ctx (T)": "ter_roberta_ctx_gold", "Qwen3-8B 零样本+ctx (T)": "ter_qwen3_8b_zs_ctx_gold",
             "Qwen3-8B LoRA+ctx (T)": "ter_qwen3_8b_lora_ctx_gold"},
}
LOCAL["cremad"] = {k: v for k, v in LOCAL["ravdess"].items()}
AV = ["wavlm_label7", "enet_b0_8_va_mtl_label7"]
FUSE = {  # late fusion：log 概率等权平均（和 fusion.py 的 avg 一致）
    "ravdess": {"late fusion avg A+V": AV}, "cremad": {"late fusion avg A+V": AV},
    "meld": {"late fusion avg A+V+T": AV + ["ter_qwen3_8b_lora_ctx_gold"],
             "late fusion avg A+V+T (ASR 文本)": AV + ["ter_qwen3_8b_lora_ctx_asr"]},
}


def score(y, pred, labels):
    return 100 * balanced_accuracy_score(y, pred), 100 * f1_score(y, pred, labels=labels, average="macro")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=56)
    a = ap.parse_args()
    out = []
    for api_ds, ds in DS.items():
        sub = pd.read_csv(f"{ROOT}/data/api_subset/{api_ds}/subset.csv")
        sub = sub.groupby("label7").head(max(1, a.n // sub.label7.nunique()))
        labels = [c for c in LABEL7 if c in set(sub.label7)]
        rows = []
        meta = pd.read_csv(f"{PRED}/{ds}/meta.csv")
        pos = {k: i for i, k in enumerate(meta.key)}
        idx = [pos[k] for k in sub.key]

        def sub_probs(f):
            d = np.load(f"{PRED}/{ds}/pred_{f}.npz", allow_pickle=True)
            cls = list(d["classes"])
            return d["probs"][idx][:, [cls.index(c) for c in labels]]

        items = [(n, [f]) for n, f in LOCAL.get(ds, {}).items()] + list(FUSE.get(ds, {}).items())
        for name, fs in items:
            if not all(os.path.exists(f"{PRED}/{ds}/pred_{f}.npz") for f in fs):
                continue
            Pi = sub_probs(fs[0]) if len(fs) == 1 else np.mean(
                [np.log(np.clip(sub_probs(f), 1e-6, 1)) for f in fs], 0)
            ok = ~np.isnan(Pi).any(1)
            pred = np.array(labels)[np.nan_to_num(Pi, nan=-1).argmax(1)]
            ua, f1 = score(sub.label7.values[ok], pred[ok], labels)
            rows.append(("本地", name, ua, f1, int(ok.sum())))
        for cf in sorted(glob.glob(f"{ROOT}/results/api_cache/*__{api_ds}__*.jsonl")):
            prov, model, _, mode = os.path.basename(cf)[:-6].split("__")
            ans = {}
            for line in open(cf):
                r = json.loads(line)
                if "answer" in r:
                    ans[r["key"]] = r["answer"]
            keys = [k for k in sub.key if k in ans]
            if len(keys) < 0.8 * len(sub):
                continue
            y = sub.set_index("key").loc[keys].label7.values
            pred = [parse(ans[k]) for k in keys]
            ua, f1 = score(y, pred, labels)
            rows.append((prov, f"{model.replace('_', '/', 1) if prov == 'openrouter' else model} {mode}", ua, f1,
                         len(keys)))
        out.append(f"\n### {api_ds}（{len(sub)} 条，{len(labels)} 类，随机 UA = {100 / len(labels):.1f}）\n")
        out.append("| 来源 | 方法 | UA | macro-F1 | n |\n|---|---|---|---|---|")
        for r in sorted(rows, key=lambda r: -r[2]):
            out.append(f"| {r[0]} | {r[1]} | {r[2]:.1f} | {r[3]:.1f} | {r[4]} |")
    print("\n".join(out))


if __name__ == "__main__":
    main()
