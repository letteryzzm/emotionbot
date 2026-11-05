"""晚融合：把各模态的 7 类概率合起来。

python fusion.py <ds> <name=pred_file> [<name=pred_file> ...]
  pred_file 是 ~/emo/work/<ds>/ 下的 pred_*.npz（不含 pred_ 前缀和 .npz 后缀）
两种融合：
  avg    log 概率等权平均（完全不调参）
  stack  逻辑回归 stacker，按说话人 / 对话分组 5 折交叉验证（测试集内部 CV，同一组不跨折）
只在所有模态都有预测的样本上评测；同时报告每个单模态在同一子集上的数字，保证可比。
"""
import sys

import numpy as np
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import GroupKFold

from common import LABEL7, WORK, load_meta, log_result, metrics


def load(ds, meta, f):
    d = np.load(f"{WORK}/{ds}/pred_{f}.npz", allow_pickle=True)
    assert (d["keys"] == meta.key.values).all()
    P = d["probs"].astype(np.float64)
    cls = list(d["classes"])
    if cls != LABEL7:  # 映射到 LABEL7 顺序
        Q = np.full((len(P), 7), np.nan)
        for j, c in enumerate(cls):
            if c in LABEL7:
                Q[:, LABEL7.index(c)] = P[:, j]
        P = Q
    return P


if __name__ == "__main__":
    ds = sys.argv[1]
    specs = [s.split("=") for s in sys.argv[2:]]
    meta = load_meta(ds).reset_index(drop=True)
    present = [c for c in LABEL7 if c in set(meta.label7)]
    pi = [LABEL7.index(c) for c in present]
    Ps = {n: load(ds, meta, f)[:, pi] for n, f in specs}
    m = meta.label7.isin(present).values.copy()
    if "split" in meta and ds != "ravdess":
        m &= (meta.split == "test").values
    for P in Ps.values():
        m &= ~np.isnan(P).any(1)
    idx = np.where(m)[0]
    y = meta.label7.values[idx]
    tag = "+".join(n for n, _ in specs)
    for n, P in Ps.items():
        log_result(task="fusion_single", ds=ds, feat=n, combo=tag, **metrics(y, np.array(present)[P[idx].argmax(1)]))
    L = [np.log(np.clip(P[idx], 1e-6, 1)) for P in Ps.values()]
    avg = np.mean(L, 0)
    log_result(task="fusion", ds=ds, feat=f"avg[{tag}]", **metrics(y, np.array(present)[avg.argmax(1)]))
    X = np.concatenate(L, 1)
    groups = meta.dialogue.values[idx] if "dialogue" in meta else meta.speaker.values[idx]
    pred = np.empty(len(idx), dtype=object)
    for tr, te in GroupKFold(5).split(X, y, groups):
        clf = LogisticRegression(max_iter=2000, class_weight="balanced", C=1.0).fit(X[tr], y[tr])
        pred[te] = clf.predict(X[te])
    log_result(task="fusion", ds=ds, feat=f"stack[{tag}]", **metrics(y, pred.astype(str)))
