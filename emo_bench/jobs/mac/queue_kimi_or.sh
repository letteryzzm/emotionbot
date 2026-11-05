#!/bin/bash
# Kimi K3 只看画面：百炼版不支持视频输入，改走 OpenRouter（Mac 上跑）
cd "$(dirname "$0")/../.."; source .venv/bin/activate
export API_SUBSET=$PWD/data/api_subset RESULTS=$PWD/results/api_local.jsonl
for ds in ravdess cremad meld; do python src/api_eval.py openrouter moonshotai/kimi-k3 $ds video --n 56 --workers 8; done
cat results/api_cache/openrouter__*.jsonl | python -c "import sys,json;print('spent total:', sum(json.loads(l).get('cost') or 0 for l in sys.stdin))"
echo KIMI_OR_DONE
