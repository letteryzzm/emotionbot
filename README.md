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
| `scripts/` | 舵机测试、表情模仿、装配图渲染、颈部支架 CAD |
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

## 不在仓库里的文件

- 完整打印包、Blender 装配模型：见 GitHub Release。
- 原作者文件：从上面的官方页面下载，放到 `upstream/`。重新生成装配图需要 `upstream/` 里的参考 OBJ。
- 模型权重放 `models/`，数据集放 `datasets/`、`emo_bench/data/`，都已忽略。
- API key 放 `emo_bench/.env`，不要提交。
