"""给闭源 API 评测导出子集：和 omni.py 完全相同的分层抽样（seed 0, n=700），外加 TER 的文本子集。

python make_api_subset.py
输出 ~/emo/work/api_subset/<ds>/{subset.csv, wav/, vid_silent/, vid_av/}
  wav        16k 单声道
  vid_silent 无声 mp4（360p, 原帧率）——FER 模式
  vid_av     带声音 mp4（360p）——给能原生读视频音轨的模型（Gemini）
TER 子集：cped / meld 测试集各分层抽 1000 条，带上文（前 8 句），只要文本。
"""
import os
import subprocess
from multiprocessing import Pool

import numpy as np
import pandas as pd

from common import LABEL7, WORK, load_meta
from omni import sample
from ter_llm import contexts

FFMPEG = os.path.expanduser("~/emo/venv/bin/ffmpeg")
OUT = f"{WORK}/api_subset"


def conv(args):
    src, wav_src, d, key = args
    sil, av, wav = f"{d}/vid_silent/{key}.mp4", f"{d}/vid_av/{key}.mp4", f"{d}/wav/{key}.wav"
    vf = ["-vf", "scale=-2:360", "-c:v", "libx264", "-preset", "veryfast", "-crf", "26", "-pix_fmt", "yuv420p"]
    if not os.path.exists(sil):
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, *vf, "-an", sil], check=False)
    if not os.path.exists(av):
        subprocess.run([FFMPEG, "-y", "-loglevel", "error", "-i", src, *vf, "-c:a", "aac", "-ac", "1", "-b:a", "64k",
                        av], check=False)
    if not os.path.exists(wav):
        subprocess.run(["cp", wav_src, wav])


if __name__ == "__main__":
    jobs = []
    for ds in ["ravdess", "cremad", "meld"]:
        meta = load_meta(ds).reset_index(drop=True)
        ok = meta.label7.isin(LABEL7).values
        test = np.where(ok & ((meta.split == "test").values if "split" in meta else True))[0]
        idx = sample(meta, test, 700)
        d = f"{OUT}/{ds}"
        for sub in ["wav", "vid_silent", "vid_av"]:
            os.makedirs(f"{d}/{sub}", exist_ok=True)
        cols = ["key", "label7", "text", "speaker"]
        meta.iloc[idx][cols].to_csv(f"{d}/subset.csv", index=False)
        jobs += [(meta.video[i], f"{WORK}/{ds}/wav/{meta.key[i]}.wav", d, meta.key[i]) for i in idx]
        print(ds, len(idx), meta.label7.values[idx].tolist().count("neutral"))
    for ds in ["cped", "meld"]:
        meta = load_meta(ds).reset_index(drop=True)
        ctx = contexts(meta)
        ok = meta.label7.isin(LABEL7).values
        test = np.where(ok & (meta.split == "test").values)[0]
        idx = sample(meta, test, 1000)
        t = meta.iloc[idx][["key", "label7", "text", "speaker"]].copy()
        t["context"] = [ctx[i] for i in idx]
        os.makedirs(f"{OUT}/ter_{ds}", exist_ok=True)
        t.to_csv(f"{OUT}/ter_{ds}/subset.csv", index=False)
    with Pool(14) as p:
        p.map(conv, jobs, chunksize=8)
    print("done", len(jobs))
