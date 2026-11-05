"""动态 FER：DFER-CLIP（DFEW fold1 官方权重）跨数据集零样本。

python dfer_clip_eval.py <ds>
输入用 prep.py 存的 16 帧人脸裁剪（和 DFER-CLIP 测试设置一致：16 段、224、只 /255 不做 CLIP 归一化）。
DFEW 的 7 类和我们的 LABEL7 一致，只是顺序不同。
"""
import os
import sys
from types import SimpleNamespace

import numpy as np
import torch

from common import LABEL7, MODELS, WORK, load_meta, log_result, metrics

sys.path.insert(0, f"{MODELS}/dfer-clip")
from clip import clip  # noqa: E402
from clip.model import build_model  # noqa: E402
from models.Generate_Model import GenerateModel  # noqa: E402
from models.Text import class_descriptor_7  # noqa: E402

DFEW_ORDER = ["happy", "sad", "neutral", "angry", "surprise", "disgust", "fear"]

if __name__ == "__main__":
    ds = sys.argv[1]
    ck = torch.load(f"{MODELS}/dferclip_dfew_fold1.pth", map_location="cpu", weights_only=False)
    sd = ck.get("state_dict", ck)
    sd = {k.replace("module.", ""): v for k, v in sd.items()}
    clip_sd = {k[len("clip_model_."):]: v for k, v in sd.items() if k.startswith("clip_model_.")}
    clip_model = build_model(clip_sd).float()
    args = SimpleNamespace(contexts_number=8, class_token_position="end", class_specific_contexts="True", load_and_tune_prompt_learner="False",
                           temporal_layers=1)
    model = GenerateModel(input_text=class_descriptor_7, clip_model=clip_model, args=args)
    missing, unexpected = model.load_state_dict(sd, strict=False)
    print("missing", len(missing), "unexpected", len(unexpected))
    model = model.cuda().eval()

    meta = load_meta(ds)
    test = np.ones(len(meta), bool) if ds == "ravdess" else (meta.split == "test").values
    P = np.full((len(meta), 7), np.nan, np.float32)
    with torch.no_grad():
        for i, k in enumerate(meta.key):
            p = f"{WORK}/{ds}/face/{k}.npy"
            if not test[i] or not os.path.exists(p):
                continue
            f = np.load(p)
            if len(f) < 16:
                f = np.concatenate([f, np.repeat(f[-1:], 16 - len(f), 0)])
            x = torch.from_numpy(f).float().div(255).permute(0, 3, 1, 2)[None].cuda()
            prob = torch.softmax(model(x).float(), -1)[0].cpu().numpy()
            P[i] = prob[[DFEW_ORDER.index(c) for c in LABEL7]]
    present = [c for c in LABEL7 if c in set(meta.label7)]
    pi = [LABEL7.index(c) for c in present]
    m = test & ~np.isnan(P).any(1) & meta.label7.isin(present).values
    pred = np.array(present)[P[m][:, pi].argmax(1)]
    log_result(task="zeroshot", ds=ds, feat="dfer_clip_dfew", space="label7", **metrics(meta.label7.values[m], pred))
    np.savez(f"{WORK}/{ds}/pred_dfer_clip_dfew_zs.npz", keys=meta.key.values, probs=P, classes=np.array(LABEL7))
