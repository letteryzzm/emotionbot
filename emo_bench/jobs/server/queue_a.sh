#!/bin/bash
# 小模型队列：特征 -> 探针 -> 零样本。等 MELD 预处理和 CREMA-D 语音特征完成后开始。
cd ~/emo/code; source ~/emo/venv/bin/activate; export HF_HOME=~/emo/hf OMP_NUM_THREADS=4
until grep -q EXIT= ~/emo/logs/prep_meld.log && grep -q EXIT= ~/emo/logs/ser_cremad.log; do sleep 20; done
python prep.py ravdess > ~/emo/logs/prep_ravdess.log 2>&1 &
for m in hog enet_b0_8_va_mtl enet_b2_8; do python fer_feats.py cremad $m; done
for m in sensevoice e2v_plus e2v_base audeering wavlm egemaps; do python ser_feats.py meld $m; done
for m in hog enet_b0_8_va_mtl enet_b2_8; do python fer_feats.py meld $m; done
wait
for m in sensevoice e2v_plus e2v_base audeering wavlm egemaps; do python ser_feats.py ravdess $m; done
for m in hog enet_b0_8_va_mtl enet_b2_8; do python fer_feats.py ravdess $m; done
for ds in ravdess cremad meld; do
  python zeroshot.py $ds
  for f in egemaps wavlm e2v_base e2v_plus audeering hog enet_b0_8_va_mtl enet_b2_8; do
    python probe.py $ds $f --space native; python probe.py $ds $f --space label7
  done
done
for m in tfidf jhartmann roberta roberta_ctx; do python ter_finetune.py meld $m; done
until [ -f ~/emo/models/dferclip_dfew_fold1.pth ] && [ $(stat -c %s ~/emo/models/dferclip_dfew_fold1.pth) -ge 614854176 ]; do sleep 30; done
for ds in ravdess cremad meld; do python dfer_clip_eval.py $ds; done
echo QUEUE_A_DONE
