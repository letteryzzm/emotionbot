"""数据预处理：统一 meta.csv + 16k 单声道 wav + 人脸裁剪 npy。

用法: python prep.py ravdess|cremad|meld
输出: ~/emo/work/<ds>/meta.csv, wav/<key>.wav, face/<key>.npy (uint8 [T,224,224,3])
"""
import glob
import io
import json
import os
import subprocess
import sys
from multiprocessing import Pool

import cv2
import numpy as np
import pandas as pd

HOME = os.path.expanduser("~/emo")
DATA = f"{HOME}/data"
FFMPEG = f"{HOME}/venv/bin/ffmpeg"
YUNET = f"{HOME}/models/yunet/yunet.onnx"
N_FRAMES = 16
FACE = 224

# 统一 7 类；其余映射为 other
LABEL7 = ["neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"]


def emobox_split(ds):
    """读 EmoBox 的划分，返回 {key: [(fold, split), ...]}"""
    out = {}
    for fn in glob.glob(f"{DATA}/emobox/data/{ds}/fold_*/*.jsonl"):
        fold = int(fn.split("fold_")[1].split("/")[0])
        split = "test" if "_test_" in fn else ("valid" if "_valid_" in fn else "train")
        for line in open(fn):
            d = json.loads(line)
            out.setdefault(d["key"], []).append((fold, split))
    return out


# ---------------- 人脸 ----------------
_det = None


def detector():
    global _det
    if _det is None:
        cv2.setNumThreads(1)
        _det = cv2.FaceDetectorYN.create(YUNET, "", (320, 320), 0.6, 0.3, 50)
    return _det


def crop_largest_face(frame):
    h, w = frame.shape[:2]
    scale = 640 / max(h, w) if max(h, w) > 640 else 1.0
    small = cv2.resize(frame, (int(w * scale), int(h * scale))) if scale != 1.0 else frame
    det = detector()
    det.setInputSize((small.shape[1], small.shape[0]))
    _, faces = det.detect(small)
    if faces is None or len(faces) == 0:
        return None, 0.0
    f = max(faces, key=lambda r: r[2] * r[3])
    x, y, bw, bh = (f[:4] / scale).tolist()
    cx, cy, s = x + bw / 2, y + bh / 2, max(bw, bh)
    x0, y0 = int(max(cx - s / 2, 0)), int(max(cy - s / 2, 0))
    x1, y1 = int(min(cx + s / 2, w)), int(min(cy + s / 2, h))
    crop = frame[y0:y1, x0:x1]
    if crop.size == 0:
        return None, 0.0
    return cv2.resize(cv2.cvtColor(crop, cv2.COLOR_BGR2RGB), (FACE, FACE)), float(f[-1])


def faces_from_video(path):
    cap = cv2.VideoCapture(path)
    frames = []
    while True:
        ok, fr = cap.read()
        if not ok:
            break
        frames.append(fr)
    cap.release()
    if not frames:
        return None, 0, 0
    idx = np.linspace(0, len(frames) - 1, min(N_FRAMES, len(frames))).round().astype(int)
    crops, confs = [], []
    for i in idx:
        c, s = crop_largest_face(frames[i])
        if c is not None:
            crops.append(c)
            confs.append(s)
    if not crops:
        return None, len(frames), 0
    return np.stack(crops), len(frames), float(np.mean(confs))


def extract_wav(src, dst):
    subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, "-ac", "1", "-ar", "16000", "-vn", dst], check=True)


def process(item):
    key, video, out = item
    wav, face = f"{out}/wav/{key}.wav", f"{out}/face/{key}.npy"
    res = {"key": key, "n_face": 0, "face_conf": 0.0}
    try:
        if not os.path.exists(wav):
            extract_wav(video, wav)
        if not os.path.exists(face):
            crops, nf, conf = faces_from_video(video)
            if crops is not None:
                np.save(face, crops)
                res.update(n_face=len(crops), face_conf=conf)
        else:
            res["n_face"] = len(np.load(face, mmap_mode="r"))
    except Exception as e:  # 坏视频直接记录
        res["err"] = str(e)[:200]
    return res


# ---------------- 各数据集 ----------------
def meta_ravdess():
    import pyarrow.parquet as pq
    names = ["angry", "calm", "disgust", "fearful", "happy", "neutral", "sad", "surprised"]
    to7 = {"angry": "angry", "calm": "other", "disgust": "disgust", "fearful": "fear", "happy": "happy",
           "neutral": "neutral", "sad": "sad", "surprised": "surprise"}
    split = emobox_split("ravdess")
    vdir = f"{DATA}/ravdess_av/video"
    os.makedirs(vdir, exist_ok=True)
    rows = []
    for f in sorted(glob.glob(f"{DATA}/ravdess_av/data/*.parquet")):
        pf = pq.ParquetFile(f)
        for rg in range(pf.num_row_groups):
            for r in pf.read_row_group(rg, columns=["video_id", "video", "emotion", "transcription"]).to_pylist():
                vid = r["video_id"].replace(".mp4", "")
                parts = vid.split("-")
                vpath = f"{vdir}/{vid}.mp4"
                if not os.path.exists(vpath):
                    open(vpath, "wb").write(r["video"]["bytes"])
                ekey = "ravdess-03-" + "-".join(parts[1:])  # EmoBox 用音频文件名（modality=03）
                native = names[r["emotion"]]
                rows.append(dict(key=vid, video=vpath, speaker=int(parts[6]), native=native, label7=to7[native],
                                 intensity=int(parts[3]), text=r["transcription"],
                                 test_fold=[fo for fo, s in split.get(ekey, []) if s == "test"][0]))
    return pd.DataFrame(rows)


def meta_cremad():
    to7 = {"ANG": "angry", "DIS": "disgust", "FEA": "fear", "HAP": "happy", "NEU": "neutral", "SAD": "sad"}
    texts = {"IEO": "It's eleven o'clock", "TIE": "That is exactly what happened", "IOM": "I'm on my way to the meeting",
             "IWW": "I wonder what this is about", "TAI": "The airplane is almost full", "MTI": "Maybe tomorrow it will be cold",
             "IWL": "I would like a new alarm clock", "ITH": "I think I have a doctor's appointment",
             "DFA": "Don't forget a jacket", "ITS": "I think I've seen this before",
             "TSI": "The surface is slick", "WSI": "We'll stop in a couple of minutes"}
    split = emobox_split("cremad")
    vids = {os.path.basename(p)[:-4]: p for p in glob.glob(f"{DATA}/cremad/CREMA-D/**/*.flv", recursive=True)}
    rows = []
    for k, sp in split.items():
        stem = k.replace("cremad-", "").replace("-", "_")
        if stem not in vids:
            continue
        spk, sent, emo, _ = stem.split("_")
        rows.append(dict(key=stem, video=vids[stem], speaker=int(spk), native=emo, label7=to7[emo],
                         text=texts[sent], split=sp[0][1]))
    return pd.DataFrame(rows)


def meta_meld():
    to7 = {"neutral": "neutral", "joy": "happy", "sadness": "sad", "anger": "angry", "surprise": "surprise",
           "fear": "fear", "disgust": "disgust"}
    root = f"{DATA}/meld/MELD.Raw"
    cfg = {"train": ("train_sent_emo.csv", "train_splits"),
           "valid": ("dev_sent_emo.csv", "dev_splits_complete"),
           "test": ("test_sent_emo.csv", "output_repeated_splits_test")}
    rows = []
    for sp, (csv, vd) in cfg.items():
        df = pd.read_csv(f"{root}/{csv}")
        for r in df.itertuples():
            name = f"dia{r.Dialogue_ID}_utt{r.Utterance_ID}"
            vpath = f"{root}/{vd}/{name}.mp4"
            if not os.path.exists(vpath):
                continue
            rows.append(dict(key=f"{sp}_{name}", video=vpath, speaker=r.Speaker, native=r.Emotion,
                             label7=to7[r.Emotion], text=str(r.Utterance).replace("\x92", "'"), split=sp,
                             dialogue=f"{sp}_{r.Dialogue_ID}", utt=int(r.Utterance_ID)))
    return pd.DataFrame(rows)


if __name__ == "__main__":
    ds = sys.argv[1]
    out = f"{HOME}/work/{ds}"
    os.makedirs(f"{out}/wav", exist_ok=True)
    os.makedirs(f"{out}/face", exist_ok=True)
    meta = {"ravdess": meta_ravdess, "cremad": meta_cremad, "meld": meta_meld}[ds]()
    print(ds, len(meta), meta.label7.value_counts().to_dict(), flush=True)
    with Pool(15) as p:
        res = []
        for i, r in enumerate(p.imap_unordered(process, [(k, v, out) for k, v in zip(meta.key, meta.video)], chunksize=4)):
            res.append(r)
            if i % 500 == 0:
                print(i, flush=True)
    meta = meta.merge(pd.DataFrame(res), on="key", how="left")
    meta.to_csv(f"{out}/meta.csv", index=False)
    print("faces missing:", (meta.n_face == 0).sum(), "errors:", meta.get("err", pd.Series()).notna().sum())
