# emotionbot

给 Will Cogley 的 Robot Head α2.0.33 加上情感感知和表达：3 块 Pico 控制 21 个舵机，电脑负责摄像头、麦克风和决策。

基于 [Robot Head α2.0.33](https://willcogley.notion.site/Robot-Head-2-0-33-1d724779b64d80568fd9cf1c7abd3e64) 和 [EyeMech ε3.2](https://willcogley.notion.site/EyeMech-3-1-1af24779b64d80b19edfdd795d4b90e5)，作者 Will Cogley，协议 CC BY-NC-SA 4.0。本仓库的 PCB、打印件等衍生内容沿用同一协议，不得商用。

上游 GitHub 仓库（作者账号 [will-cogley](https://github.com/will-cogley)）：

| 仓库 | 内容 | 注意 |
|---|---|---|
| [will-cogley/RobotHead](https://github.com/will-cogley/RobotHead) | 摄像头人脸追踪、舵机编排代码，没有 STL 和 PCB | 上游代码目前只支持一个下颌舵机（`JAWLEFT`），本项目 JL、JR 都接；仓库未声明协议，复用代码前先确认授权 |
| [will-cogley/EyeMech_Epsilon](https://github.com/will-cogley/EyeMech_Epsilon) | 眼部机构打印件、代码、装配 PDF、License | |

## 目录

| 路径 | 内容 |
|---|---|
| `firmware/` | 三块 Pico 共用的 MicroPython 固件，`config_*.py` 是舵机引脚和范围的唯一数据源 |
| `head/` | 电脑端控制，22 维动作空间 u ∈ [0,1] |
| `perception/` | 实时感知：VAD、SenseVoice ASR+SER、emotion2vec、人脸情绪、文本情感、融合与矛盾检测 |
| `agent/` | 中枢决策：情绪状态平滑、表情策略、idle 动画、TTS、回声门控 |
| `app/` | 运行时：`python -m app.run` 装配闭环 + 标准库仪表盘 |
| `scripts/` | 舵机测试、表情模仿、装配图渲染、颈部支架 CAD、环境自检、模型预下载 |
| `pcb/` | 嘴部板、眼眉板的工程文件和 Gerber |
| `emo_bench/` | 情感识别 benchmark（代码和汇总结果，数据不在仓库） |
| `print_package/给朋友打印_2026-11-01/` | 补打零件 STL 和拓竹打印说明 |
| `docs/` | 组装、焊接、电源、螺丝清单、复现计划、情感模块文档；`docs/综述/` 是调研报告和论文精读 |

从这里开始看：`docs/组装流程.html`、`docs/复现计划.md`、`docs/装配核查-可选与待测.md`。

接线和测试：`docs/舵机接线与上电检查.html`、`docs/下巴和嘴部测试交接.md`。

## 快速开始

```bash
uv venv && uv pip install -e '.[dev]'
.venv/bin/pytest -q                                  # 用假硬件测固件和电脑端
.venv/bin/python scripts/demo_expressions.py --viz   # 表情预览
firmware/flash.sh eyes                               # 刷 Pico（eyes / brows / mouth，先刷 MicroPython）
.venv/bin/python scripts/servo_check.py --board eyes # 逐个测舵机
.venv/bin/python scripts/servo_check.py --center     # 全部 90°，装舵盘前用
.venv/bin/mpremote run firmware/sweep_test.py        # 不刷固件，只测一个舵机
```

## 实时闭环（黑客松）

麦克风 / T5 板 → VAD 切句 → SenseVoice（文本 + 情感标签）+ emotion2vec（语音情感）
+ 人脸情绪 + 文本情感 → 融合与**语气/字面矛盾检测** → 规则策略 → 22 维表情 + TTS 回应，
全程在仪表盘上可见。

```powershell
# 0. 环境（Python 3.11/3.12；每台机器各跑一次）
powershell -File scripts\setup_env.ps1 -WithModels        # Windows
```
```bash
bash scripts/setup_env.sh --with-models                   # Linux（演示机 4060 用这个）
```

```powershell
# 1. 起演示（笔记本麦克风 + 摄像头 + 本机扬声器 + 真机头）
python -m app.run

# 2. 其他输入源
python -m app.run --source udp --udp-port 8770          # T5 板推 16k/s16le PCM 到 8770
python -m app.run --source file --wav demo.wav --loop   # 离线回放
python -m app.run --stub --sim                          # 不加载模型，只调界面

# 3. 常用开关：--sim 不连 Pico；--no-face；--no-tts；--ports COM5,COM6,COM7
# 4. 排障
python scripts\selfcheck.py
python scripts\list_ports.py
```

浏览器打开 `http://127.0.0.1:8000`。仪表盘给出三模态概率、融合结果、矛盾横幅、
60 秒时间线、22 维驱动的 2D 表情、端到端延迟，以及 Rest / 手动表情 / 手动说话按钮。

**兜底顺序**：真机头 → 仿真（仪表盘 2D 脸）；T5 音频 → 笔记本麦克风 → wav 回放；
摄像头 → 纯音频文本；在线 TTS → 本地 TTS（Windows SAPI / Linux espeak-ng）→ 静音。
任何一环缺失都不会让 demo 起不来。

**Linux 演示机**（RTX 4060 Laptop 8GB）：
- Pico 三块板是 `/dev/ttyACM*`，自动发现走 USB VID `0x2E8A`；打不开就 `sudo usermod -aG dialout $USER` 后重新登录，或 `--ports /dev/ttyACM0,/dev/ttyACM1,/dev/ttyACM2`
- 多块声卡时用 `EMOBOT_AUDIO_OUT=<设备号或名字>` 指定 TTS 输出，`--mic-device` 指定麦克风
- 离线兜底 TTS 用 `sudo apt install espeak-ng`；在线 edge-tts 正常时不使用
- 显存 8GB 比开发机 6GB 宽裕，模型目录放在 `$HOME/emo_models`（或任意盘，改 `EMOBOT_MODEL_DIR`），直接把开发机下好的整个目录 `rsync` 过去最省时间

队友接口（T5 音频格式、扬声器回传、Pico 口号）见 `docs/实时管道-队友接口.md`。

## 不在仓库里的文件

- 完整打印包、Blender 装配模型：见 GitHub Release。
- 原作者文件：从上面的官方页面下载，放到 `upstream/`。重新生成装配图需要 `upstream/` 里的参考 OBJ。
- 模型权重放 `models/`，数据集放 `datasets/`、`emo_bench/data/`，都已忽略。
- API key 放 `emo_bench/.env`，不要提交。
