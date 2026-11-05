"""生成交互式 HTML 测评报告：report/index.html + report/media/（56 条样本视频）+ report/figs/。

python src/build_report.py
数据来源：results/preds/<ds>/pred_*.npz（本地模型）、results/api_cache/*.jsonl（闭源）、results/results.jsonl（完整测试集数字）。
整个 report/ 目录是自包含的静态网页，可以直接放到任何静态托管上。
"""
import glob
import json
import os
import shutil

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix

from api_eval import LABEL7, parse

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)  # emo_bench/
PRED = f"{ROOT}/results/preds"
OUT = f"{ROOT}/report"
FIGS = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../docs/情感识别模块/figs")
N = 56

DS = {  # api 子集名 -> (pred 目录, 标题, 说明)
    "ravdess": ("ravdess", "RAVDESS", "24 名专业演员，英文，两句固定台词，绿幕正脸。情绪夸张、画面干净——表演数据的「上限」场景。"),
    "cremad": ("cremad", "CREMA-D", "91 名演员，英文，12 句固定台词，480p，没有 surprise。情绪比 RAVDESS 弱，众包标注者也常认错。"),
    "meld": ("meld", "MELD", "美剧《老友记》真实对话：镜头切换、多人同框、背景笑声，最接近机器人会遇到的对话场景。"),
    "ter_cped": ("cped", "CPED（中文文本）", "40 部国产电视剧的对话，只有文字。很多情绪要靠语气和画面才看得出，纯文本天然吃亏。"),
}

# 本地方法：(id, 显示名, 模态, 代, pred 文件列表；多于一个表示 log 概率平均融合)
AV = ["wavlm_label7", "enet_b0_8_va_mtl_label7"]
LOCAL_AV = [
    ("egemaps", "eGeMAPS + 线性", "语音", "第1代 手工特征", ["egemaps_label7"]),
    ("wavlm", "WavLM-large 探针", "语音", "第2代 自监督", ["wavlm_label7"]),
    ("e2v", "emotion2vec+ 零样本 ⚠污染", "语音", "第2代 自监督", ["e2v_plus_zs"]),
    ("sv", "SenseVoice 零样本", "语音", "第3代 大模型", ["sensevoice_ban_zs"]),
    ("hog", "HOG + 线性", "人脸", "第1代 手工特征", ["hog_label7"]),
    ("enet", "EmotiEffNet-B0 探针", "人脸", "第2代 专用模型", ["enet_b0_8_va_mtl_label7"]),
    ("enet_zs", "EmotiEffNet-B0 零样本", "人脸", "第2代 专用模型", ["enet_b0_8_va_mtl_zs"]),
    ("dfer", "DFER-CLIP 零样本", "人脸", "第2代 专用模型", ["dfer_clip_dfew_zs"]),
    ("fuse_av", "融合：WavLM + EmotiEffNet", "融合", "融合", AV),
    ("omni_a", "Qwen2.5-Omni-7B 音频", "语音", "第3代 本地全模态", ["omni_audio_api"]),
    ("omni_v", "Qwen2.5-Omni-7B 视频", "人脸", "第3代 本地全模态", ["omni_video_api"]),
    ("omni_av", "Qwen2.5-Omni-7B 音视频", "音视频", "第3代 本地全模态", ["omni_av_api"]),
]
LOCAL = {
    "ravdess": LOCAL_AV, "cremad": LOCAL_AV,
    "meld": LOCAL_AV + [
        ("tfidf", "TF-IDF + LR", "文本", "第1代 手工特征", ["ter_tfidf_gold"]),
        ("roberta", "RoBERTa 微调", "文本", "第2代 预训练微调", ["ter_roberta_gold"]),
        ("qzs", "Qwen3-8B 零样本", "文本", "第3代 大模型", ["ter_qwen3_8b_zs_gold"]),
        ("qzsc", "Qwen3-8B 零样本 + 上文", "文本", "第3代 大模型", ["ter_qwen3_8b_zs_ctx_gold"]),
        ("lora", "Qwen3-8B LoRA + 上文", "文本", "第3代 大模型", ["ter_qwen3_8b_lora_ctx_gold"]),
        ("lora_asr", "Qwen3-8B LoRA + 上文（ASR 文本）", "文本", "第3代 大模型", ["ter_qwen3_8b_lora_ctx_asr"]),
        ("fuse_avt", "融合：WavLM + EmotiEffNet + LoRA", "融合", "融合", AV + ["ter_qwen3_8b_lora_ctx_gold"]),
        ("fuse_avt_asr", "融合（ASR 文本）", "融合", "融合", AV + ["ter_qwen3_8b_lora_ctx_asr"]),
        ("omni_avt", "Qwen2.5-Omni-7B 音视频 + 字幕", "音视频+文本", "第3代 本地全模态", ["omni_avt_api"]),
    ],
    "cped": [
        ("tfidf", "TF-IDF + LR", "文本", "第1代 手工特征", ["ter_tfidf_gold"]),
        ("roberta", "中文 RoBERTa 微调", "文本", "第2代 预训练微调", ["ter_roberta_gold"]),
        ("roberta_ctx", "中文 RoBERTa 微调 + 上文", "文本", "第2代 预训练微调", ["ter_roberta_ctx_gold"]),
        ("qzs", "Qwen3-8B 零样本", "文本", "第3代 大模型", ["ter_qwen3_8b_zs_gold"]),
        ("qzsc", "Qwen3-8B 零样本 + 上文", "文本", "第3代 大模型", ["ter_qwen3_8b_zs_ctx_gold"]),
        ("lora", "Qwen3-8B LoRA + 上文", "文本", "第3代 大模型", ["ter_qwen3_8b_lora_ctx_gold"]),
    ],
}
API_NAME = {"google_gemini-3.8-flash": "Gemini 3.8 Flash", "qwen3.8-omni-flash": "qwen3.8-omni-flash",
            "qwen3-omni-flash": "qwen3-omni-flash", "minimax_minimax-m3": "MiniMax M3",
            "moonshotai_kimi-k3": "Kimi K3", "kimi-k3": "Kimi K3", "bytedance-seed_seed-2.0-lite": "Seed 2.0 Lite",
            "qwen3.5-plus": "qwen3.5-plus",
            "nvidia_nemotron-3-nano-omni-30b-a3b-reasoning:free": "Nemotron 3 Nano Omni（免费）"}
MODE = {"audio": ("音频", "语音"), "video": ("无声视频", "人脸"), "av": ("音视频", "音视频"),
        "avt": ("音视频 + 字幕", "音视频+文本"), "text_ctx": ("文本 + 上文", "文本")}


def subset(api_ds):
    sub = pd.read_csv(f"{ROOT}/data/api_subset/{api_ds}/subset.csv")
    return sub.groupby("label7").head(max(1, N // sub.label7.nunique())).reset_index(drop=True)


def load_probs(ds, f, labels):
    d = np.load(f"{PRED}/{ds}/pred_{f}.npz", allow_pickle=True)
    cls = list(d["classes"])
    return d["keys"], d["probs"][:, [cls.index(c) for c in labels]].astype(np.float64)


def method_probs(ds, files, labels):
    if len(files) == 1:
        return load_probs(ds, files[0], labels)
    keys, P0 = load_probs(ds, files[0], labels)
    Ps = [np.log(np.clip(P0, 1e-6, 1))] + [np.log(np.clip(load_probs(ds, f, labels)[1], 1e-6, 1)) for f in files[1:]]
    L = np.mean(Ps, 0)
    E = np.exp(L - np.nanmax(L, 1, keepdims=True))
    return keys, E / E.sum(1, keepdims=True)


def summarize(y, pred, labels):
    """UA / macro-F1 / 每类召回 / 混淆矩阵；pred 里 None 表示无答案，'invalid' 表示答非所问"""
    ok = [p is not None for p in pred]
    yy = np.array(y)[ok]
    pp = np.array([p for p in pred if p is not None])
    rec = {}
    for c in labels:
        m = yy == c
        rec[c] = float((pp[m] == c).mean()) if m.any() else None
    ua = 100 * np.mean([v for v in rec.values() if v is not None])
    f1s = []
    for c in labels:
        tp = ((pp == c) & (yy == c)).sum()
        prec = tp / max((pp == c).sum(), 1)
        r = tp / max((yy == c).sum(), 1)
        f1s.append(0 if tp == 0 else 2 * prec * r / (prec + r))
    cm = confusion_matrix(yy, pp, labels=labels + ["invalid"])[:len(labels)].tolist()
    return dict(UA=round(ua, 1), F1=round(100 * float(np.mean(f1s)), 1), correct=int((yy == pp).sum()),
                n=int(len(yy)), recall=rec, cm=cm)


def build_ds(api_ds):
    ds, title, desc = DS[api_ds]
    sub = subset(api_ds)
    labels = [c for c in LABEL7 if c in set(sub.label7)]
    meta = pd.read_csv(f"{PRED}/{ds}/meta.csv")
    pos = {k: i for i, k in enumerate(meta.key)}
    y = sub.label7.tolist()
    samples = []
    for r in sub.itertuples():
        s = dict(key=r.key, label=r.label7, text=str(r.text) if isinstance(r.text, str) else "",
                 speaker=str(r.speaker))
        if api_ds == "ter_cped":
            s["context"] = [c for c in str(r.context).split("\n") if c and c != "nan"][-6:]
        else:
            s["video"] = f"media/{api_ds}/{r.key}.mp4"
            if api_ds == "meld":  # 上文：同一段对话的前 3 句
                m = meta.iloc[pos[r.key]]
                prev = meta[(meta.split == m.split) & (meta.dialogue == m.dialogue) & (meta.utt < m.utt)]
                s["context"] = [f"{a.speaker}: {a.text}" for a in prev.sort_values("utt").tail(3).itertuples()]
        samples.append(s)

    methods = []
    for mid, name, mod, fam, files in LOCAL.get(ds, []):
        if not all(os.path.exists(f"{PRED}/{ds}/pred_{f}.npz") for f in files):
            continue
        keys, P = method_probs(ds, files, labels)
        kp = {k: i for i, k in enumerate(keys)}
        preds, confs = [], []
        for k in sub.key:
            p = P[kp[k]]
            if np.isnan(p).any():
                preds.append(None)
                confs.append(None)
            else:
                preds.append(labels[int(p.argmax())])
                confs.append(round(float(p.max()), 2))
        methods.append(dict(id=mid, name=name, source="本地", modality=mod, family=fam, preds=preds, conf=confs,
                            **summarize(y, preds, labels)))
    for cf in sorted(glob.glob(f"{ROOT}/results/api_cache/*__{api_ds}__*.jsonl")):
        prov, model, _, mode = os.path.basename(cf)[:-6].split("__")
        if prov == "dashscope" and model == "kimi-k3" and mode == "video":
            continue  # 百炼版 Kimi 不支持视频，全部失败
        ans = {}
        for line in open(cf):
            r = json.loads(line)
            if "answer" in r:
                ans[r["key"]] = r["answer"]
        if sum(k in ans for k in sub.key) < 0.8 * len(sub):
            continue
        preds = [parse(ans[k]) if k in ans else None for k in sub.key]
        raw = [ans.get(k, "")[:80] for k in sub.key]
        mlabel, mod = MODE[mode]
        methods.append(dict(id=f"{prov}:{model}:{mode}", name=f"{API_NAME.get(model, model)} · {mlabel}",
                            source="闭源 API" if "nemotron" not in model else "开放权重 API",
                            provider="OpenRouter" if prov == "openrouter" else "阿里百炼",
                            modality=mod, family="闭源全模态" if mode != "text_ctx" else "闭源大模型",
                            preds=preds, raw=raw, **summarize(y, preds, labels)))
    return dict(id=api_ds, title=title, desc=desc, labels=labels, samples=samples, methods=methods)


def full_results():
    """完整测试集上的本地结果：每个配置取最新一条"""
    seen = {}
    for line in open(f"{ROOT}/results/results.jsonl"):
        d = json.loads(line)
        if d.get("task") not in ("probe", "zeroshot", "ter") or d.get("space") != "label7":
            continue
        seen[(d["task"], d["ds"], d["feat"], d.get("text", ""))] = d
    rows = [dict(task=k[0], ds=k[1], feat=k[2], text=k[3], UA=round(d["UA"], 1), WA=round(d["WA"], 1),
                 F1=round(d["macroF1"], 1), n=d.get("n")) for k, d in seen.items()]
    # 融合：用 pred 文件在完整测试集上重算（log 概率平均，和 fusion.py 的 avg 一致）
    for ds, combos in {"ravdess": {"融合 A+V": AV}, "cremad": {"融合 A+V": AV},
                       "meld": {"融合 A+V+T（标注文本）": AV + ["ter_qwen3_8b_lora_ctx_gold"],
                                "融合 A+V+T（ASR 文本）": AV + ["ter_qwen3_8b_lora_ctx_asr"]}}.items():
        meta = pd.read_csv(f"{PRED}/{ds}/meta.csv")
        labels = [c for c in LABEL7 if c in set(meta.label7)]
        test = np.ones(len(meta), bool) if ds == "ravdess" else (meta.split == "test").values
        for name, files in combos.items():
            _, P = method_probs(ds, files, labels)
            m = test & meta.label7.isin(labels).values & ~np.isnan(P).any(1)
            pred = [labels[i] for i in P[m].argmax(1)]
            s = summarize(meta.label7.values[m].tolist(), pred, labels)
            acc = 100 * s["correct"] / s["n"]
            rows.append(dict(task="fusion", ds=ds, feat=name, text="", UA=s["UA"], WA=round(acc, 1), F1=s["F1"],
                             n=s["n"]))
    return rows


def full_confusions():
    """完整测试集混淆矩阵（只做几个代表性方法，用来说明「不平衡数据上的分数」）"""
    out = {}
    for ds, f, name in [("meld", "ter_qwen3_8b_lora_ctx_gold", "MELD · Qwen3-8B LoRA + 上文（完整测试集 2,610 句）"),
                        ("meld", "enet_b0_8_va_mtl_label7", "MELD · EmotiEffNet-B0 探针（完整测试集）"),
                        ("ravdess", "wavlm_label7", "RAVDESS · WavLM 探针（全部 1,248 条，交叉验证）"),
                        ("cped", "ter_qwen3_8b_lora_ctx_gold", "CPED · Qwen3-8B LoRA + 上文（完整测试集）")]:
        meta = pd.read_csv(f"{PRED}/{ds}/meta.csv")
        labels = [c for c in LABEL7 if c in set(meta.label7)]
        _, P = load_probs(ds, f, labels)
        test = np.ones(len(meta), bool) if ds == "ravdess" else (meta.split == "test").values
        m = test & meta.label7.isin(labels).values & ~np.isnan(P).any(1)
        pred = [labels[i] for i in P[m].argmax(1)]
        s = summarize(meta.label7.values[m].tolist(), pred, labels)
        s["labels"] = labels
        s["support"] = [int((meta.label7.values[m] == c).sum()) for c in labels]
        out[f"{ds}:{f}"] = dict(name=name, **s)
    return out


def main():
    os.makedirs(f"{OUT}/figs", exist_ok=True)
    data = dict(datasets=[build_ds(d) for d in DS], full=full_results(), fullcm=full_confusions())
    for d in data["datasets"]:
        if d["id"] == "ter_cped":
            continue
        os.makedirs(f"{OUT}/media/{d['id']}", exist_ok=True)
        for s in d["samples"]:
            dst = f"{OUT}/{s['video']}"
            if not os.path.exists(dst):
                shutil.copy(f"{ROOT}/data/api_subset/{d['id']}/vid_av/{s['key']}.mp4", dst)
    for f in glob.glob(f"{FIGS}/*.png"):
        shutil.copy(f, f"{OUT}/figs/")
    tpl = open(f"{HERE}/report_template.html").read()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, separators=(",", ":")))
    open(f"{OUT}/index.html", "w").write(html)
    print("methods per ds:", {d["id"]: len(d["methods"]) for d in data["datasets"]})


if __name__ == "__main__":
    main()
