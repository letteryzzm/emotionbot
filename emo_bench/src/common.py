import json
import os
import time

import numpy as np
import pandas as pd
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

HOME = os.path.expanduser("~/emo")
WORK = f"{HOME}/work"
MODELS = f"{HOME}/models"
RESULTS = os.path.expanduser("~/work/emo_results/results.jsonl")  # 持久盘
LABEL7 = ["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"]


def load_meta(ds):
    m = pd.read_csv(f"{WORK}/{ds}/meta.csv")
    return m


def folds(ds, meta):
    """返回 [(fold_name, train_idx, test_idx, valid_idx)]，都是说话人独立的划分。"""
    if ds == "ravdess":  # EmoBox 6 折
        out = []
        for f in sorted(meta.test_fold.unique()):
            te = np.where(meta.test_fold == f)[0]
            tr_all = np.where(meta.test_fold != f)[0]
            out.append((f"fold{f}", tr_all, te, None))
        return out
    if ds == "cremad":
        return [("fold1", np.where(meta.split == "train")[0], np.where(meta.split == "test")[0], None)]
    if ds in ("meld", "cped"):
        return [("official", np.where(meta.split == "train")[0], np.where(meta.split == "test")[0],
                 np.where(meta.split == "valid")[0])]
    raise ValueError(ds)


def metrics(y_true, y_pred):
    y_true, y_pred = np.asarray(y_true), np.asarray(y_pred)
    return dict(
        UA=100 * balanced_accuracy_score(y_true, y_pred),
        WA=100 * accuracy_score(y_true, y_pred),
        macroF1=100 * f1_score(y_true, y_pred, average="macro"),
        wF1=100 * f1_score(y_true, y_pred, average="weighted"),
        n=int(len(y_true)),
    )


def log_result(**kw):
    kw["time"] = time.strftime("%Y-%m-%d %H:%M:%S")
    os.makedirs(os.path.dirname(RESULTS), exist_ok=True)
    with open(RESULTS, "a") as f:
        f.write(json.dumps(kw, ensure_ascii=False) + "\n")
    print(json.dumps({k: (round(v, 2) if isinstance(v, float) else v) for k, v in kw.items()}, ensure_ascii=False),
          flush=True)


def mean_metrics(rows):
    keys = ["UA", "WA", "macroF1", "wF1"]
    out = {k: float(np.mean([r[k] for r in rows])) for k in keys}
    out["n"] = int(sum(r["n"] for r in rows))
    return out
