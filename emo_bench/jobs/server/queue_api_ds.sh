#!/bin/bash
# 百炼（DashScope）轻量测评：每个数据集分层抽 56 条（和 OpenRouter 同一批样本）
cd ~/emo/code; source ~/emo/venv/bin/activate
N="--n 56 --workers 6"
for m in qwen3-omni-flash qwen3.8-omni-flash; do
  for ds in ravdess cremad meld; do for mode in audio video av; do python api_eval.py dashscope $m $ds $mode $N; done; done
  python api_eval.py dashscope $m meld avt $N
done
for ds in ravdess cremad meld; do python api_eval.py dashscope kimi-k3 $ds video $N; done
for m in qwen3.8-omni-flash kimi-k3 qwen3.5-plus; do python api_eval.py dashscope $m ter_cped text_ctx $N; done
echo API_DS_DONE
