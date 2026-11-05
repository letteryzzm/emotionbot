"""测评报告的 3 张图（输出到笔记目录 情感识别模块/figs/）。

python src/make_figs.py
图 1  三代方法 × 三个数据集（完整测试集 UA）
图 2  MELD：同一批 56 条上各模型 audio / video / av / avt 四种输入
图 3  MELD 文本：标注文本 vs ASR 转写（完整测试集 macro-F1）
"""
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "../../docs/情感识别模块/figs")
os.makedirs(OUT, exist_ok=True)
plt.rcParams.update({"font.size": 10, "axes.spines.top": False, "axes.spines.right": False})

# ---------- 图 1：三代方法（数字来自 results/results.jsonl，完整测试集） ----------
ds = ["RAVDESS", "CREMA-D", "MELD"]
groups = {
    "SER gen1: eGeMAPS+linear": [53.1, 53.3, 23.0],
    "SER gen2: WavLM probe": [79.8, 80.6, 35.5],
    "FER gen1: HOG+linear": [53.5, 74.5, 14.7],
    "FER gen2: EmotiEffNet probe": [64.7, 84.0, 21.5],
    "Fusion A+V (avg)": [85.0, 91.1, np.nan],
}
colors = ["#9ecae1", "#3182bd", "#fdae6b", "#e6550d", "#31a354"]
x = np.arange(len(ds))
w = 0.16
fig, ax = plt.subplots(figsize=(8, 4))
for i, (k, v) in enumerate(groups.items()):
    ax.bar(x + (i - 2) * w, v, w, label=k, color=colors[i])
ax.axhline(100 / 7, ls="--", c="gray", lw=1)
ax.text(2.45, 100 / 7 + 1, "chance (7 cls)", color="gray", fontsize=8, ha="right")
ax.set_xticks(x, ds)
ax.set_ylabel("UA (%)")
ax.set_ylim(0, 100)
ax.legend(fontsize=8, ncol=2, loc="upper right")
ax.set_title("Fig 1. Handcrafted vs SSL features, full test sets")
fig.tight_layout()
fig.savefig(f"{OUT}/fig1_generations.png", dpi=150)

# ---------- 图 2：MELD 同一批 56 条，四种输入 ----------
models = ["qwen3.8-omni-flash", "qwen3-omni-flash", "Gemini 3.8 Flash", "Qwen2.5-Omni-7B (local)"]
modes = ["audio", "video", "av", "avt"]
vals = np.array([
    [44.6, 23.5, 44.4, 55.1],
    [53.6, 18.7, 41.8, 46.8],
    [48.2, 25.0, 37.5, 48.7],
    [32.1, 23.2, 32.1, 44.6],
])
mc = ["#6baed6", "#fd8d3c", "#74c476", "#9e9ac8"]
x = np.arange(len(models))
w = 0.2
fig, ax = plt.subplots(figsize=(8, 4))
for j, m in enumerate(modes):
    ax.bar(x + (j - 1.5) * w, vals[:, j], w, label=m, color=mc[j])
ax.axhline(100 / 7, ls="--", c="gray", lw=1)
ax.set_xticks(x, models, fontsize=9)
ax.set_ylabel("UA (%) on 56 balanced MELD clips")
ax.set_ylim(0, 70)
ax.legend(title="input", fontsize=8)
ax.set_title("Fig 2. MELD: adding video often hurts (n=56, ±~13 pt 95% CI)")
fig.tight_layout()
fig.savefig(f"{OUT}/fig2_meld_modes.png", dpi=150)

# ---------- 图 3：标注文本 vs ASR 文本 ----------
meths = ["TF-IDF", "RoBERTa", "RoBERTa+ctx", "Qwen3-8B zs", "Qwen3-8B zs+ctx", "Qwen3-8B LoRA+ctx"]
gold = [32.7, 45.8, 45.6, 45.3, 43.7, 54.0]
asr = [np.nan, 32.3, 31.6, 32.6, 34.2, 36.3]
x = np.arange(len(meths))
fig, ax = plt.subplots(figsize=(8, 3.8))
ax.bar(x - 0.2, gold, 0.4, label="gold transcript", color="#3182bd")
ax.bar(x + 0.2, asr, 0.4, label="SenseVoice ASR", color="#fdae6b")
for i in range(len(meths)):
    if not np.isnan(asr[i]):
        ax.text(x[i] + 0.2, asr[i] + 1, f"-{gold[i] - asr[i]:.0f}", ha="center", fontsize=8, color="#a63603")
ax.set_xticks(x, meths, rotation=15, fontsize=9)
ax.set_ylabel("macro-F1 (%)")
ax.set_ylim(0, 65)
ax.legend(fontsize=8)
ax.set_title("Fig 3. MELD text emotion: the ASR gap (full test set, n=2610)")
fig.tight_layout()
fig.savefig(f"{OUT}/fig3_asr_gap.png", dpi=150)
print("saved to", OUT)
