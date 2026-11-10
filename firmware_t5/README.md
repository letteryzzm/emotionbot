# T5 固件（EB2 版）

> 历史实现。2026-11-10 已确定后续不使用 T5 开发板；新阶段由电脑直接接入麦克风、摄像头和扬声器。本目录保留用于追溯，不作为新流程的构建或运行依赖，见[下一阶段方案](../docs/下一阶段方案-上位机情绪识别与标定.md)。

基于协作者的线条表情版（`/srv/robot-head/t5_screen`，TuyaOpen 示例 `emotionbot_screen`），新增 `eb2.c/.h`，改动 `main.c`：

- 去掉 LVGL 定时器轮询 UART，改由 `eb2_start()` 启动收发线程；EB1 命令仍由 `host_command()` 处理，`EMOTION` 改 LVGL 对象时持 `lv_vendor_disp_lock()`。
- 用 flush 钩子把每次刷新拷进影子帧缓冲（PSRAM，320×480 RGB565），只发变化的脏矩形。
- `SCREEN`、`VOICE`、`BAUD`、`STAT` 四组新命令，见 `docs/T5屏幕与语音协议-EB2.md`。

## 在 ROG 上编译和刷写

SDK 在 `/srv/robot-head/tools/t5/TuyaOpen`（Gitee 克隆，固定提交 `a80c0dd`，T5AI 平台 `69793c6`）。
工具链用 curl 下载，脚本自带下载只有 10 KB/s。

```bash
cd /srv/robot-head/tools/t5/TuyaOpen && export PATH=$PWD:$PATH && . .venv/bin/activate
cp <本目录>/*.c <本目录>/*.h  examples/graphics/emotionbot_screen/src/
cp <本目录>/CMakeLists.txt     examples/graphics/emotionbot_screen/
cd examples/graphics/emotionbot_screen && tos.py build      # 首次要 echo 1 | tos.py config choice
./tools/t5/tyutool_cli write -d T5AI -p /dev/serial/by-id/usb-1a86_USB_Dual_Serial_5AAE165026-if00 -b 921600 -f dist/emotionbot_screen_1.0.0/emotionbot_screen_QIO_1.0.0.bin
```

回退固件：`/srv/robot-head/t5_screen/firmware/emotionbot_screen_QIO_line_faces.bin`（协作者的线条表情版）。
