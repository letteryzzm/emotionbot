#!/usr/bin/env bash
# 用法: ./flash.sh eyes|brows|mouth [port]
# 先给 Pico 刷 MicroPython 固件（按住 BOOTSEL 插 USB，拖 .uf2 进去），再跑这个脚本
set -euo pipefail
role=$1
port=${2:-auto}
cd "$(dirname "$0")"
mp="mpremote connect $port"
$mp fs cp servo.py :servo.py
$mp fs cp "config_${role}.py" :config.py
$mp fs cp main.py :main.py
$mp reset
echo "flashed $role"
