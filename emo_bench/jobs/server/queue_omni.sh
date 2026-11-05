#!/bin/bash
# Qwen2.5-Omni-7B 本地零样本：只跑闭源 API 同一批 56 条样本（方便直接对比，GPU 时间约十几分钟）
cd ~/emo/code; source ~/emo/venv/bin/activate
for ds in ravdess cremad meld; do for m in audio video av; do python omni.py $ds $m --api_n 56; done; done
python omni.py meld avt --api_n 56
echo OMNI_DONE
