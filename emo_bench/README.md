# emo_bench：FER / SER / TER 测评

2026-10-19 在 featurize 1×RTX 4090 上跑的情感识别测评（三代方法 × 三模态 + 融合 + 闭源 API）。
文字报告：`../docs/情感识别模块/06-实验报告.md`
网页报告：`report/index.html`（双击打开）

## 目录

```
emo_bench/
├── src/            所有代码（互相 import，必须放在同一目录）
├── jobs/
│   ├── server/     服务器上跑过的任务队列（历史记录，服务器布局见下）
│   └── mac/        在 Mac 上跑的 OpenRouter 测评（可直接重跑：bash jobs/mac/queue_api_or.sh）
├── data/
│   └── api_subset/ 闭源 API 用的样本子集（每个数据集 700 条：wav、无声 / 带声 mp4；CPED 只有文本）
├── results/
│   ├── results.jsonl   全部数字的原始记录（服务器写入，一行一个实验）
│   ├── api_local.jsonl Mac 上跑的闭源数字
│   ├── api_cache/      闭源每条样本的原始回答（可断点续跑）
│   ├── preds/<ds>/     本地模型逐样本预测 pred_*.npz + meta.csv
│   ├── same_subset.md  闭源 vs 本地，同一批 56 条的对比表
│   ├── server_logs/    服务器日志
│   └── logs_mac/       Mac 任务日志
├── report/         网页报告（src/build_report.py 生成，静态，约 15 MB）
│   └── dataset_preview/  数据集预览页
├── .env            API key（权限 600，不进 git）
└── .venv/          Mac 端环境（pandas / sklearn / matplotlib）
```

DFER-CLIP 权重在 `../models/dfer-clip/dferclip_dfew_fold1.pth`。

## 代码一览（src/）

| 阶段 | 文件 |
|---|---|
| 公共 | `common.py`（路径、7 类标签、数据划分、指标、写结果） |
| 数据准备 | `prep.py`（meta + 16k wav + 人脸裁剪）、`ter_data.py`（CPED）、`make_api_subset.py`、`peek_data.py` |
| 语音 SER | `ser_feats.py`（eGeMAPS / WavLM / emotion2vec / SenseVoice / audeering） |
| 人脸 FER | `fer_feats.py`（HOG / EmotiEffNet）、`dfer_clip_eval.py` |
| 文本 TER | `ter_finetune.py`（TF-IDF / RoBERTa）、`ter_llm.py`（Qwen3-8B 零样本 / QLoRA） |
| 评测 | `probe.py`（线性探针）、`zeroshot.py`、`fusion.py`、`omni.py`（Qwen2.5-Omni-7B） |
| 闭源 | `api_eval.py`（百炼 / OpenRouter / Gemini / MiniMax） |
| 推荐方案验证 | `fast_layer.py`（零样本快层 + omni 慢层，输出 results/fast_layer.md） |
| 报告 | `same_subset.py`、`make_figs.py`、`build_report.py` + `report_template.html` |

## 在 Mac 上重新生成报告

```bash
cd emo_bench && source .venv/bin/activate
python src/same_subset.py > results/same_subset.md
python src/make_figs.py        # 图输出到笔记目录 情感识别模块/figs/
python src/build_report.py     # 生成 report/
```

## 服务器布局（featurize）

服务器上代码是平铺的：`~/emo/code/` = 本地 `src/`，数据和特征在 `~/emo/work/<ds>/`，模型在 `~/emo/models/`，结果写到 `~/work/emo_results/results.jsonl`。
同步代码：`rsync -a src/ featurize-emo:emo/code/`；`jobs/server/` 里的脚本按服务器布局写（`cd ~/emo/code`），要复用时一起拷过去。
