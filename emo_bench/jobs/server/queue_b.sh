#!/bin/bash
# 大模型队列：Qwen3-8B TER（CPED 先跑，不依赖音频），MELD 等 SenseVoice 转写，最后 Qwen2.5-Omni。
cd ~/emo/code; source ~/emo/venv/bin/activate; export HF_HOME=~/emo/hf
until grep -q EXIT= ~/emo/logs/dl_omni.log; do sleep 20; done
until grep -q EXIT= ~/emo/logs/ter_cped.log; do sleep 20; done
for m in zs zs_ctx lora_ctx; do python ter_llm.py cped $m; done
until [ -f ~/emo/work/meld/feat_sensevoice.npz ]; do sleep 30; done
for m in zs zs_ctx lora_ctx; do python ter_llm.py meld $m --train_n 10000; done
until grep -q QUEUE_A_DONE ~/emo/logs/queue_a.log; do sleep 30; done
for ds in ravdess cremad meld; do for m in audio video av; do python omni.py $ds $m --n 700; done; done
python omni.py meld avt --n 700
echo QUEUE_B_DONE
