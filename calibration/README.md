# 人工标定表情库

运行 `scripts/tune_server.py` 并保存 neutral 后，这里生成 `expressions.json`。不预填未经人工确认的角度。

按[表情标定闭环](../docs/表情标定闭环.md)逐组调整、保存其余六类、重启后重放验收。JSON 是小型配置，正式标定后可与 `head/centers.json` 一起提交；`.lock` 是运行时锁文件，不提交。仿真库独立保存在 `outputs/calibration-sim/`。
