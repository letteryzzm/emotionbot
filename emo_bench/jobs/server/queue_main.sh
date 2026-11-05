#!/bin/bash
# 单一 GPU 队列（顺序执行，避免显存冲突）。已存在的特征文件跳过。
cd ~/emo/code; source ~/emo/venv/bin/activate; export HF_HOME=~/emo/hf OMP_NUM_THREADS=8
have() { [ -f ~/emo/work/$1/feat_$2.npz ]; }
# 等当前正在跑的 Qwen3 CPED 打分结束
while pgrep -f "ter_llm.py cped" > /dev/null; do sleep 20; done
until grep -q EXIT= ~/emo/logs/prep_ravdess.log 2>/dev/null || [ -f ~/emo/work/ravdess/meta.csv ]; do sleep 20; done
for ds in cremad meld ravdess; do
  for m in sensevoice e2v_plus e2v_base audeering wavlm egemaps; do have $ds $m || python ser_feats.py $ds $m; done
  for m in enet_b0_8_va_mtl enet_b2_8 hog; do have $ds $m || python fer_feats.py $ds $m; done
done
for ds in ravdess cremad meld; do
  python zeroshot.py $ds
  for f in egemaps wavlm e2v_base e2v_plus audeering hog enet_b0_8_va_mtl enet_b2_8; do
    python probe.py $ds $f --space native; python probe.py $ds $f --space label7
  done
  python dfer_clip_eval.py $ds
done
for m in tfidf jhartmann roberta roberta_ctx; do python ter_finetune.py meld $m; done
echo SMALL_DONE
for m in zs zs_ctx lora_ctx; do python ter_llm.py meld $m --train_n 10000; done
python ter_llm.py cped lora_ctx
for ds in ravdess cremad meld; do for m in audio video av; do python omni.py $ds $m --n 700; done; done
python omni.py meld avt --n 700
echo QUEUE_MAIN_DONE
