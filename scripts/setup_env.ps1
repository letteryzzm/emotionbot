<#
.SYNOPSIS
    一键准备 EmotionBot 的 Python 3.11 环境。开发机和演示机都跑这一个脚本。

.EXAMPLE
    powershell -File scripts\setup_env.ps1
    powershell -File scripts\setup_env.ps1 -Torch cu121 -WithModels
    若提示禁止运行脚本：先执行 Set-ExecutionPolicy -Scope Process RemoteSigned 再重试。

.NOTES
    可重复执行：已存在的 venv 会复用，pip 安装本身是幂等的。
#>
param(
    [string]$PythonExe = "py -3.11",
    [ValidateSet("cu121", "cu124", "cpu")]
    [string]$Torch = "cu121",
    [string]$TorchIndex = "",
    [string]$PipMirror = "https://pypi.tuna.tsinghua.edu.cn/simple",
    [string]$ModelDir = "D:\emo_models",
    [switch]$WithModels
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
Set-Location $Root
Write-Host "== EmotionBot 环境准备 ==" -ForegroundColor Cyan
Write-Host "项目目录: $Root"

# 1. 找到 Python 3.11
$pyCmd = $PythonExe -split " "
$ver = & $pyCmd[0] $pyCmd[1..($pyCmd.Length-1)] -c "import sys;print('%d.%d'%sys.version_info[:2])" 2>$null
if (-not $ver) {
    Write-Host "找不到 Python。请安装 Python 3.11 后重试：" -ForegroundColor Red
    Write-Host "  winget install Python.Python.3.11"
    Write-Host "  或从 https://www.python.org/downloads/release/python-3119/ 安装"
    exit 1
}
if ($ver -notin @("3.11", "3.12")) {
    Write-Host "当前 Python $ver 不符合要求（需要 3.11/3.12）" -ForegroundColor Red
    exit 1
}
Write-Host "Python $ver OK" -ForegroundColor Green

# 2. venv
if (-not (Test-Path ".venv\Scripts\python.exe")) {
    Write-Host "创建 .venv ..."
    & $pyCmd[0] $pyCmd[1..($pyCmd.Length-1)] -m venv .venv
} else {
    Write-Host ".venv 已存在，复用"
}
$py = Join-Path $Root ".venv\Scripts\python.exe"

# 3. 基础工具
& $py -m pip install --upgrade pip -i $PipMirror
if ($LASTEXITCODE -ne 0) { throw "pip 升级失败，检查网络或 -PipMirror" }

# 4. torch（CUDA 版必须从官方 index 装，清华源没有）
if (-not $TorchIndex) {
    $TorchIndex = "https://download.pytorch.org/whl/$Torch"
}
Write-Host "安装 torch ($Torch): $TorchIndex" -ForegroundColor Cyan
& $py -m pip install torch torchvision torchaudio --index-url $TorchIndex
if ($LASTEXITCODE -ne 0) {
    Write-Host "torch 安装失败。可先试 CPU 版继续开发：" -ForegroundColor Yellow
    Write-Host "  $py -m pip install torch torchvision --index-url https://download.pytorch.org/whl/cpu"
    throw "torch 安装失败"
}

# 5. 项目依赖
Write-Host "安装项目依赖 ..."
& $py -m pip install -e ".[dev,audio,vision]" -i $PipMirror
if ($LASTEXITCODE -ne 0) { throw "项目依赖安装失败" }

Write-Host "安装实时推理依赖（funasr / edge-tts / 音频）..."
# 分成两条：emotion2vec 不是 PyPI 包（走 funasr + ModelScope），混在一起会让整条命令失败
& $py -m pip install funasr -i $PipMirror
# 必须锁 4.x：transformers 5.x 要求 torch>=2.6，cu121 的 torch 2.5.1 会被判定为不可用
& $py -m pip install "transformers==4.57.6" -i $PipMirror
if ($LASTEXITCODE -ne 0) {
    Write-Host "funasr 安装失败：界面、策略、离线回放仍可跑；优先检查 pip 源或 Python 版本" -ForegroundColor Yellow
}
& $py -m pip install edge-tts miniaudio pyttsx3 timm -i $PipMirror
if ($LASTEXITCODE -ne 0) {
    Write-Host "TTS 依赖安装失败：可先用 SAPI 或 --no-tts" -ForegroundColor Yellow
}

# 6. 模型
$env:EMOBOT_MODEL_DIR = $ModelDir
if ($WithModels) {
    Write-Host "下载模型到 $ModelDir ..." -ForegroundColor Cyan
    & $py scripts\prefetch_models.py --dest $ModelDir
} else {
    Write-Host "跳过模型下载（加 -WithModels 自动下载）"
}

# 7. 自检
Write-Host "`n运行环境自检 ..." -ForegroundColor Cyan
& $py scripts\selfcheck.py
$checkExit = $LASTEXITCODE

Write-Host "`n== 完成 ==" -ForegroundColor Green
Write-Host "激活环境:   .\.venv\Scripts\Activate.ps1"
Write-Host "设置模型:   `$env:EMOBOT_MODEL_DIR='$ModelDir'"
Write-Host "跑测试:     python -m pytest -q"
Write-Host "启动 demo:  python -m app.run --source mic"
if ($checkExit -ne 0) {
    Write-Host "自检有失败项（见上），先修好再演示。" -ForegroundColor Yellow
    exit $checkExit
}
