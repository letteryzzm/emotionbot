"""冻结特征 + 线性分类头（EmoBox 风格的 linear probe），说话人独立划分。

python probe.py <ds> <feat_name> [--space native|label7]
- 特征文件 ~/emo/work/<ds>/feat_<feat_name>.npz 的 feat 可以是 [N,D] 或 [N,L,D]（逐层，用验证集选层）
- 类别加权交叉熵，验证集上选 weight decay（和层）
- 测试集预测概率存到 pred_<feat_name>_<space>.npz，给融合用
"""
import argparse

import numpy as np
import torch
import torch.nn.functional as F

from common import LABEL7, WORK, folds, load_meta, log_result, mean_metrics, metrics

torch.manual_seed(0)
np.random.seed(0)


def train_linear(Xtr, ytr, n_cls, wd, epochs=400):
    mu, sd = Xtr.mean(0, keepdim=True), Xtr.std(0, keepdim=True) + 1e-5
    W = torch.zeros(Xtr.shape[1], n_cls, device="cuda", requires_grad=True)
    b = torch.zeros(n_cls, device="cuda", requires_grad=True)
    cnt = torch.bincount(ytr, minlength=n_cls).float()
    cw = (cnt.sum() / (n_cls * cnt.clamp(min=1)))
    opt = torch.optim.Adam([W, b], lr=1e-2, weight_decay=0)
    Z = (Xtr - mu) / sd
    for _ in range(epochs):
        opt.zero_grad()
        loss = F.cross_entropy(Z @ W + b, ytr, weight=cw) + wd * (W ** 2).sum()
        loss.backward()
        opt.step()
    return lambda X: torch.softmax(((X - mu) / sd) @ W + b, -1)


def inner_split(meta, tr):
    """从训练集按说话人切 15% 当验证集"""
    spk = meta.speaker.values[tr]
    us = np.unique(spk)
    rng = np.random.RandomState(0)
    val_spk = set(rng.choice(us, max(1, int(round(len(us) * 0.15))), replace=False))
    m = np.array([s in val_spk for s in spk])
    return tr[~m], tr[m]


def fit_select(X, y, tr, va, n_cls, layered):
    layers = range(X.shape[1]) if layered else [None]
    best = (-1, None, None)
    yt = torch.tensor(y, device="cuda")
    for L in layers:
        XL = X[:, L] if L is not None else X
        for wd in [1e-4, 1e-3, 1e-2]:
            f = train_linear(XL[tr], yt[tr], n_cls, wd)
            p = f(XL[va]).argmax(-1).cpu().numpy()
            ua = metrics(y[va], p)["UA"]
            if ua > best[0]:
                best = (ua, L, wd)
    return best


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("ds")
    ap.add_argument("feat")
    ap.add_argument("--space", default="native")
    ap.add_argument("--layer", default="", help="固定层：整数 / last / mean（对照 EmoBox，不做逐折选层）")
    a = ap.parse_args()

    meta = load_meta(a.ds)
    d = np.load(f"{WORK}/{a.ds}/feat_{a.feat}.npz", allow_pickle=True)
    assert (d["keys"] == meta.key.values).all()
    X = torch.tensor(d["feat"].astype(np.float32), device="cuda")
    layered = X.dim() == 3
    tag = a.feat
    if layered and a.layer:
        X = X.mean(1) if a.layer == "mean" else X[:, -1 if a.layer == "last" else int(a.layer)]
        layered, tag = False, f"{a.feat}@{a.layer}"

    if a.space == "native":
        classes = sorted(meta.native.unique())
        lab = meta.native.values
    else:
        classes = LABEL7
        lab = meta.label7.values
    keep = np.isin(lab, classes)
    y = np.array([classes.index(l) if l in classes else -1 for l in lab])

    rows, probs_all = [], np.full((len(meta), len(classes)), np.nan, dtype=np.float32)
    for name, tr, te, va in folds(a.ds, meta):
        tr, te = tr[keep[tr]], te[keep[te]]
        if va is None:
            tr_in, va = inner_split(meta, tr)
        else:
            va = va[keep[va]]
            tr_in = tr
        ua, L, wd = fit_select(X, y, tr_in, va, len(classes), layered)
        XL = X[:, L] if L is not None else X
        trf = np.concatenate([tr_in, va]) if a.ds in ("ravdess", "cremad") else tr
        f = train_linear(XL[trf], torch.tensor(y, device="cuda")[trf], len(classes), wd)
        P = f(XL[te]).detach().cpu().numpy()
        probs_all[te] = P
        r = metrics(y[te], P.argmax(-1))
        r.update(layer=L, wd=wd)
        rows.append(r)
    m = mean_metrics(rows)
    log_result(task="probe", ds=a.ds, feat=tag, space=a.space, folds=len(rows),
               layers=[r["layer"] for r in rows], **m)
    np.savez(f"{WORK}/{a.ds}/pred_{tag}_{a.space}.npz", keys=meta.key.values, probs=probs_all,
             classes=np.array(classes))


if __name__ == "__main__":
    main()
