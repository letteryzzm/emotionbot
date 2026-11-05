#!/bin/bash
# 修好视频分辨率参数后补跑 Qwen2.5-Omni 的 video / av / avt（等 queue_omni 跑完，避免两个 7B 同时占显存）
cd ~/emo/code; source ~/emo/venv/bin/activate
until grep -q OMNI_DONE ~/emo/logs/omni.log; do sleep 20; done
for ds in ravdess cremad meld; do for m in video av; do python omni.py $ds $m --api_n 56; done; done
python omni.py meld avt --api_n 56
echo OMNI2_DONE
