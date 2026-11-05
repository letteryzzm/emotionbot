"""人脸侧：逐帧特征 / 零样本概率。

python fer_feats.py <ds> <model>
model:
  hog            64x64 灰度 HOG（第一代基线），逐帧后取平均
  enet_b0_8_va_mtl / enet_b2_8   EmotiEffLib（AffectNet 训练），逐帧特征 + 8 类概率（+ V/A）
输出: ~/emo/work/<ds>/feat_<model>.npz
  feat [N,D] 帧平均特征; frame_probs [N,16,8]; mask [N,16]; va [N,16,2]（仅 mtl）
"""
import os
import sys

import cv2
import numpy as np
import torch
from tqdm import tqdm

from common import WORK, load_meta

T = 16


def load_faces(ds, key):
    p = f"{WORK}/{ds}/face/{key}.npy"
    return np.load(p) if os.path.exists(p) else None


def run_hog(ds, keys):
    from skimage.feature import hog as sk_hog
    hog = lambda x: sk_hog(x, orientations=9, pixels_per_cell=(8, 8), cells_per_block=(2, 2), feature_vector=True)
    feats = []
    for k in tqdm(keys, mininterval=30):
        f = load_faces(ds, k)
        if f is None:
            feats.append(np.zeros(1764, np.float32))
            continue
        g = [cv2.resize(cv2.cvtColor(x, cv2.COLOR_RGB2GRAY), (64, 64)) for x in f]
        feats.append(np.mean([hog(x) for x in g], 0))
    return dict(feat=np.stack(feats).astype(np.float32))


@torch.no_grad()
def run_eff(ds, keys, name):
    from emotiefflib.facial_analysis import EmotiEffLibRecognizer

    class Fast:
        """和 EmotiEffLib 同样的权重和预处理（Resize + ImageNet 归一化），但整批在 GPU 上做。"""

        def __init__(self, name):
            self.rec = EmotiEffLibRecognizer(engine="torch", model_name=name, device="cuda")
            self.rec.model.half()
            self.size = self.rec.img_size
            self.mean = torch.tensor(self.rec.mean, device="cuda").view(1, 3, 1, 1)
            self.std = torch.tensor(self.rec.std, device="cuda").view(1, 3, 1, 1)

        def extract_features(self, frames):
            x = torch.from_numpy(np.stack(frames)).cuda().permute(0, 3, 1, 2).float() / 255
            x = F.interpolate(x, size=(self.size, self.size), mode="bilinear", align_corners=False)
            return self.rec.model(((x - self.mean) / self.std).half()).float().cpu().numpy()

        def classify_emotions(self, ft, logits=False):
            return self.rec.classify_emotions(ft, logits=logits)

    import torch.nn.functional as F
    rec = Fast(name)
    mtl = "_mtl" in name
    D = None
    feats, fprobs, masks, vas = [], [], [], []
    for k in tqdm(keys, mininterval=30):
        f = load_faces(ds, k)
        if f is None:
            feats.append(None)
            fprobs.append(np.zeros((T, 8), np.float32))
            masks.append(np.zeros(T, bool))
            vas.append(np.zeros((T, 2), np.float32))
            continue
        ft = rec.extract_features(list(f))
        D = ft.shape[1]
        _, sc = rec.classify_emotions(ft, logits=False)
        n = len(f)
        pr, va, m = np.zeros((T, 8), np.float32), np.zeros((T, 2), np.float32), np.zeros(T, bool)
        pr[:n] = sc[:, :8]
        if mtl:
            va[:n] = sc[:, 8:10]
        m[:n] = True
        feats.append(ft.mean(0))
        fprobs.append(pr)
        masks.append(m)
        vas.append(va)
    feats = np.stack([x if x is not None else np.zeros(D, np.float32) for x in feats])
    d = dict(feat=feats.astype(np.float32), frame_probs=np.stack(fprobs), mask=np.stack(masks),
             classes=np.array(["Anger", "Contempt", "Disgust", "Fear", "Happiness", "Neutral", "Sadness", "Surprise"]))
    if mtl:
        d["va"] = np.stack(vas)
    return d


if __name__ == "__main__":
    ds, model = sys.argv[1], sys.argv[2]
    meta = load_meta(ds)
    d = run_hog(ds, meta.key) if model == "hog" else run_eff(ds, meta.key, model)
    np.savez(f"{WORK}/{ds}/feat_{model}.npz", keys=meta.key.values, **d)
    print("saved", {k: getattr(v, "shape", None) for k, v in d.items()})
