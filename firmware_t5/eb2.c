/* EB2：屏幕回传 + 语音上下行 + 串口提速。和 EB1 文本命令共用 UART0。
 *
 * 线程模型
 *   LVGL 任务   ：flush 钩子把刷新区域拷进影子帧缓冲，并合并成一个脏矩形（只持锁拷贝，很快）
 *   eb2_rx 线程 ：读 UART，分出 EB1 文本行（交给 on_line）和 PCM_DOWN 二进制包
 *   eb2_tx 线程 ：按帧率发屏幕脏矩形；把麦克风环形缓冲里的 20 ms 帧发成 PCM_UP
 *   eb2_play    ：把喇叭环形缓冲里的 PCM 交给 tdl_audio_play（可能阻塞，所以单独一个线程）
 */
#include <stdio.h>
#include <string.h>
#include <stdlib.h>
#include <stdarg.h>
#include "tuya_cloud_types.h"
#include "tal_api.h"
#include "tal_uart.h"
#include "tkl_gpio.h"
#include "tdl_audio_manage.h"
#include "board_com_api.h"
#include "lv_vendor.h"
#include "src/display/lv_display_private.h"   /* 取原来的 flush_cb */
#include "eb2.h"

#define MAGIC0 0xEB
#define MAGIC1 0x02
#define T_SCREEN_INFO 0x01
#define T_SCREEN_RECT 0x02
#define T_SCREEN_END  0x03
#define T_PCM_UP      0x10
#define T_PCM_DOWN    0x11
#define T_PCM_STAT    0x12
#define MAX_PAYLOAD   4096
#define UART_PORT     TUYA_UART_NUM_0
#define BASE_BAUD     115200
#define RX_BUF        8192

/* ---------- UART 写 ---------- */
static MUTEX_HANDLE tx_lock;
static uint32_t cur_baud = BASE_BAUD;

void eb2_write(const void *data, size_t len)
{
    const uint8_t *p = data;
    if (tx_lock) tal_mutex_lock(tx_lock);
    while (len) {
        int n = tal_uart_write(UART_PORT, p, len > 512 ? 512 : (uint32_t)len);
        if (n <= 0) { tal_system_sleep(1); continue; }
        p += n; len -= (size_t)n;
    }
    if (tx_lock) tal_mutex_unlock(tx_lock);
}

static uint16_t crc16(const uint8_t *d, size_t n)
{
    uint16_t c = 0xFFFF;
    while (n--) {
        c ^= (uint16_t)(*d++) << 8;
        for (int i = 0; i < 8; i++) c = (c & 0x8000) ? (uint16_t)((c << 1) ^ 0x1021) : (uint16_t)(c << 1);
    }
    return c;
}

static uint16_t tx_seq;
static uint8_t pkt[8 + MAX_PAYLOAD + 2];

/* 调用方持有 tx_lock 以外的“发包锁”：只有 eb2_tx 线程和 rx 线程的 PCM_STAT 会发包，用 pkt_lock 保护 pkt 缓冲 */
static MUTEX_HANDLE pkt_lock;
static void send_packet(uint8_t type, const uint8_t *head, size_t hn, const uint8_t *body, size_t bn)
{
    size_t len = hn + bn;
    if (len > MAX_PAYLOAD) return;
    tal_mutex_lock(pkt_lock);
    pkt[0] = MAGIC0; pkt[1] = MAGIC1; pkt[2] = type; pkt[3] = 0;
    uint16_t s = tx_seq++;
    pkt[4] = s & 0xFF; pkt[5] = s >> 8; pkt[6] = len & 0xFF; pkt[7] = len >> 8;
    if (hn) memcpy(pkt + 8, head, hn);
    if (bn) memcpy(pkt + 8 + hn, body, bn);
    uint16_t c = crc16(pkt + 2, 6 + len);
    pkt[8 + len] = c & 0xFF; pkt[9 + len] = c >> 8;
    eb2_write(pkt, 10 + len);
    tal_mutex_unlock(pkt_lock);
}

/* ---------- 屏幕 ---------- */
static uint16_t *shadow;                 /* RGB565，逻辑坐标，和 LVGL 一致 */
static uint32_t scr_w, scr_h;
static MUTEX_HANDLE shadow_lock;
static int dx1 = 1 << 20, dy1 = 1 << 20, dx2 = -1, dy2 = -1;   /* 脏矩形 */
static volatile int scr_stream;
static volatile uint32_t scr_period_ms = 200;
static volatile int scr_full;            /* 请求整帧 */
static volatile int scr_once;
static uint16_t frame_no;
static lv_display_flush_cb_t orig_flush;
static uint32_t flush_cnt;

static void flush_hook(lv_display_t *disp, const lv_area_t *area, uint8_t *px_map)
{
    if (shadow && lv_display_get_color_format(disp) == LV_COLOR_FORMAT_RGB565) {
        int w = area->x2 - area->x1 + 1, h = area->y2 - area->y1 + 1;
        int stride = lv_draw_buf_width_to_stride(w, LV_COLOR_FORMAT_RGB565);
        if (area->x1 >= 0 && area->y1 >= 0 && (uint32_t)area->x2 < scr_w && (uint32_t)area->y2 < scr_h) {
            tal_mutex_lock(shadow_lock);
            for (int r = 0; r < h; r++)
                memcpy(shadow + (area->y1 + r) * scr_w + area->x1, px_map + r * stride, (size_t)w * 2);
            if (area->x1 < dx1) dx1 = area->x1;
            if (area->y1 < dy1) dy1 = area->y1;
            if (area->x2 > dx2) dx2 = area->x2;
            if (area->y2 > dy2) dy2 = area->y2;
            flush_cnt++;
            tal_mutex_unlock(shadow_lock);
        }
    }
    orig_flush(disp, area, px_map);
}

/* 一行 RLE：(次数, 像素lo, 像素hi)*，返回字节数 */
static size_t rle_row(const uint16_t *px, int w, uint8_t *out)
{
    size_t n = 0;
    int i = 0;
    while (i < w) {
        int j = i + 1;
        while (j < w && j - i < 255 && px[j] == px[i]) j++;
        out[n++] = (uint8_t)(j - i); out[n++] = px[i] & 0xFF; out[n++] = px[i] >> 8;
        i = j;
    }
    return n;
}

static void send_rect(uint16_t frame, int x, int y, int w, int h)
{
    static uint8_t body[MAX_PAYLOAD];
    static uint8_t row[255 * 3 + 3];
    size_t used = 0; int rows = 0, y0 = y;
    for (int r = 0; r < h; r++) {
        size_t rn;
        tal_mutex_lock(shadow_lock);
        rn = rle_row(shadow + (size_t)(y + r) * scr_w + x, w, row);
        tal_mutex_unlock(shadow_lock);
        if (rows && used + rn > MAX_PAYLOAD - 11) {
            uint8_t hd[11] = {frame & 0xFF, frame >> 8, x & 0xFF, x >> 8, y0 & 0xFF, y0 >> 8, w & 0xFF, w >> 8, rows & 0xFF, rows >> 8, 1};
            send_packet(T_SCREEN_RECT, hd, 11, body, used);
            used = 0; rows = 0; y0 = y + r;
        }
        memcpy(body + used, row, rn); used += rn; rows++;
    }
    if (rows) {
        uint8_t hd[11] = {frame & 0xFF, frame >> 8, x & 0xFF, x >> 8, y0 & 0xFF, y0 >> 8, w & 0xFF, w >> 8, rows & 0xFF, rows >> 8, 1};
        send_packet(T_SCREEN_RECT, hd, 11, body, used);
    }
}

static void send_info(void)
{
    uint8_t b[5] = {scr_w & 0xFF, scr_w >> 8, scr_h & 0xFF, scr_h >> 8, 0};
    send_packet(T_SCREEN_INFO, b, 5, NULL, 0);
}

static void screen_pump(void)
{
    if (!shadow || !(scr_stream || scr_once)) return;
    int x1, y1, x2, y2;
    tal_mutex_lock(shadow_lock);
    if (scr_full) { dx1 = 0; dy1 = 0; dx2 = scr_w - 1; dy2 = scr_h - 1; scr_full = 0; }
    x1 = dx1; y1 = dy1; x2 = dx2; y2 = dy2;
    if (x2 >= x1) { dx1 = dy1 = 1 << 20; dx2 = dy2 = -1; }
    tal_mutex_unlock(shadow_lock);
    if (x2 < x1) return;
    scr_once = 0;
    uint16_t f = ++frame_no;
    send_rect(f, x1, y1, x2 - x1 + 1, y2 - y1 + 1);
    uint8_t e[2] = {f & 0xFF, f >> 8};
    send_packet(T_SCREEN_END, e, 2, NULL, 0);
}

/* ---------- 语音 ---------- */
#define UP_FRAMES 64            /* 麦克风环：64 * 640 B ≈ 1.3 s */
#define FR_BYTES  640
static uint8_t up_ring[UP_FRAMES][FR_BYTES];
static uint8_t up_vad[UP_FRAMES];
static uint32_t up_ts[UP_FRAMES];
static volatile uint32_t up_w, up_r, up_drop;
static volatile int vad_now;
static volatile int voice_on;
static TDL_AUDIO_HANDLE_T aud;

#define PLAY_BYTES (32 * 1024)  /* 喇叭环：1 s */
static uint8_t *play_ring;
static volatile uint32_t pl_w, pl_r, pl_drop, pl_under;
static uint8_t spk_vol = 60;

int eb2_voice_active(void) { return voice_on; }

static void mic_cb(TDL_AUDIO_FRAME_FORMAT_E type, TDL_AUDIO_STATUS_E status, uint8_t *data, uint32_t len)
{
    (void)type;
    if (status == TDL_AUDIO_STATUS_VAD_START) vad_now = 1;
    else if (status == TDL_AUDIO_STATUS_VAD_END) vad_now = 0;
    if (!voice_on || !data || len == 0) return;
    while (len) {
        uint32_t n = len > FR_BYTES ? FR_BYTES : len;
        if (up_w - up_r >= UP_FRAMES) { up_r++; up_drop++; }
        uint32_t k = up_w % UP_FRAMES;
        memset(up_ring[k], 0, FR_BYTES);
        memcpy(up_ring[k], data, n);
        up_vad[k] = (uint8_t)vad_now;
        up_ts[k] = (uint32_t)tal_system_get_millisecond();
        up_w++;
        data += n; len -= n;
    }
}

static int voice_start(void)
{
    if (voice_on) return 0;
    int err = tdl_audio_find(AUDIO_CODEC_NAME, &aud);
    if (!err) { up_w = up_r = 0; pl_w = pl_r = 0; err = tdl_audio_open(aud, mic_cb); }
    if (!err) { tdl_audio_volume_set(aud, spk_vol); voice_on = 1; }
    return err;
}

static void voice_stop(void)
{
    if (!voice_on) return;
    voice_on = 0;
    tal_system_sleep(60);
    tdl_audio_play_stop(aud);
    tdl_audio_close(aud);
}

static void voice_pump(void)
{
    while (voice_on && up_r != up_w) {
        uint32_t k = up_r % UP_FRAMES;
        uint8_t hd[5] = {up_ts[k] & 0xFF, (up_ts[k] >> 8) & 0xFF, (up_ts[k] >> 16) & 0xFF, up_ts[k] >> 24, up_vad[k]};
        send_packet(T_PCM_UP, hd, 5, up_ring[k], FR_BYTES);
        up_r++;
    }
}

static void play_task(void *arg)
{
    (void)arg;
    static uint8_t chunk[FR_BYTES];
    for (;;) {
        if (!voice_on || pl_w - pl_r < FR_BYTES) {
            if (voice_on && pl_w == pl_r) pl_under++;
            tal_system_sleep(5);
            continue;
        }
        for (uint32_t i = 0; i < FR_BYTES; i++) chunk[i] = play_ring[(pl_r + i) % PLAY_BYTES];
        pl_r += FR_BYTES;
        tdl_audio_play(aud, chunk, FR_BYTES);
    }
}

static void pcm_down(const uint8_t *d, uint32_t n)
{
    if (!voice_on) return;
    if (PLAY_BYTES - (pl_w - pl_r) < n) { pl_drop++; return; }
    for (uint32_t i = 0; i < n; i++) play_ring[(pl_w + i) % PLAY_BYTES] = d[i];
    pl_w += n;
}

static void send_stat(void)
{
    uint32_t q = (pl_w - pl_r) / 32;          /* 16 kHz s16 = 32 B/ms */
    uint8_t b[12] = {q & 0xFF, (q >> 8) & 0xFF, pl_under & 0xFF, (pl_under >> 8) & 0xFF,
                     pl_drop & 0xFF, (pl_drop >> 8) & 0xFF, up_drop & 0xFF, (up_drop >> 8) & 0xFF,
                     flush_cnt & 0xFF, (flush_cnt >> 8) & 0xFF, 0, 0};
    send_packet(T_PCM_STAT, b, 10, NULL, 0);
}

/* ---------- 命令（EB1 文本，EB2 新增部分） ---------- */
static volatile uint32_t pending_baud;
static volatile uint32_t baud_deadline;     /* 提速后 3 s 内没收到命令就回退 */
static eb2_line_cb line_cb;

static void reply(unsigned id, const char *fmt, ...)
{
    char b[96];
    int n = snprintf(b, sizeof b, "EB1 %u ", id);
    va_list ap; va_start(ap, fmt);
    n += vsnprintf(b + n, sizeof b - n, fmt, ap);
    va_end(ap);
    b[n++] = '\n';
    eb2_write(b, n);
}

static int handle_eb2_command(char *line)
{
    unsigned id; char op[12], a1[12] = "", a2[12] = "";
    int f = sscanf(line, "EB1 %u %11s %11s %11s", &id, op, a1, a2);
    if (f < 2) return 0;
    if (!strcmp(op, "SCREEN")) {
        if (!shadow) { reply(id, "ERR SCREEN nobuf"); return 1; }
        if (!strcmp(a1, "START")) {
            unsigned fps = (f > 3) ? (unsigned)atoi(a2) : 5;
            if (fps < 1) fps = 1;
            if (fps > 20) fps = 20;
            scr_period_ms = 1000 / fps;
            reply(id, "OK SCREEN %u %u 0", (unsigned)scr_w, (unsigned)scr_h);
            send_info(); scr_full = 1; scr_stream = 1;
        } else if (!strcmp(a1, "SNAP")) {
            reply(id, "OK SCREEN %u %u 0", (unsigned)scr_w, (unsigned)scr_h);
            send_info(); scr_full = 1; scr_once = 1;
        } else if (!strcmp(a1, "STOP")) {
            scr_stream = 0; reply(id, "OK SCREEN STOP");
        } else reply(id, "ERR command");
        return 1;
    }
    if (!strcmp(op, "VOICE")) {
        if (!strcmp(a1, "START")) {
            int e = voice_start();
            if (e) reply(id, "ERR VOICE %d", e); else reply(id, "OK VOICE START");
        } else if (!strcmp(a1, "STOP")) { voice_stop(); reply(id, "OK VOICE STOP"); }
        else if (!strcmp(a1, "VOL") && f > 3) {
            spk_vol = (uint8_t)atoi(a2);
            if (voice_on) tdl_audio_volume_set(aud, spk_vol);
            reply(id, "OK VOICE VOL %u", spk_vol);
        } else reply(id, "ERR command");
        return 1;
    }
    if (!strcmp(op, "BAUD")) {
        uint32_t b = (uint32_t)atoi(a1);
        if (b < 9600 || b > 2000000)   /* 实测 2M 稳定，3M 不通 */ { reply(id, "ERR BAUD"); return 1; }
        reply(id, "OK BAUD %u", (unsigned)b);
        pending_baud = b;
        return 1;
    }
    if (!strcmp(op, "SPK") && f >= 3) {      /* 诊断：直接强制功放使能脚 GPIO28 的电平 */
        int lvl = atoi(a1) ? 1 : 0;
        tkl_gpio_write(TUYA_GPIO_NUM_28, lvl ? TUYA_GPIO_LEVEL_HIGH : TUYA_GPIO_LEVEL_LOW);
        reply(id, "OK SPK %d", lvl);
        return 1;
    }
    if (!strcmp(op, "STAT")) {
        reply(id, "OK STAT baud=%u voice=%d scr=%d flush=%u", (unsigned)cur_baud, voice_on, scr_stream, (unsigned)flush_cnt);
        return 1;
    }
    return 0;
}

static int uart_open(uint32_t baud)
{
    TAL_UART_CFG_T c = {0};
    c.base_cfg.baudrate = baud;
    c.base_cfg.databits = TUYA_UART_DATA_LEN_8BIT;
    c.base_cfg.stopbits = TUYA_UART_STOP_LEN_1BIT;
    c.base_cfg.parity = TUYA_UART_PARITY_TYPE_NONE;
    c.rx_buffer_size = RX_BUF;
    return tal_uart_init(UART_PORT, &c);
}

/* ---------- 接收线程：EB1 文本行 + EB2 包 ---------- */
static void rx_task(void *arg)
{
    (void)arg;
    static uint8_t buf[MAX_PAYLOAD + 16 + 256];
    static char line[96];
    uint32_t have = 0;
    uint32_t last_cmd = (uint32_t)tal_system_get_millisecond();
    uint8_t in[256];
    for (;;) {
        uint32_t now = (uint32_t)tal_system_get_millisecond();
        if (pending_baud) {                      /* 回执发完、发送缓冲排空后再切 */
            uint32_t b = pending_baud; pending_baud = 0;
            tal_system_sleep(30);
            tal_mutex_lock(tx_lock);
            tal_uart_deinit(UART_PORT);
            if (uart_open(b) != OPRT_OK) { uart_open(BASE_BAUD); cur_baud = BASE_BAUD; }
            else { cur_baud = b; baud_deadline = now + 4000; }
            tal_mutex_unlock(tx_lock);
            have = 0; last_cmd = now;
        }
        if (cur_baud != BASE_BAUD && baud_deadline && (int32_t)(now - baud_deadline) > 0) {
            tal_mutex_lock(tx_lock);               /* 提速后电脑没有联系上：回退，防止失联 */
            tal_uart_deinit(UART_PORT); uart_open(BASE_BAUD); cur_baud = BASE_BAUD;
            tal_mutex_unlock(tx_lock);
            baud_deadline = 0; have = 0;
        }
        int n = tal_uart_read(UART_PORT, in, sizeof in);
        if (n <= 0) { tal_system_sleep(2); continue; }
        if (have + (uint32_t)n > sizeof buf) have = 0;
        memcpy(buf + have, in, n); have += (uint32_t)n;
        uint32_t pos = 0;
        while (pos < have) {
            if (buf[pos] == MAGIC0) {
                if (have - pos < 2) break;
                if (buf[pos + 1] != MAGIC1) { pos++; continue; }
                if (have - pos < 8) break;
                uint32_t len = buf[pos + 6] | (buf[pos + 7] << 8);
                if (len > MAX_PAYLOAD) { pos++; continue; }
                if (have - pos < 10 + len) break;
                uint16_t c = crc16(buf + pos + 2, 6 + len);
                if (c == (buf[pos + 8 + len] | (buf[pos + 9 + len] << 8))) {
                    if (buf[pos + 2] == T_PCM_DOWN) { pcm_down(buf + pos + 8, len); }
                    pos += 10 + len;
                } else pos++;
                continue;
            }
            uint8_t *nl = memchr(buf + pos, '\n', have - pos);
            uint8_t *eb = memchr(buf + pos, MAGIC0, have - pos);
            if (eb && (!nl || eb < nl)) { pos = (uint32_t)(eb - buf); continue; }
            if (!nl) { if (have - pos > 200) pos = have; break; }
            uint32_t ln = (uint32_t)(nl - (buf + pos));
            if (ln < sizeof line) {
                memcpy(line, buf + pos, ln); line[ln] = 0;
                if (ln && line[ln - 1] == '\r') line[ln - 1] = 0;
                last_cmd = now;
                if (!strncmp(line, "EB1 ", 4)) baud_deadline = 0;   /* 乱码不算联系上 */
                if (!handle_eb2_command(line) && line_cb) line_cb(line);
            }
            pos = (uint32_t)(nl - buf) + 1;
        }
        if (pos) { memmove(buf, buf + pos, have - pos); have -= pos; }
        (void)last_cmd;
    }
}

/* ---------- 发送线程 ---------- */
static void tx_task(void *arg)
{
    (void)arg;
    uint32_t last_scr = 0, last_stat = 0;
    for (;;) {
        uint32_t now = (uint32_t)tal_system_get_millisecond();
        voice_pump();
        if ((scr_stream && now - last_scr >= scr_period_ms) || scr_once) { last_scr = now; screen_pump(); }
        if (voice_on && now - last_stat >= 250) { last_stat = now; send_stat(); }
        tal_system_sleep(5);
    }
}

static THREAD_HANDLE th_rx, th_tx, th_play;
static int spawn(THREAD_HANDLE *h, THREAD_FUNC_CB fn, const char *name, uint32_t stack, int psram)
{
    THREAD_CFG_T c = {0};
    c.stackDepth = stack; c.priority = THREAD_PRIO_2; c.thrdname = (char *)name; c.psram_mode = psram;
    return tal_thread_create_and_start(h, NULL, NULL, fn, NULL, &c);
}

int eb2_start(eb2_line_cb on_line)
{
    line_cb = on_line;
    tal_mutex_create_init(&tx_lock);
    tal_mutex_create_init(&pkt_lock);
    tal_mutex_create_init(&shadow_lock);
    if (uart_open(BASE_BAUD) != OPRT_OK) return -1;

    lv_display_t *d = lv_display_get_default();
    scr_w = (uint32_t)lv_display_get_horizontal_resolution(d);
    scr_h = (uint32_t)lv_display_get_vertical_resolution(d);
    shadow = tal_psram_malloc((size_t)scr_w * scr_h * 2);
    play_ring = tal_psram_malloc(PLAY_BYTES);
    if (shadow) {
        memset(shadow, 0, (size_t)scr_w * scr_h * 2);
        orig_flush = d->flush_cb;
        lv_display_set_flush_cb(d, flush_hook);
        lv_obj_invalidate(lv_screen_active());        /* 让现有画面重画一遍，影子缓冲从此同步 */
    }
    spawn(&th_rx, rx_task, "eb2_rx", 8 * 1024, 0);
    spawn(&th_tx, tx_task, "eb2_tx", 8 * 1024, 0);
    spawn(&th_play, play_task, "eb2_play", 4 * 1024, 0);
    return 0;
}
