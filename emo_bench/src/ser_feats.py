"""语音侧：抽特征 / 零样本预测。

python ser_feats.py <ds> <model>
model:
  egemaps     openSMILE eGeMAPSv02 functionals（88 维，第一代基线）
  wavlm       WavLM-large 每层 mean-pool -> [N, 25, 1024]（EmoBox 对照）
  e2v_base    emotion2vec_base utterance 特征 [N, 768]
  e2v_plus    emotion2vec_plus_large utterance 特征 [N, 1024] + 9 类零样本概率
  sensevoice  SenseVoiceSmall：情感标签 + ASR 文本（文本给 TER 的 ASR 消融用）
  sensevoice_ban  同上，但禁止输出 EMO_UNKNOWN（强制 7 选 1）
  audeering   wav2vec2 MSP-dim：arousal / dominance / valence
输出: ~/emo/work/<ds>/feat_<model>.npz
"""
import os
import sys

import numpy as np
import soundfile as sf
import torch
from tqdm import tqdm

from common import MODELS, WORK, load_meta

MAX_SEC = 20  # 截断超长句（MELD 有少数很长的片段）


def load_wav(path):
    x, sr = sf.read(path, dtype="float32")
    assert sr == 16000
    if x.ndim > 1:
        x = x.mean(1)
    return x[: MAX_SEC * sr]


def run_egemaps(paths):
    import opensmile
    smile = opensmile.Smile(feature_set=opensmile.FeatureSet.eGeMAPSv02,
                            feature_level=opensmile.FeatureLevel.Functionals)
    feats = []
    for p in tqdm(paths, mininterval=30):
        try:
            feats.append(smile.process_signal(load_wav(p), 16000).values[0])
        except Exception:
            feats.append(np.zeros(88, dtype=np.float32))
    return dict(feat=np.nan_to_num(np.array(feats, dtype=np.float32)))


@torch.no_grad()
def run_wavlm(paths):
    from transformers import AutoFeatureExtractor, WavLMModel
    fe = AutoFeatureExtractor.from_pretrained(f"{MODELS}/wavlm-large")
    m = WavLMModel.from_pretrained(f"{MODELS}/wavlm-large").cuda().eval().half()
    out = []
    for p in tqdm(paths, mininterval=30):
        x = load_wav(p)
        if len(x) < 8000:
            x = np.pad(x, (0, 8000 - len(x)))
        inp = fe(x, sampling_rate=16000, return_tensors="pt").input_values.cuda().half()
        hs = m(inp, output_hidden_states=True).hidden_states  # 25 x [1,T,1024]
        out.append(torch.stack([h[0].float().mean(0) for h in hs]).cpu().numpy().astype(np.float16))
    return dict(feat=np.stack(out))


def run_e2v(paths, name):
    from funasr import AutoModel
    m = AutoModel(model=f"{MODELS}/{name}", disable_update=True, device="cuda")
    feats, probs, labels = [], [], None
    for p in tqdm(paths, mininterval=30):
        r = m.generate(load_wav(p), granularity="utterance", extract_embedding=True, disable_pbar=True)[0]  # 截断长句防 OOM
        feats.append(np.asarray(r["feats"]).reshape(-1))
        if "scores" in r:
            probs.append(np.asarray(r["scores"]))
            labels = r["labels"]
    d = dict(feat=np.stack(feats).astype(np.float32))
    if probs:
        d.update(probs=np.stack(probs).astype(np.float32), labels=np.array(labels))
    return d


def run_sensevoice(paths, ban_unk=False):
    from funasr import AutoModel
    m = AutoModel(model=f"{MODELS}/SenseVoiceSmall", disable_update=True, device="cuda")
    tags, texts, raws = [], [], []
    B = 8  # MELD 有长句，32 会 OOM；输入先截断到 MAX_SEC
    for i in tqdm(range(0, len(paths), B), mininterval=30):
        res = m.generate(input=[load_wav(p) for p in paths[i:i + B]], language="auto", use_itn=True, batch_size=B,
                         disable_pbar=True, ban_emo_unk=ban_unk)
        for r in res:
            t = r["text"]  # 形如 <|en|><|NEUTRAL|><|Speech|><|withitn|>text
            parts = t.split("|>")
            tag = [x.replace("<|", "") for x in parts[:4]]
            raws.append(t)
            tags.append(tag[1] if len(tag) > 1 else "")
            texts.append(parts[-1].strip() if len(parts) > 1 else t)
    return dict(tag=np.array(tags), text=np.array(texts), raw=np.array(raws))


@torch.no_grad()
def run_audeering(paths):
    import torch.nn as nn
    from transformers import Wav2Vec2Processor
    from transformers.models.wav2vec2.modeling_wav2vec2 import Wav2Vec2Model, Wav2Vec2PreTrainedModel

    class RegressionHead(nn.Module):
        def __init__(self, config):
            super().__init__()
            self.dense = nn.Linear(config.hidden_size, config.hidden_size)
            self.dropout = nn.Dropout(config.final_dropout)
            self.out_proj = nn.Linear(config.hidden_size, config.num_labels)

        def forward(self, x):
            return self.out_proj(self.dropout(torch.tanh(self.dense(self.dropout(x)))))

    class EmotionModel(Wav2Vec2PreTrainedModel):  # 照抄 model card
        def __init__(self, config):
            super().__init__(config)
            self.config = config
            self.wav2vec2 = Wav2Vec2Model(config)
            self.classifier = RegressionHead(config)
            self.init_weights()

        def forward(self, input_values):
            hidden = self.wav2vec2(input_values)[0].mean(dim=1)
            return hidden, self.classifier(hidden)

    path = f"{MODELS}/wav2vec2-large-robust-12-ft-emotion-msp-dim"
    proc = Wav2Vec2Processor.from_pretrained(path)
    m = EmotionModel.from_pretrained(path).cuda().eval()
    out, feats = [], []
    for p in tqdm(paths, mininterval=30):
        x = proc(load_wav(p), sampling_rate=16000).input_values[0]
        h, y = m(torch.from_numpy(x)[None].cuda())
        out.append(y[0].cpu().numpy())
        feats.append(h[0].cpu().numpy())
    return dict(adv=np.stack(out), feat=np.stack(feats).astype(np.float32))  # 列顺序: arousal, dominance, valence


if __name__ == "__main__":
    ds, model = sys.argv[1], sys.argv[2]
    meta = load_meta(ds)
    paths = [f"{WORK}/{ds}/wav/{k}.wav" for k in meta.key]
    fn = {"egemaps": run_egemaps, "wavlm": run_wavlm, "e2v_base": lambda p: run_e2v(p, "emotion2vec_base"),
          "e2v_plus": lambda p: run_e2v(p, "emotion2vec_plus_large"), "sensevoice": run_sensevoice,
          "sensevoice_ban": lambda p: run_sensevoice(p, ban_unk=True),
          "audeering": run_audeering}[model]
    d = fn(paths)
    np.savez(f"{WORK}/{ds}/feat_{model}.npz", keys=meta.key.values, **d)
    print("saved", {k: getattr(v, "shape", None) for k, v in d.items()})
