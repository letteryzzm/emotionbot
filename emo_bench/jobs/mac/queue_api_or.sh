#!/bin/bash
# OpenRouter 轻量测评：每个数据集分层抽 56 条（每类 8 条，CREMA-D 每类 9 条），只看个大概。
# 不测：Gemini Pro、小米 MiMo、OpenAI、Z-AI。总花费超过 BUDGET 美元就停。
# 在 Mac 上跑：服务器是国内 IP，OpenRouter 上的 Gemini 有地区限制。Kimi K3 视频见 queue_kimi_or.sh。
cd "$(dirname "$0")/../.."; source .venv/bin/activate
export API_SUBSET=$PWD/data/api_subset RESULTS=$PWD/results/api_local.jsonl
N=56; BUDGET=9
spent() { cat results/api_cache/openrouter__*.jsonl 2>/dev/null | python -c "import sys,json;print(sum(json.loads(l).get('cost') or 0 for l in sys.stdin))"; }
run() { s=$(spent); echo "spent so far: \$$s"; python -c "import sys;sys.exit(float('$s')>$BUDGET)" || { echo BUDGET_STOP; exit 0; }
        python src/api_eval.py openrouter "$@" --n $N --workers 8; }
G=google/gemini-3.8-flash
for ds in ravdess cremad meld; do for mode in audio video av; do run $G $ds $mode; done; done
run $G meld avt
for m in minimax/minimax-m3 bytedance-seed/seed-2.0-lite; do for ds in ravdess cremad meld; do run $m $ds video; done; done
for m in $G minimax/minimax-m3 bytedance-seed/seed-2.0-lite; do run $m ter_cped text_ctx; done
run nvidia/nemotron-3-nano-omni-30b-a3b-reasoning:free meld av
echo "spent total: \$$(spent)"; echo API_OR_DONE
