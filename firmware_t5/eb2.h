#ifndef EB2_H
#define EB2_H
#include <stdint.h>
#include <stddef.h>
#include "lvgl.h"

/* 电脑端协议见 docs/T5屏幕与语音协议-EB2.md */
typedef void (*eb2_line_cb)(char *line);

/* 在 lv_vendor_init() 之后调用：挂接屏幕刷新钩子，初始化 UART0 并启动收发线程。 */
int eb2_start(eb2_line_cb on_line);

/* 线程安全地写 UART0（回执、数据包共用一把锁）。 */
void eb2_write(const void *data, size_t len);

/* 语音通道占用麦克风/喇叭期间，AUDIO、MUSIC 自检应返回 busy。 */
int eb2_voice_active(void);
#endif
