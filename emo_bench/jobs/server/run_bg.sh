#!/bin/bash
# 用法: run_bg.sh <name> <cmd...>   后台运行并写日志到 ~/emo/logs/<name>.log
name=$1; shift
cd ~/emo/code
setsid nohup bash -c "source ~/emo/venv/bin/activate; export HF_HOME=~/emo/hf; $*; echo EXIT=\$?" > ~/emo/logs/$name.log 2>&1 < /dev/null &
echo started $name
