#!/usr/bin/env bash
# 一键准备 EmotionBot 的 Python 3.11 环境（Linux / macOS）。演示机是 Ubuntu + 4060 Laptop 用这个。
#
#   bash scripts/setup_env.sh
#   bash scripts/setup_env.sh --with-models
#   bash scripts/setup_env.sh --torch cu121 --mirror https://pypi.tuna.tsinghua.edu.cn/simple
#
# 可重复执行：已有 .venv 会复用，pip 安装本身幂等。
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

PY="${PYTHON:-python3.11}"
TORCH_CUDA="${TORCH_CUDA:-cu124}"        # 4060 用 cu124；旧驱动可改 cu121 / cpu
PIP_MIRROR="${PIP_MIRROR:-}"             # 空 = 官方 PyPI；国内可给清华源
MODEL_DIR="${EMOBOT_MODEL_DIR:-$HOME/emo_models}"
WITH_MODELS=0

while [[ $# -gt 0 ]]; do
    case "$1" in
        --torch) TORCH_CUDA="$2"; shift 2 ;;
        --mirror) PIP_MIRROR="$2"; shift 2 ;;
        --model-dir) MODEL_DIR="$2"; shift 2 ;;
        --python) PY="$2"; shift 2 ;;
        --with-models) WITH_MODELS=1; shift ;;
        -h|--help) sed -n '2,10p' "$0"; exit 0 ;;
        *) echo "未知参数: $1"; exit 1 ;;
    esac
done

echo "== EmotionBot 环境准备（Linux/macOS）=="
echo "项目目录: $ROOT"

if ! command -v "$PY" >/dev/null 2>&1; then
    echo "找不到 $PY。请先安装 Python 3.11：" >&2
    echo "  sudo apt install python3.11 python3.11-venv   # Ubuntu 22.04 需先加 deadsnakes PPA" >&2
    echo "  或把 PYTHON=/path/to/python3.11 传进来" >&2
    exit 1
fi
VER="$("$PY" -c 'import sys;print("%d.%d"%sys.version_info[:2])')"
if [[ "$VER" != "3.11" && "$VER" != "3.12" ]]; then
    echo "当前 Python $VER 不符合要求（需要 3.11/3.12）" >&2
    exit 1
fi
echo "Python $VER OK"

if [[ ! -x .venv/bin/python ]]; then
    echo "创建 .venv ..."
    "$PY" -m venv .venv || {
        echo "venv 创建失败。Ubuntu 上通常缺 python3.11-venv：" >&2
        echo "  sudo apt install python3.11-venv" >&2
        exit 1
    }
else
    echo ".venv 已存在，复用"
fi
PYV="$ROOT/.venv/bin/python"

PIP_ARGS=()
[[ -n "$PIP_MIRROR" ]] && PIP_ARGS=(-i "$PIP_MIRROR")

echo "升级 pip ..."
"$PYV" -m pip install --upgrade pip "${PIP_ARGS[@]}"

echo "安装 torch ($TORCH_CUDA) ..."
"$PYV" -m pip install torch torchvision torchaudio \
    --index-url "https://download.pytorch.org/whl/$TORCH_CUDA" || {
    echo "torch 安装失败。可先装 CPU 版继续开发：" >&2
    echo "  $PYV -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu" >&2
    exit 1
}

echo "安装项目依赖 ..."
"$PYV" -m pip install -e ".[dev,audio,vision]" "${PIP_ARGS[@]}"

echo "安装实时推理依赖（funasr / transformers / TTS）..."
# emotion2vec 不是 PyPI 包（走 funasr + ModelScope），别把它写进同一条命令
"$PYV" -m pip install funasr "${PIP_ARGS[@]}"
# 必须锁 4.x：transformers 5.x 要求 torch>=2.6，2.5/2.6 的组合会被判定为不可用
"$PYV" -m pip install "transformers==4.57.6" "${PIP_ARGS[@]}"
"$PYV" -m pip install edge-tts miniaudio timm "${PIP_ARGS[@]}" || {
    echo "TTS 依赖安装失败：可先用 espeak-ng 或 --no-tts" >&2
}

# 系统库提示（不自动 sudo，交给用户决定）
missing=()
command -v espeak-ng >/dev/null 2>&1 || command -v espeak >/dev/null 2>&1 || missing+=("espeak-ng（离线 TTS 兜底）")
[[ -f /usr/lib/x86_64-linux-gnu/libportaudio.so.2 ]] || missing+=("libportaudio2（sounddevice 依赖）")
ldconfig -p 2>/dev/null | grep -q libGL.so.1 || missing+=("libgl1（opencv 依赖）")
if [[ ${#missing[@]} -gt 0 ]]; then
    echo
    echo "建议补装系统库（Debian/Ubuntu）：" >&2
    echo "  sudo apt install ${missing[*]}"
fi
if command -v id >/dev/null 2>&1 && ! id -nG "$USER" 2>/dev/null | tr ' ' '\n' | grep -qx dialout; then
    echo "提示：当前用户不在 dialout 组，三块 Pico 的串口会打不开：" >&2
    echo "  sudo usermod -aG dialout $USER   # 重新登录生效" >&2
fi

export EMOBOT_MODEL_DIR="$MODEL_DIR"
if [[ "$WITH_MODELS" -eq 1 ]]; then
    echo "下载模型到 $MODEL_DIR ..."
    "$PYV" scripts/prefetch_models.py --dest "$MODEL_DIR"
else
    echo "跳过模型下载（加 --with-models 自动下载，或稍后跑 prefetch_models.py）"
fi

echo
echo "运行环境自检 ..."
"$PYV" scripts/selfcheck.py
CHECK_EXIT=$?

echo
echo "== 完成 =="
echo "激活环境:   source .venv/bin/activate"
echo "设置模型:   export EMOBOT_MODEL_DIR=$MODEL_DIR"
echo "跑测试:     python -m pytest -q"
echo "启动 demo:  python -m app.run --source mic"
if [[ $CHECK_EXIT -ne 0 ]]; then
    echo "自检有失败项（见上），先修好再演示。" >&2
    exit $CHECK_EXIT
fi
