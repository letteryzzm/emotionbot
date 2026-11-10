#include <stdint.h>
#include <stdio.h>
#include <string.h>
#include "tuya_cloud_types.h"
#include "tal_api.h"
#include "tal_uart.h"
#include "tdl_audio_manage.h"
#include <math.h>
#include "tkl_output.h"
#include "board_com_api.h"
#include "lvgl.h"
#include "lv_vendor.h"
#include "bench.h"
#include "line_face.h"
#include "eb2.h"

LV_FONT_DECLARE(ui_font_cn_18);
LV_FONT_DECLARE(ui_font_cn_24);

/* Screen expressions and host commands are independent of the servo boards. */
static const char *emotions[] = {"平静", "开心", "难过", "生气", "惊讶", "害怕", "厌恶"};
static lv_obj_t *content;
static int page = 0;
static int emotion = 0;
static lv_obj_t *face_art;
static lv_timer_t *face_timer;
static unsigned face_tick;
static lv_obj_t *bench_lines[3];

static lv_obj_t *label(lv_obj_t *parent, const char *text, int x, int y, int size, uint32_t color)
{
    lv_obj_t *obj = lv_label_create(parent);
    lv_label_set_text(obj, text);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_style_text_color(obj, lv_color_hex(color), 0);
    lv_obj_set_style_text_font(obj, size >= 22 ? &ui_font_cn_24 : &ui_font_cn_18, 0);
    return obj;
}

static lv_obj_t *panel(lv_obj_t *parent, int x, int y, int w, int h, uint32_t color)
{
    lv_obj_t *obj = lv_obj_create(parent);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_size(obj, w, h);
    lv_obj_set_style_bg_color(obj, lv_color_hex(color), 0);
    lv_obj_set_style_border_width(obj, 0, 0);
    lv_obj_set_style_radius(obj, 18, 0);
    lv_obj_set_style_pad_all(obj, 0, 0);
    lv_obj_clear_flag(obj, LV_OBJ_FLAG_SCROLLABLE);
    return obj;
}

static void face_tick_cb(lv_timer_t *timer)
{
    (void)timer;
    if (page != 0 || face_art == NULL) return;
    static const int8_t bob[] = {0, 1, 2, 3, 2, 1, 0, -1};
    face_tick++;
    lv_obj_set_y(face_art, 13 + bob[face_tick % 8]);
}

static void draw_face(lv_obj_t *parent)
{
    face_art = line_face_create(parent, emotion);
    face_tick = 0;
}

static void render(void);
static void start_bench_once(void);

/* Single bounded acoustic test. Only aggregate levels leave the board. */
static unsigned audio_phase, mic_frames[3], mic_peak[3][2];
static unsigned tone_level(const int16_t *samples, unsigned n, float coef)
{
    float a = 0, b = 0;
    for (unsigned i = 0; i < n; i++) {
        float next = samples[i] + coef * a - b;
        b = a;
        a = next;
    }
    return (unsigned)(2.f * sqrtf(fmaxf(0, a*a+b*b-coef*a*b)) / n);
}
static void mic_frame(TDL_AUDIO_FRAME_FORMAT_E type, TDL_AUDIO_STATUS_E status,
                      uint8_t *data, uint32_t bytes)
{
    unsigned phase = __atomic_load_n(&audio_phase, __ATOMIC_RELAXED);
    if (!data || bytes < 32 || phase >= 3) return;
    unsigned n = bytes / 2;
    const float coeff[] = {1.847759f, 1.414214f};
    for (int j = 0; j < 2; j++) {
        unsigned level = tone_level((const int16_t *)data, n, coeff[j]);
        if (level > mic_peak[phase][j]) mic_peak[phase][j] = level;
    }
    mic_frames[phase]++;
}
static void audio_test(char *reply, size_t size, unsigned id)
{
    TDL_AUDIO_HANDLE_T h = NULL;
    memset(mic_frames, 0, sizeof(mic_frames));
    memset(mic_peak, 0, sizeof(mic_peak));
    __atomic_store_n(&audio_phase, 0, __ATOMIC_RELAXED);
    int err = tdl_audio_find(AUDIO_CODEC_NAME, &h);
    if (!err) err = tdl_audio_open(h, mic_frame);
    if (!err) {
        err = tdl_audio_volume_set(h, 45);
        tal_system_sleep(650);
        for (unsigned k = 1; !err && k <= 2; k++) {
            int16_t pcm[320];
            for (int i = 0; i < 320; i++)
                pcm[i] = (int16_t)(6000 * sinf(i * k * 0.39269908f));
            __atomic_store_n(&audio_phase, k, __ATOMIC_RELAXED);
            for (int j = 0; !err && j < 22; j++) {
                err = tdl_audio_play(h, (uint8_t *)pcm, sizeof(pcm));
                tal_system_sleep(20);
            }
            tal_system_sleep(180);
        }
        __atomic_store_n(&audio_phase, 3, __ATOMIC_RELAXED);
        tdl_audio_close(h);
    }
    if (err) snprintf(reply, size, "EB1 %u ERR AUDIO %d\n", id, err);
    else snprintf(reply, size, "EB1 %u AUDIO %u,%u,%u %u,%u %u,%u %u,%u\n", id,
                  mic_frames[0], mic_frames[1], mic_frames[2], mic_peak[0][0],
                  mic_peak[0][1], mic_peak[1][0], mic_peak[1][1], mic_peak[2][0], mic_peak[2][1]);
}

/* UART0 is the T5AI programming channel. Commands are handled on the LVGL
 * thread, so a success reply is sent only after the screen state is updated. */
static int play_twinkle(void)
{
    static const unsigned melody[] = {
        262,262,392,392,440,440,392,0,349,349,330,330,294,294,262,0,
        392,392,349,349,330,330,294,0,392,392,349,349,330,330,294,0,
        262,262,392,392,440,440,392,0,349,349,330,330,294,294,262,0
    };
    TDL_AUDIO_HANDLE_T h = NULL;
    int err = tdl_audio_find(AUDIO_CODEC_NAME, &h);
    if (!err) err = tdl_audio_open(h, mic_frame);
    if (err) return err;
    err = tdl_audio_volume_set(h, 45);
    for (unsigned k = 0; !err && k < sizeof(melody)/sizeof(melody[0]); ++k) {
        float phase = 0, step = melody[k] * (6.2831853f / 16000.f);
        for (int j = 0; !err && j < 14; ++j) {
            int16_t pcm[320];
            for (int i = 0; i < 320; ++i) {
                float env = j == 0 ? i/320.f : j == 13 ? 1.f-i/320.f : 1.f;
                pcm[i] = (int16_t)(6500 * env * sinf(phase));
                phase += step;
                if (phase >= 6.2831853f) phase -= 6.2831853f;
            }
            err = tdl_audio_play(h, (uint8_t *)pcm, sizeof(pcm));
            tal_system_sleep(20);
        }
    }
    tal_system_sleep(120);
    tdl_audio_close(h);
    return err;
}

static void host_command(char *line)
{
    static const char *names[] = {"neutral", "happy", "sad", "angry", "surprise", "fear", "disgust"};
    unsigned id;
    char op[16], arg[24], extra;
    char reply[96];
    int fields = sscanf(line, "EB1 %u %15s %23s %c", &id, op, arg, &extra);
    if (fields < 2) return;
    if (fields == 2 && strcmp(op, "PING") == 0) {
        snprintf(reply, sizeof(reply), "EB1 %u OK PONG\n", id);
    } else if (fields == 2 && eb2_voice_active() && (strcmp(op, "MUSIC") == 0 || strcmp(op, "AUDIO") == 0)) {
        snprintf(reply, sizeof(reply), "EB1 %u ERR busy\n", id);
    } else if (fields == 2 && strcmp(op, "MUSIC") == 0) {
        int err = play_twinkle();
        snprintf(reply, sizeof(reply), err ? "EB1 %u ERR MUSIC\n" : "EB1 %u OK MUSIC\n", id);
    } else if (fields == 2 && strcmp(op, "AUDIO") == 0) {
        audio_test(reply, sizeof(reply), id);
    } else if (fields == 3 && strcmp(op, "EMOTION") == 0) {
        int i;
        for (i = 0; i < 7 && strcmp(arg, names[i]) != 0; ++i) {}
        if (i == 7) {
            snprintf(reply, sizeof(reply), "EB1 %u ERR emotion\n", id);
        } else {
            emotion = i;
            lv_vendor_disp_lock();      /* 命令来自 eb2_rx 线程，改 LVGL 对象必须持锁 */
            render();
            lv_vendor_disp_unlock();
            snprintf(reply, sizeof(reply), "EB1 %u OK EMOTION %s\n", id, names[i]);
        }
    } else {
        snprintf(reply, sizeof(reply), "EB1 %u ERR command\n", id);
    }
    eb2_write(reply, strlen(reply));
}

static void nav_event(lv_event_t *event)
{
    if (lv_event_get_code(event) != LV_EVENT_CLICKED) return;
    page = (int)(intptr_t)lv_event_get_user_data(event);
    render();
    if (page == 3) start_bench_once();
}

static void emotion_event(lv_event_t *event)
{
    if (lv_event_get_code(event) != LV_EVENT_CLICKED) return;
    emotion = (int)(intptr_t)lv_event_get_user_data(event);
    PR_NOTICE("screen preview emotion: %s", emotions[emotion]);
    render();
}

static void button(lv_obj_t *parent, const char *text, int x, int y, int w, int h,
                   uint32_t color, lv_event_cb_t cb, int value)
{
    lv_obj_t *obj = lv_button_create(parent);
    lv_obj_set_pos(obj, x, y);
    lv_obj_set_size(obj, w, h);
    lv_obj_set_style_bg_color(obj, lv_color_hex(color), 0);
    lv_obj_set_style_radius(obj, 13, 0);
    lv_obj_add_event_cb(obj, cb, LV_EVENT_CLICKED, (void *)(intptr_t)value);
    lv_obj_t *txt = lv_label_create(obj);
    lv_label_set_text(txt, text);
    lv_obj_set_style_text_font(txt, &ui_font_cn_18, 0);
    lv_obj_center(txt);
}

static void render_home(void)
{
    lv_obj_t *hero = panel(content, 16, 4, 288, 297, 0x172B44);
    draw_face(hero);
    label(hero, emotions[emotion], 18, 256, 24, 0xE7F6FF);
    lv_obj_t *status = panel(content, 16, 307, 288, 47, 0x1A2638);
    label(status, "开发板在线，舵机板未连接", 13, 13, 18, 0xFFCA75);
}

static void render_emotions(void)
{
    label(content, "点击切换表情", 17, 9, 18, 0xB5C7D8);
    for (int i = 0; i < 7; ++i) {
        int col = i % 2, row = i / 2;
        button(content, emotions[i], 16 + col * 148, 44 + row * 72, 140, 61,
               i == emotion ? 0x197D75 : 0x243B55, emotion_event, i);
    }
    label(content, "仅供预览，未发送舵机指令", 16, 329, 18, 0xFFCA75);
}

static void render_device(void)
{
    lv_obj_t *card = panel(content, 16, 8, 288, 294, 0x1A2638);
    label(card, "硬件状态", 18, 22, 18, 0x6DE4C2);
    label(card, "屏幕：320乘480", 18, 65, 18, 0xE7F6FF);
    label(card, "触摸：已开启", 18, 97, 18, 0xE7F6FF);
    label(card, "摄像头：ROG 外接", 18, 129, 18, 0xE7F6FF);
    label(card, "音频：板载麦克风和扬声器", 18, 161, 18, 0xE7F6FF);
    label(card, "舵机板：未连接", 18, 193, 18, 0xFFCA75);
    label(card, "固件：线条表情联调版", 18, 245, 18, 0x9CB3C9);
    label(content, "离线运行，无需联网", 17, 323, 18, 0xB5C7D8);
}

static void refresh_bench(lv_timer_t *timer)
{
    (void)timer;
    if (page != 3) return;
    static const char *names[] = {"正弦模型", "关键词模型", "人像模型"};
    for (int i = 0; i < 3; ++i) {
        if (!bench_lines[i]) continue;
        char line[128];
        const bench_result_t *r = &bench_results[i];
        if (r->status == 0) snprintf(line, sizeof(line), "%s\n等待", names[i]);
        else if (r->status == 1) snprintf(line, sizeof(line), "%s\n运行中", names[i]);
        else if (r->status == 2) snprintf(line, sizeof(line), "%s  %lu字节\n耗时 %lu.%03lu毫秒\n内存 %lu/%lu字节", names[i],
                                           (unsigned long)r->model_bytes,
                                           (unsigned long)(r->latency_us / 1000),
                                           (unsigned long)(r->latency_us % 1000),
                                           (unsigned long)r->arena_bytes,
                                           (unsigned long)r->arena_alloc_bytes);
        else snprintf(line, sizeof(line), "%s\n运行失败（%d）", names[i], r->status);
        lv_label_set_text(bench_lines[i], line);
    }
}

static void render_models(void)
{
    label(content, "板上模型测速", 16, 5, 18, 0x6DE4C2);
    for (int i = 0; i < 3; ++i) {
        lv_obj_t *card = panel(content, 16, 32 + i * 96, 288, 86, 0x1A2638);
        bench_lines[i] = label(card, "等待", 16, 10, 18, 0xE7F6FF);
    }
    label(content, "仅测模拟输入；内存为已用/预留", 16, 329, 18, 0xFFCA75);
    refresh_bench(NULL);
}

static void render(void)
{
    face_art = NULL;
    bench_lines[0] = bench_lines[1] = bench_lines[2] = NULL;
    lv_obj_clean(content);
    if (page == 0) render_home();
    else if (page == 1) render_emotions();
    else if (page == 2) render_device();
    else render_models();
}

static THREAD_HANDLE bench_thread;
static int bench_started;
static void bench_task(void *arg)
{
    (void)arg;
    bench_run_all();
    tal_thread_delete(bench_thread);
}

static void start_bench_once(void)
{
    if (bench_started) return;
    bench_started = 1;
    THREAD_CFG_T cfg = {0};
    cfg.stackDepth = 128 * 1024;
    cfg.priority = THREAD_PRIO_1;
    cfg.thrdname = "ml_bench";
    cfg.psram_mode = TRUE;
    if (tal_thread_create_and_start(&bench_thread, NULL, NULL, bench_task, NULL, &cfg) != OPRT_OK) {
        bench_started = 0;
        PR_ERR("model benchmark thread failed");
    }
}

void user_main(void)
{
    tal_log_init(TAL_LOG_LEVEL_DEBUG, 4096, (TAL_LOG_OUTPUT_CB)tkl_log_output);
    if (board_register_hardware() != OPRT_OK) {
        PR_ERR("board_register_hardware failed");
        return;
    }
    lv_vendor_init(DISPLAY_NAME);
    lv_obj_t *screen = lv_screen_active();
    lv_obj_set_style_bg_color(screen, lv_color_hex(0x0B1727), 0);
    lv_obj_clear_flag(screen, LV_OBJ_FLAG_SCROLLABLE);
    label(screen, "表情机器人", 17, 10, 24, 0xE7F6FF);
    label(screen, "屏幕控制", 17, 39, 18, 0x6DE4C2);
    content = panel(screen, 0, 73, 320, 361, 0x0B1727);
    button(screen, "主页", 5, 438, 74, 40, 0x243B55, nav_event, 0);
    button(screen, "表情", 83, 438, 74, 40, 0x243B55, nav_event, 1);
    button(screen, "设备", 161, 438, 74, 40, 0x243B55, nav_event, 2);
    button(screen, "模型", 239, 438, 76, 40, 0x243B55, nav_event, 3);
    render();
    if (eb2_start(host_command) != 0)
        PR_ERR("eb2 start failed");
    face_timer = lv_timer_create(face_tick_cb, 160, NULL);
    lv_timer_create(refresh_bench, 500, NULL);
    lv_vendor_start(5, 1024 * 8);
}

static THREAD_HANDLE app_thread;
static void app_task(void *arg)
{
    (void)arg;
    user_main();
    tal_thread_delete(app_thread);
}

void tuya_app_main(void)
{
    THREAD_CFG_T cfg = {0};
    cfg.stackDepth = 1024 * 4;
    cfg.priority = THREAD_PRIO_1;
    cfg.thrdname = "screen_app";
    tal_thread_create_and_start(&app_thread, NULL, NULL, app_task, NULL, &cfg);
}
