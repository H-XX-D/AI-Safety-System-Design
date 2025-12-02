/*
 * Dashboard GUI implementation using esp_lcd
 * Renders a dark themed control panel with live system metrics.
 */

#include "gui.h"

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "esp_heap_caps.h"
#include "esp_lcd_panel_ops.h"
#include "esp_lcd_panel_rgb.h"
#include "esp_log.h"
#include "esp_timer.h"
#include "esp_err.h"
#include <driver/gpio.h>

// Optional touch callback provided by platform-specific code. When available
// it will forward coordinate-based taps to the registered handler.
static gui_touch_handler_t g_touch_handler = NULL;

// Glyph rotation modes for display orientation handling. Change this value
// to adapt to different panel orientations if needed. Placed early so any
// helper functions that map raw hardware input to UI coordinates can refer
// to the rotation constant.
// Use the runtime glyph rotation variable rather than a compile-time constant
// so we can cycle orientation without recompiling/flashing.
static GlyphRotationMode g_glyph_rotation = ROTATE_90;
static bool g_swap_xy = false;
static bool g_flip_x = false;
static bool g_flip_y = false;

void gui_register_touch_handler(gui_touch_handler_t handler) {
    g_touch_handler = handler;
}

void gui_fire_touch_coords(int x, int y, bool pressed)
{
    if (g_touch_handler) {
        g_touch_handler(x, y, pressed);
    }
}

void gui_map_coords_raw_to_ui(int raw_x, int raw_y, int raw_max_x, int raw_max_y, int* out_x, int* out_y)
{
    // Avoid divide-by-zero
    if (!out_x || !out_y) return;
    if (raw_max_x <= 0) raw_max_x = 4095;
    if (raw_max_y <= 0) raw_max_y = 4095;

    // Scale to viewport
    int sx = (raw_x * (GUI_LCD_H_RES - 1)) / raw_max_x;
    int sy = (raw_y * (GUI_LCD_V_RES - 1)) / raw_max_y;

    // Rotate based on current runtime glyph rotation setting
    switch (g_glyph_rotation) {
        case ROTATE_0:
            *out_x = sx;
            *out_y = sy;
            break;
        case ROTATE_90:
            *out_x = GUI_LCD_H_RES - 1 - sy;
            *out_y = sx;
            break;
        case ROTATE_180:
            *out_x = GUI_LCD_H_RES - 1 - sx;
            *out_y = GUI_LCD_V_RES - 1 - sy;
            break;
        case ROTATE_270:
            *out_x = sy;
            *out_y = GUI_LCD_V_RES - 1 - sx;
            break;
    }
    // Optionally swap axes and flip if the panel wiring or physical mount differs
    if (g_swap_xy) {
        int tmp = *out_x; *out_x = *out_y; *out_y = tmp;
    }
    if (g_flip_x) {
        *out_x = GUI_LCD_H_RES - 1 - *out_x;
    }
    if (g_flip_y) {
        *out_y = GUI_LCD_V_RES - 1 - *out_y;
    }
}


static const char* TAG = "gui";

#define LCD_H_RES 800
#define LCD_V_RES 480

// NOTE: Glyph rotation mode and kGlyphRotation are defined earlier in the file

static constexpr gpio_num_t LCD_BK_LIGHT_GPIO = GPIO_NUM_4;

/*
 * Font data adapted from https://github.com/dhepper/font8x8 (MIT License).
 */
static const uint8_t font8x8_basic[95][8] = {
    {0x00,0x00,0x00,0x00,0x00,0x00,0x00,0x00}, // 0x20 ' '
    {0x00,0x00,0x5f,0x00,0x00,0x00,0x00,0x00}, // 0x21 '!'
    {0x00,0x07,0x00,0x07,0x00,0x00,0x00,0x00}, // 0x22 '"'
    {0x14,0x7f,0x14,0x7f,0x14,0x00,0x00,0x00}, // 0x23 '#'
    {0x24,0x2a,0x7f,0x2a,0x12,0x00,0x00,0x00}, // 0x24 '$'
    {0x23,0x13,0x08,0x64,0x62,0x00,0x00,0x00}, // 0x25 '%'
    {0x36,0x49,0x55,0x22,0x50,0x00,0x00,0x00}, // 0x26 '&'
    {0x00,0x05,0x03,0x00,0x00,0x00,0x00,0x00}, // 0x27 '\''
    {0x00,0x1c,0x22,0x41,0x00,0x00,0x00,0x00}, // 0x28 '('
    {0x00,0x41,0x22,0x1c,0x00,0x00,0x00,0x00}, // 0x29 ')'
    {0x14,0x08,0x3e,0x08,0x14,0x00,0x00,0x00}, // 0x2a '*'
    {0x08,0x08,0x3e,0x08,0x08,0x00,0x00,0x00}, // 0x2b '+'
    {0x00,0x50,0x30,0x00,0x00,0x00,0x00,0x00}, // 0x2c ','
    {0x08,0x08,0x08,0x08,0x08,0x00,0x00,0x00}, // 0x2d '-'
    {0x00,0x60,0x60,0x00,0x00,0x00,0x00,0x00}, // 0x2e '.'
    {0x20,0x10,0x08,0x04,0x02,0x00,0x00,0x00}, // 0x2f '/'
    {0x3e,0x51,0x49,0x45,0x3e,0x00,0x00,0x00}, // 0x30 '0'
    {0x00,0x42,0x7f,0x40,0x00,0x00,0x00,0x00}, // 0x31 '1'
    {0x42,0x61,0x51,0x49,0x46,0x00,0x00,0x00}, // 0x32 '2'
    {0x21,0x41,0x45,0x4b,0x31,0x00,0x00,0x00}, // 0x33 '3'
    {0x18,0x14,0x12,0x7f,0x10,0x00,0x00,0x00}, // 0x34 '4'
    {0x27,0x45,0x45,0x45,0x39,0x00,0x00,0x00}, // 0x35 '5'
    {0x3c,0x4a,0x49,0x49,0x30,0x00,0x00,0x00}, // 0x36 '6'
    {0x01,0x71,0x09,0x05,0x03,0x00,0x00,0x00}, // 0x37 '7'
    {0x36,0x49,0x49,0x49,0x36,0x00,0x00,0x00}, // 0x38 '8'
    {0x06,0x49,0x49,0x29,0x1e,0x00,0x00,0x00}, // 0x39 '9'
    {0x00,0x36,0x36,0x00,0x00,0x00,0x00,0x00}, // 0x3a ':'
    {0x00,0x56,0x36,0x00,0x00,0x00,0x00,0x00}, // 0x3b ';'
    {0x08,0x14,0x22,0x41,0x00,0x00,0x00,0x00}, // 0x3c '<'
    {0x14,0x14,0x14,0x14,0x14,0x00,0x00,0x00}, // 0x3d '='
    {0x41,0x22,0x14,0x08,0x00,0x00,0x00,0x00}, // 0x3e '>'
    {0x02,0x01,0x51,0x09,0x06,0x00,0x00,0x00}, // 0x3f '?'
    {0x3e,0x41,0x5d,0x59,0x4e,0x00,0x00,0x00}, // 0x40 '@'
    {0x7e,0x11,0x11,0x11,0x7e,0x00,0x00,0x00}, // 0x41 'A'
    {0x7f,0x49,0x49,0x49,0x36,0x00,0x00,0x00}, // 0x42 'B'
    {0x3e,0x41,0x41,0x41,0x22,0x00,0x00,0x00}, // 0x43 'C'
    {0x7f,0x41,0x41,0x22,0x1c,0x00,0x00,0x00}, // 0x44 'D'
    {0x7f,0x49,0x49,0x49,0x41,0x00,0x00,0x00}, // 0x45 'E'
    {0x7f,0x09,0x09,0x09,0x01,0x00,0x00,0x00}, // 0x46 'F'
    {0x3e,0x41,0x49,0x49,0x7a,0x00,0x00,0x00}, // 0x47 'G'
    {0x7f,0x08,0x08,0x08,0x7f,0x00,0x00,0x00}, // 0x48 'H'
    {0x00,0x41,0x7f,0x41,0x00,0x00,0x00,0x00}, // 0x49 'I'
    {0x20,0x40,0x41,0x3f,0x01,0x00,0x00,0x00}, // 0x4a 'J'
    {0x7f,0x08,0x14,0x22,0x41,0x00,0x00,0x00}, // 0x4b 'K'
    {0x7f,0x40,0x40,0x40,0x40,0x00,0x00,0x00}, // 0x4c 'L'
    {0x7f,0x02,0x0c,0x02,0x7f,0x00,0x00,0x00}, // 0x4d 'M'
    {0x7f,0x04,0x08,0x10,0x7f,0x00,0x00,0x00}, // 0x4e 'N'
    {0x3e,0x41,0x41,0x41,0x3e,0x00,0x00,0x00}, // 0x4f 'O'
    {0x7f,0x09,0x09,0x09,0x06,0x00,0x00,0x00}, // 0x50 'P'
    {0x3e,0x41,0x51,0x21,0x5e,0x00,0x00,0x00}, // 0x51 'Q'
    {0x7f,0x09,0x19,0x29,0x46,0x00,0x00,0x00}, // 0x52 'R'
    {0x46,0x49,0x49,0x49,0x31,0x00,0x00,0x00}, // 0x53 'S'
    {0x01,0x01,0x7f,0x01,0x01,0x00,0x00,0x00}, // 0x54 'T'
    {0x3f,0x40,0x40,0x40,0x3f,0x00,0x00,0x00}, // 0x55 'U'
    {0x1f,0x20,0x40,0x20,0x1f,0x00,0x00,0x00}, // 0x56 'V'
    {0x7f,0x20,0x18,0x20,0x7f,0x00,0x00,0x00}, // 0x57 'W'
    {0x63,0x14,0x08,0x14,0x63,0x00,0x00,0x00}, // 0x58 'X'
    {0x03,0x04,0x78,0x04,0x03,0x00,0x00,0x00}, // 0x59 'Y'
    {0x61,0x51,0x49,0x45,0x43,0x00,0x00,0x00}, // 0x5a 'Z'
    {0x00,0x7f,0x41,0x41,0x00,0x00,0x00,0x00}, // 0x5b '['
    {0x02,0x04,0x08,0x10,0x20,0x00,0x00,0x00}, // 0x5c '\\'
    {0x00,0x41,0x41,0x7f,0x00,0x00,0x00,0x00}, // 0x5d ']'
    {0x04,0x02,0x01,0x02,0x04,0x00,0x00,0x00}, // 0x5e '^'
    {0x80,0x80,0x80,0x80,0x80,0x00,0x00,0x00}, // 0x5f '_'
    {0x00,0x03,0x05,0x00,0x00,0x00,0x00,0x00}, // 0x60 '`'
    {0x20,0x54,0x54,0x54,0x78,0x00,0x00,0x00}, // 0x61 'a'
    {0x7f,0x48,0x44,0x44,0x38,0x00,0x00,0x00}, // 0x62 'b'
    {0x38,0x44,0x44,0x44,0x20,0x00,0x00,0x00}, // 0x63 'c'
    {0x38,0x44,0x44,0x48,0x7f,0x00,0x00,0x00}, // 0x64 'd'
    {0x38,0x54,0x54,0x54,0x18,0x00,0x00,0x00}, // 0x65 'e'
    {0x08,0x7e,0x09,0x01,0x02,0x00,0x00,0x00}, // 0x66 'f'
    {0x0c,0x52,0x52,0x52,0x3e,0x00,0x00,0x00}, // 0x67 'g'
    {0x7f,0x08,0x04,0x04,0x78,0x00,0x00,0x00}, // 0x68 'h'
    {0x00,0x44,0x7d,0x40,0x00,0x00,0x00,0x00}, // 0x69 'i'
    {0x20,0x40,0x44,0x3d,0x00,0x00,0x00,0x00}, // 0x6a 'j'
    {0x7f,0x10,0x28,0x44,0x00,0x00,0x00,0x00}, // 0x6b 'k'
    {0x00,0x41,0x7f,0x40,0x00,0x00,0x00,0x00}, // 0x6c 'l'
    {0x7c,0x04,0x18,0x04,0x78,0x00,0x00,0x00}, // 0x6d 'm'
    {0x7c,0x08,0x04,0x04,0x78,0x00,0x00,0x00}, // 0x6e 'n'
    {0x38,0x44,0x44,0x44,0x38,0x00,0x00,0x00}, // 0x6f 'o'
    {0x7c,0x14,0x14,0x14,0x08,0x00,0x00,0x00}, // 0x70 'p'
    {0x08,0x14,0x14,0x18,0x7c,0x00,0x00,0x00}, // 0x71 'q'
    {0x7c,0x08,0x04,0x04,0x08,0x00,0x00,0x00}, // 0x72 'r'
    {0x48,0x54,0x54,0x54,0x20,0x00,0x00,0x00}, // 0x73 's'
    {0x04,0x3f,0x44,0x40,0x20,0x00,0x00,0x00}, // 0x74 't'
    {0x3c,0x40,0x40,0x20,0x7c,0x00,0x00,0x00}, // 0x75 'u'
    {0x1c,0x20,0x40,0x20,0x1c,0x00,0x00,0x00}, // 0x76 'v'
    {0x3c,0x40,0x30,0x40,0x3c,0x00,0x00,0x00}, // 0x77 'w'
    {0x44,0x28,0x10,0x28,0x44,0x00,0x00,0x00}, // 0x78 'x'
    {0x0c,0x50,0x50,0x50,0x3c,0x00,0x00,0x00}, // 0x79 'y'
    {0x44,0x64,0x54,0x4c,0x44,0x00,0x00,0x00}, // 0x7a 'z'
    {0x00,0x08,0x36,0x41,0x00,0x00,0x00,0x00}, // 0x7b '{'
    {0x00,0x00,0x7f,0x00,0x00,0x00,0x00,0x00}, // 0x7c '|'
    {0x00,0x41,0x36,0x08,0x00,0x00,0x00,0x00}, // 0x7d '}'
    {0x08,0x04,0x08,0x10,0x08,0x00,0x00,0x00}  // 0x7e '~'
};

static constexpr int FONT_SCALE_X = 1;
static constexpr int FONT_SCALE_Y = 1;
static constexpr int GLYPH_WIDTH = 8 * FONT_SCALE_X;
static constexpr int GLYPH_HEIGHT = 8 * FONT_SCALE_Y;
static constexpr int CHAR_SPACING = 3;
static constexpr int LINE_SPACING = 6;

static uint16_t* g_linebuf = nullptr;
static esp_lcd_panel_handle_t g_panel = NULL;

static inline int char_step(void) {
    if (g_glyph_rotation == ROTATE_90 || g_glyph_rotation == ROTATE_270) {
        return GLYPH_HEIGHT + CHAR_SPACING;
    }
    return GLYPH_WIDTH + CHAR_SPACING;
}

static inline int line_height(void) {
    if (g_glyph_rotation == ROTATE_90 || g_glyph_rotation == ROTATE_270) {
        return GLYPH_WIDTH + LINE_SPACING;
    }
    return GLYPH_HEIGHT + LINE_SPACING;
}

// Reverse bit order in a byte (8-bit value)
static inline uint8_t reverse_bits(uint8_t v) {
    // efficient reverse for 8-bit values
    v = ((v & 0xF0) >> 4) | ((v & 0x0F) << 4);
    v = ((v & 0xCC) >> 2) | ((v & 0x33) << 2);
    v = ((v & 0xAA) >> 1) | ((v & 0x55) << 1);
    return v;
}

// Rotate an 8x8 glyph as needed. The glyph input is the 8 bytes from font8x8 that
// correspond to rows; the output 'out' will contain 8 bytes in the same format.
static void rotate_glyph(const uint8_t* glyph, uint8_t out[8], GlyphRotationMode mode)
{
    switch (mode) {
        case ROTATE_0:
            for (int r = 0; r < 8; ++r) out[r] = glyph[r];
            break;
        case ROTATE_90: {
            // rotated[r][c] = original[7 - c][r]
            for (int r = 0; r < 8; ++r) {
                uint8_t row = 0;
                for (int c = 0; c < 8; ++c) {
                    uint8_t bit = (glyph[7 - c] >> r) & 1;
                    row |= (bit << c);
                }
                out[r] = row;
            }
            break;
        }
        case ROTATE_180: {
            // rotated[r] = reverse_bits(original[7 - r])
            for (int r = 0; r < 8; ++r) {
                out[r] = reverse_bits(glyph[7 - r]);
            }
            break;
        }
        case ROTATE_270: {
            // rotated[r][c] = original[c][7 - r]
            for (int r = 0; r < 8; ++r) {
                uint8_t row = 0;
                for (int c = 0; c < 8; ++c) {
                    uint8_t bit = (glyph[c] >> (7 - r)) & 1;
                    row |= (bit << c);
                }
                out[r] = row;
            }
            break;
        }
    }
}

static void enable_backlight(void)
{
    gpio_config_t cfg = {};
    cfg.pin_bit_mask = 1ULL << static_cast<uint32_t>(LCD_BK_LIGHT_GPIO);
    cfg.mode = GPIO_MODE_OUTPUT;
    gpio_config(&cfg);
    gpio_set_level(LCD_BK_LIGHT_GPIO, 1);
}

static esp_lcd_panel_handle_t init_rgb_panel_internal(void)
{
    esp_lcd_panel_handle_t panel = NULL;
    esp_lcd_rgb_panel_config_t panel_config;
    memset(&panel_config, 0, sizeof(panel_config));
    panel_config.clk_src = LCD_CLK_SRC_DEFAULT;
    panel_config.timings.pclk_hz = 25 * 1000 * 1000;
    panel_config.timings.h_res = LCD_H_RES;
    panel_config.timings.v_res = LCD_V_RES;
    panel_config.timings.hsync_pulse_width = 4;
    panel_config.timings.hsync_back_porch = 8;
    panel_config.timings.hsync_front_porch = 8;
    panel_config.timings.vsync_pulse_width = 4;
    panel_config.timings.vsync_back_porch = 8;
    panel_config.timings.vsync_front_porch = 8;
    panel_config.timings.flags.pclk_active_neg = 1;
    panel_config.timings.flags.hsync_idle_low = 0;
    panel_config.timings.flags.vsync_idle_low = 0;
    panel_config.timings.flags.de_idle_high = 0;
    panel_config.data_width = 16;
    panel_config.hsync_gpio_num = 46;
    panel_config.vsync_gpio_num = 3;
    panel_config.de_gpio_num = 5;
    panel_config.pclk_gpio_num = 7;
    // Map data pins and control lines to the Waveshare ESP32-S3 Touch LCD 7" defaults.
    int data_pins[16] = {14,38,18,17,10,39,0,45,48,47,21,1,2,42,41,40};
    for (int i = 0; i < 16; ++i) {
        panel_config.data_gpio_nums[i] = data_pins[i];
    }
    panel_config.disp_gpio_num = -1;
    panel_config.flags.fb_in_psram = 1;
    panel_config.bounce_buffer_size_px = LCD_H_RES * 10;
    panel_config.psram_trans_align = 64;

    ESP_LOGI(TAG, "Creating RGB panel");
    if (esp_lcd_new_rgb_panel(&panel_config, &panel) != ESP_OK) {
        ESP_LOGE(TAG, "Failed to create RGB panel");
        return NULL;
    }
    esp_lcd_panel_reset(panel);
    esp_lcd_panel_init(panel);
    
    // Note: Not using swap_xy to avoid coordinate confusion
    // Screen is physically 800x480, we'll use it in landscape mode
    
    esp_lcd_panel_disp_on_off(panel, true);

    return panel;
}

static void fill_rect(esp_lcd_panel_handle_t panel, int x, int y, int w, int h, uint16_t color)
{
    if (!panel || !g_linebuf || h <= 0 || w <= 0) {
        return;
    }
    if (x < 0) {
        w += x;
        x = 0;
    }
    if (x + w > LCD_H_RES) {
        w = LCD_H_RES - x;
    }
    if (w <= 0) {
        return;
    }
    if (y < 0) {
        h += y;
        y = 0;
    }
    if (y + h > LCD_V_RES) {
        h = LCD_V_RES - y;
    }
    if (h <= 0) {
        return;
    }

    for (int yy = 0; yy < h; ++yy) {
        uint16_t* row = g_linebuf;
        for (int xx = 0; xx < w; ++xx) {
            row[xx] = color;
        }
        esp_err_t err = esp_lcd_panel_draw_bitmap(panel, x, y + yy, x + w, y + yy + 1, row);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "draw_bitmap failed: %s (row=%d)", esp_err_to_name(err), y + yy);
            break;
        }
    }
}

static inline uint16_t rgb565(uint8_t r, uint8_t g, uint8_t b)
{
    return (uint16_t)(((r & 0xF8) << 8) | ((g & 0xFC) << 3) | (b >> 3));
}

static const char* safe_text(const char* text)
{
    return text ? text : "-";
}

static int measure_text(const char* text)
{
    if (!text) {
        return 0;
    }
    int max_width = 0;
    int current = 0;
    const int step = char_step();
    for (const char* p = text; *p; ++p) {
        if (*p == '\n') {
            if (current > 0) {
                current -= CHAR_SPACING;
            }
            if (current > max_width) {
                max_width = current;
            }
            current = 0;
            continue;
        }
        current += step;
    }
    if (current > 0) {
        current -= CHAR_SPACING;
    }
    if (current > max_width) {
        max_width = current;
    }
    return max_width;
}

static void draw_char(esp_lcd_panel_handle_t panel, int x, int y, char c, uint16_t fg, uint16_t bg)
{
    if (!panel || !g_linebuf) {
        return;
    }
    if (c < 32 || c > 126) {
        c = '?';
    }
    const uint8_t* glyph = font8x8_basic[c - 32];
    uint8_t rotated[8];
    rotate_glyph(glyph, rotated, g_glyph_rotation);

    // Draw rotated (or original) glyph row-by-row
    int scale_x_draw = (g_glyph_rotation == ROTATE_90 || g_glyph_rotation == ROTATE_270) ? FONT_SCALE_Y : FONT_SCALE_X;
    int scale_y_draw = (g_glyph_rotation == ROTATE_90 || g_glyph_rotation == ROTATE_270) ? FONT_SCALE_X : FONT_SCALE_Y;
    const int char_width_pixels = 8 * scale_x_draw;
    const int char_height_pixels = 8 * scale_y_draw;
    for (int row = 0; row < 8; ++row) {
        for (int sy = 0; sy < scale_y_draw; ++sy) {
            uint16_t* line = g_linebuf;
            int idx = 0;
            for (int col = 7; col >= 0; --col) {
                const bool set = (rotated[row] & (1 << col)) != 0;
                for (int sx = 0; sx < scale_x_draw; ++sx) {
                    line[idx++] = set ? fg : bg;
                }
            }
            const int draw_y = y + row * scale_y_draw + sy;
            if (draw_y < 0 || draw_y >= LCD_V_RES) {
                continue;
            }
            esp_err_t err = esp_lcd_panel_draw_bitmap(panel,
                                                      x,
                                                      draw_y,
                                                      x + char_width_pixels,
                                                      draw_y + 1,
                                                      line);
            if (err != ESP_OK) {
                ESP_LOGE(TAG, "draw_char line write failed: %s", esp_err_to_name(err));
                return;
            }
        }
    }
}

static void draw_text(esp_lcd_panel_handle_t panel, int x, int y, int max_width, const char* text, uint16_t fg, uint16_t bg)
{
    if (!panel || !text) {
        return;
    }
    int cursor_x = x;
    int cursor_y = y;
    const int step = char_step();
    const int line_step = line_height();
    const int effective_width = (max_width > 0) ? max_width : (LCD_H_RES - x);
    const int char_w = (g_glyph_rotation == ROTATE_90 || g_glyph_rotation == ROTATE_270) ? GLYPH_HEIGHT : GLYPH_WIDTH;
    for (const char* p = text; *p; ++p) {
        if (*p == '\n') {
            cursor_x = x;
            cursor_y += line_step;
            continue;
        }
        if (effective_width > 0 && (cursor_x - x) + char_w > effective_width) {
            cursor_x = x;
            cursor_y += line_step;
        }
        draw_char(panel, cursor_x, cursor_y, *p, fg, bg);
        cursor_x += step;
    }
}

static void draw_status_badge(int x, int y, const char* text, uint16_t fg, uint16_t bg)
{
    if (!g_panel) {
        return;
    }
    const int padding = 12;
    const int badge_height = line_height() + padding;
    int width = measure_text(text) + padding * 2;
    if (width < 120) {
        width = 120;
    }
    fill_rect(g_panel, x, y, width, badge_height, bg);
    draw_text(g_panel, x + padding, y + (padding / 2), width - padding * 2, safe_text(text), fg, bg);
}

static void draw_card(int x, int y, int w, int h, uint16_t background, uint16_t border, uint16_t accent)
{
    if (!g_panel) {
        return;
    }
    fill_rect(g_panel, x, y, w, h, border);
    fill_rect(g_panel, x + 2, y + 2, w - 4, h - 4, background);
    if (accent) {
        fill_rect(g_panel, x + 2, y + 2, w - 4, 4, accent);
    }
}

static void format_duration(uint32_t seconds, char* out, size_t len)
{
    uint32_t hrs = seconds / 3600U;
    uint32_t mins = (seconds % 3600U) / 60U;
    uint32_t secs = seconds % 60U;
    snprintf(out, len, "%02lu:%02lu:%02lu",
             static_cast<unsigned long>(hrs),
             static_cast<unsigned long>(mins),
             static_cast<unsigned long>(secs));
}

static void format_bytes(size_t bytes, char* out, size_t len)
{
    const size_t KB = 1024U;
    const size_t MB = KB * 1024U;
    if (bytes >= MB) {
        size_t whole = bytes / MB;
        size_t rem = bytes % MB;
        size_t tenths = (rem * 10U + MB / 2U) / MB;
        if (tenths >= 10U) {
            whole += 1U;
            tenths = 0U;
        }
        snprintf(out, len, "%u.%u MB",
                 static_cast<unsigned>(whole),
                 static_cast<unsigned>(tenths));
    } else if (bytes >= KB) {
        size_t rounded = (bytes + KB / 2U) / KB;
        snprintf(out, len, "%u KB", static_cast<unsigned>(rounded));
    } else {
        snprintf(out, len, "%u B", static_cast<unsigned>(bytes));
    }
}

void gui_render_dashboard(const gui_dashboard_data_t* data)
{
    if (!g_panel || !data) {
        return;
    }

    const uint16_t bg = rgb565(12, 13, 18);
    const uint16_t header_bg = rgb565(28, 30, 38);
    const uint16_t card_a = rgb565(24, 26, 36);
    const uint16_t card_b = rgb565(28, 30, 42);
    const uint16_t border = rgb565(40, 42, 54);
    const uint16_t accent = rgb565(0, 200, 120);
    const uint16_t accent_alt = rgb565(80, 120, 240);
    const uint16_t text_primary = rgb565(240, 240, 240);
    const uint16_t text_secondary = rgb565(170, 180, 194);
    const uint16_t badge_bg = rgb565(18, 85, 60);

    fill_rect(g_panel, 0, 0, LCD_H_RES, LCD_V_RES, bg);
    fill_rect(g_panel, 0, 0, LCD_H_RES, 72, header_bg);
    draw_text(g_panel, 24, 20, 0, "System Dashboard", text_primary, header_bg);

    const char* status_text = safe_text(data->status_text);
    int badge_width = measure_text(status_text) + 24;
    if (badge_width < 140) {
        badge_width = 140;
    }
    draw_status_badge(LCD_H_RES - badge_width - 24, 20, status_text, rgb565(255, 255, 255), badge_bg);

    const int margin = 16;
    const int header_height = 72;
    const int card_spacing = 16;
    const int card_width = (LCD_H_RES - margin * 2 - card_spacing) / 2;
    const int top_card_height = 160;
    const int bottom_card_height = LCD_V_RES - header_height - margin * 3 - top_card_height;

    const int left_x = margin;
    const int right_x = margin + card_width + card_spacing;
    const int top_y = header_height + margin;
    const int bottom_y = top_y + top_card_height + card_spacing;

    draw_card(left_x, top_y, card_width, top_card_height, card_a, border, accent);
    const int left_inner_x = left_x + 20;
    const int left_inner_y = top_y + 26;
    const int left_inner_w = card_width - 40;
    draw_text(g_panel, left_inner_x, left_inner_y, left_inner_w, "System Status", text_primary, card_a);

    char buffer[128];
    snprintf(buffer, sizeof(buffer), "Mode: %s", safe_text(data->mode_text));
    draw_text(g_panel, left_inner_x, left_inner_y + line_height(), left_inner_w, buffer, text_secondary, card_a);

    char uptime_text[32];
    format_duration(data->uptime_seconds, uptime_text, sizeof(uptime_text));
    snprintf(buffer, sizeof(buffer), "Uptime: %s", uptime_text);
    draw_text(g_panel, left_inner_x, left_inner_y + 2 * line_height(), left_inner_w, buffer, text_secondary, card_a);

    snprintf(buffer, sizeof(buffer), "Status: %s", status_text);
    draw_text(g_panel, left_inner_x, left_inner_y + 3 * line_height(), left_inner_w, buffer, text_secondary, card_a);

    draw_card(right_x, top_y, card_width, top_card_height, card_b, border, accent_alt);
    const int right_inner_x = right_x + 20;
    const int right_inner_y = top_y + 26;
    const int right_inner_w = card_width - 40;
    draw_text(g_panel, right_inner_x, right_inner_y, right_inner_w, "Memory Pools", text_primary, card_b);

    char heap_free[32];
    char heap_total[32];
    format_bytes(data->heap_free_bytes, heap_free, sizeof(heap_free));
    format_bytes(data->heap_total_bytes, heap_total, sizeof(heap_total));
    snprintf(buffer, sizeof(buffer), "Internal: %s free / %s total", heap_free, heap_total);
    draw_text(g_panel, right_inner_x, right_inner_y + line_height(), right_inner_w, buffer, text_secondary, card_b);

    if (data->psram_total_bytes > 0) {
        char psram_free[32];
        char psram_total[32];
        format_bytes(data->psram_free_bytes, psram_free, sizeof(psram_free));
        format_bytes(data->psram_total_bytes, psram_total, sizeof(psram_total));
        uint32_t used_pct = 0;
        if (data->psram_total_bytes > 0) {
            uint64_t used = data->psram_total_bytes - data->psram_free_bytes;
            used_pct = static_cast<uint32_t>((used * 100U) / (data->psram_total_bytes ? data->psram_total_bytes : 1));
        }
    snprintf(buffer, sizeof(buffer), "PSRAM: %s free of %s (%u%% used)", psram_free, psram_total, static_cast<unsigned>(used_pct));
    } else {
        snprintf(buffer, sizeof(buffer), "PSRAM: not detected");
    }
    draw_text(g_panel, right_inner_x, right_inner_y + 2 * line_height(), right_inner_w, buffer, text_secondary, card_b);

    draw_card(left_x, bottom_y, card_width, bottom_card_height, card_b, border, accent_alt);
    const int bottom_left_x = left_x + 20;
    const int bottom_left_y = bottom_y + 26;
    const int bottom_left_w = card_width - 40;
    draw_text(g_panel, bottom_left_x, bottom_left_y, bottom_left_w, "Connectivity", text_primary, card_b);
    draw_text(g_panel, bottom_left_x, bottom_left_y + line_height(), bottom_left_w, safe_text(data->connection_text), text_secondary, card_b);

    draw_card(right_x, bottom_y, card_width, bottom_card_height, card_a, border, accent);
    const int bottom_right_x = right_x + 20;
    const int bottom_right_y = bottom_y + 26;
    const int bottom_right_w = card_width - 40;
    draw_text(g_panel, bottom_right_x, bottom_right_y, bottom_right_w, "Next Steps", text_primary, card_a);
    draw_text(g_panel, bottom_right_x, bottom_right_y + line_height(), bottom_right_w, safe_text(data->action_text), text_secondary, card_a);
}

void gui_render_test_pattern(void)
{
    if (!g_panel || !g_linebuf) {
        return;
    }

    ESP_LOGI(TAG, "Rendering LCD test pattern");

    const int top_height = LCD_V_RES / 2;
    const int bottom_height = LCD_V_RES - top_height;

    struct rgb_triplet {
        uint8_t r;
        uint8_t g;
        uint8_t b;
    };

    static const rgb_triplet color_bars[] = {
        {255, 255, 255}, // White
        {255, 255,   0}, // Yellow
        {  0, 255, 255}, // Cyan
        {  0, 255,   0}, // Green
        {255,   0, 255}, // Magenta
        {255,   0,   0}, // Red
        {  0,   0, 255}, // Blue
        {  0,   0,   0}, // Black
    };

    const int bar_count = static_cast<int>(sizeof(color_bars) / sizeof(color_bars[0]));
    const int bar_width = LCD_H_RES / bar_count;

    fill_rect(g_panel, 0, 0, LCD_H_RES, LCD_V_RES, rgb565(0, 0, 0));

    int x = 0;
    for (int i = 0; i < bar_count; ++i) {
        const int width = (i == bar_count - 1) ? (LCD_H_RES - x) : bar_width;
        const rgb_triplet& triplet = color_bars[i];
        fill_rect(g_panel, x, 0, width, top_height, rgb565(triplet.r, triplet.g, triplet.b));
        x += width;
    }

    const int gradient_y = top_height;
    const int denom = (LCD_H_RES > 1) ? (LCD_H_RES - 1) : 1;
    for (int row = 0; row < bottom_height; ++row) {
        for (int col = 0; col < LCD_H_RES; ++col) {
            uint8_t level = static_cast<uint8_t>((static_cast<uint32_t>(col) * 255U) / static_cast<uint32_t>(denom));
            g_linebuf[col] = rgb565(level, level, level);
        }
        esp_err_t err = esp_lcd_panel_draw_bitmap(g_panel,
                                                  0,
                                                  gradient_y + row,
                                                  LCD_H_RES,
                                                  gradient_y + row + 1,
                                                  g_linebuf);
        if (err != ESP_OK) {
            ESP_LOGE(TAG, "test pattern gradient write failed: %s", esp_err_to_name(err));
            break;
        }
    }

    const uint16_t border_color = rgb565(255, 255, 255);
    fill_rect(g_panel, 0, 0, LCD_H_RES, 2, border_color);
    fill_rect(g_panel, 0, LCD_V_RES - 2, LCD_H_RES, 2, border_color);
    fill_rect(g_panel, 0, 0, 2, LCD_V_RES, border_color);
    fill_rect(g_panel, LCD_H_RES - 2, 0, 2, LCD_V_RES, border_color);
}

void gui_render_ui(const gui_translator_state_t* state, const gui_ui_state_t* ui)
{
    if (!g_panel || !g_linebuf || !state) {
        return;
    }

    // Disable display output during rendering to prevent flicker
    // The RGB panel will buffer changes and show them all at once
    
    // Modern dark theme with gradient-like effect
    const uint16_t bg_dark = rgb565(240, 240, 240);
    const uint16_t bg_medium = rgb565(28, 28, 35);
    const uint16_t header_bg = rgb565(255, 255, 255);
    const uint16_t accent_blue = rgb565(70, 130, 220);
    const uint16_t text_primary = rgb565(0, 0, 0);
    const uint16_t text_secondary = rgb565(100, 100, 100);
    const uint16_t status_ok = rgb565(50, 220, 120);
    const uint16_t status_warn = rgb565(255, 180, 50);
    const uint16_t status_err = rgb565(255, 80, 80);
    const uint16_t msg_high = rgb565(100, 220, 130);
    const uint16_t msg_medium = rgb565(200, 200, 100);
    const uint16_t msg_low = rgb565(255, 140, 140);
    const uint16_t card_a = rgb565(255, 255, 255);
    const uint16_t card_b = rgb565(248, 248, 248);
    const uint16_t border = rgb565(200, 200, 200);
    const uint16_t accent = rgb565(0, 200, 120);
    const uint16_t accent_alt = rgb565(80, 120, 240);

    // Clear with dark background
    fill_rect(g_panel, 0, 0, LCD_H_RES, LCD_V_RES, bg_dark);

    // Header bar with rounded bottom effect (larger, more prominent)
    const int header_height = 60;
    fill_rect(g_panel, 0, 0, LCD_H_RES, header_height, header_bg);
    
    // Accent line under header
    fill_rect(g_panel, 0, header_height, LCD_H_RES, 3, accent_blue);
    
    // Title
    draw_text(g_panel, 15, 8, 300, "AURA TRANSLATOR", text_primary, header_bg);
    
    // Status line with better formatting
    char status_line[128];
    snprintf(status_line, sizeof(status_line), "Messages: %lu   Errors: %lu   Uptime: %lus",
             (unsigned long)state->message_count,
             (unsigned long)state->error_count,
             (unsigned long)state->uptime_seconds);
    draw_text(g_panel, 15, 35, LCD_H_RES - 140, status_line, text_secondary, header_bg);

    // Modern status indicator (rounded pill shape)
    uint16_t status_color = status_err;
    const char* status_text = "ERROR";
    if (strcmp(state->connection_status, "RECEIVING") == 0) {
        status_color = status_ok;
        status_text = "LIVE";
    } else if (strcmp(state->connection_status, "WAITING") == 0) {
        status_color = status_warn;
        status_text = "READY";
    }
    
    // Status pill background
    const int pill_x = LCD_H_RES - 110;
    const int pill_y = 18;
    const int pill_w = 95;
    const int pill_h = 28;
    fill_rect(g_panel, pill_x, pill_y, pill_w, pill_h, status_color);
    
    // Status text centered in pill
    draw_text(g_panel, pill_x + 20, pill_y + 5, pill_w - 20, status_text, rgb565(0, 0, 0), status_color);

    // Tab bar
    const int tab_y = header_height + 6;
    const int tab_height = 28;
    const int tab_padding = 12;
    const char* tabs[] = {"Inbox", "Escalations", "Settings"};
    for (int t = 0; t < 3; ++t) {
        int tx = 15 + t * 120;
        int tw = 110;
        uint16_t tb = (ui && ui->active_tab == t) ? accent_blue : rgb565(40, 40, 48);
        draw_text(g_panel, tx + 10, tab_y + 4, tw - 20, tabs[t], text_primary, tb);
        // draw border
        fill_rect(g_panel, tx, tab_y, tw, tab_height, tb);
    }

    // Message log area with subtle background
    const int log_start_y = header_height + tab_height + 20;
    const int log_height = LCD_V_RES - log_start_y - 10;
    fill_rect(g_panel, 10, log_start_y, LCD_H_RES - 20, log_height, bg_medium);
    
    const int msg_line_height = 32;  // More spacing for readability
    const int max_visible = (log_height - 20) / msg_line_height;

    // Display messages with alternating background shading
    // choose which list to show
    const gui_decoded_message_t* messages = state->messages;
    int msg_count = state->num_messages;
    if (ui && ui->active_tab == GUI_TAB_ESCALATIONS) {
        messages = state->escalations;
        msg_count = state->num_escalations;
    }
    int start_idx = 0;
    if (ui) {
        if ((int)ui->list_scroll_index > 0) {
            start_idx = (int)ui->list_scroll_index;
        } else if ((int)msg_count > max_visible) {
            start_idx = (int)msg_count - max_visible;
        }
    } else {
        if ((int)msg_count > max_visible) {
            start_idx = (int)msg_count - max_visible;
        }
    }
    int y = log_start_y + 10;

    for (int i = start_idx; i < (int)msg_count && y < LCD_V_RES - 20; ++i) {
        const gui_decoded_message_t* msg = &messages[i];
        
        // Subtle alternating row background
        if ((i - start_idx) % 2 == 0) {
            fill_rect(g_panel, 15, y - 2, LCD_H_RES - 30, msg_line_height, rgb565(250, 250, 250));
        }

    // (rotation functions moved to global scope)

        // Selection highlight (when user selects a message)
        if (ui && ui->selected_index == (size_t)i) {
            // Draw a faint selection color over the row
            fill_rect(g_panel, 15, y - 2, LCD_H_RES - 30, msg_line_height, rgb565(200, 220, 255));
        }
        
        // Color code by confidence with modern colors
        uint16_t msg_color = text_primary;
        if (msg->confidence == 3) {
            msg_color = msg_high;
        } else if (msg->confidence == 2) {
            msg_color = msg_high;
        } else if (msg->confidence == 1) {
            msg_color = msg_medium;
        } else {
            msg_color = msg_low;
        }

        // Risk indicator as colored dot
        if (msg->risk_flag) {
            fill_rect(g_panel, 20, y + 8, 8, 8, status_err);
        }

        // Timestamp in secondary color
        char timestamp_part[40];
        snprintf(timestamp_part, sizeof(timestamp_part), "%s", msg->timestamp);
        draw_text(g_panel, 35, y, 100, timestamp_part, text_secondary, rgb565(0, 0, 0));
        
        // Message text
        draw_text(g_panel, 130, y, LCD_H_RES - 150, msg->text, msg_color, rgb565(0, 0, 0));
        
        y += msg_line_height;
    }

    // Bottom border accent
    fill_rect(g_panel, 0, LCD_V_RES - 3, LCD_H_RES, 3, accent_blue);
    
    // If a message is selected, draw a detail overlay on the right
    if (ui && ui->selected_index < (size_t)msg_count) {
        const gui_decoded_message_t* sel = &messages[ui->selected_index];
        int detail_x = LCD_H_RES - 360;
        int detail_w = 340;
        int detail_y = log_start_y;
        int detail_h = LCD_V_RES - detail_y - 20;
        // Ensure card color variables are defined for this function scope
        const uint16_t card_b = bg_medium;
        const uint16_t border = rgb565(40, 42, 54);
        const uint16_t accent = accent_blue;
        draw_card(detail_x - 10, detail_y - 8, detail_w + 20, detail_h + 16, card_b, border, accent);
        draw_text(g_panel, detail_x, detail_y, detail_w, "Message Detail", text_primary, card_b);
        draw_text(g_panel, detail_x, detail_y + line_height(), detail_w, sel->text, text_primary, card_b);
        draw_text(g_panel, detail_x, detail_y + 3 * line_height(), detail_w, sel->timestamp, text_secondary, card_b);
        // action buttons
        draw_card(detail_x + 20, detail_y + detail_h - 84, 140, 48, accent_blue, rgb565(255,255,255), accent_blue);
        draw_text(g_panel, detail_x + 35, detail_y + detail_h - 76, 120, "VERIFY", rgb565(0,0,0), accent_blue);
        draw_card(detail_x + 180, detail_y + detail_h - 84, 140, 48, status_err, rgb565(255,255,255), status_err);
        draw_text(g_panel, detail_x + 210, detail_y + detail_h - 76, 120, "ESCALATE", rgb565(0,0,0), status_err);
    }
    // If Settings tab is active, show rotation option in the right-side card
    if (ui && ui->active_tab == GUI_TAB_SETTINGS) {
        int detail_x = LCD_H_RES - 360;
        int detail_w = 340;
        int detail_y = log_start_y;
        int detail_h = LCD_V_RES - detail_y - 20;
        draw_card(detail_x - 10, detail_y - 8, detail_w + 20, detail_h + 16, card_b, border, accent);
        draw_text(g_panel, detail_x, detail_y, detail_w, "Settings", text_primary, card_b);
        // show rotation value
        char rottext[64];
        switch (g_glyph_rotation) {
            case ROTATE_0: snprintf(rottext, sizeof(rottext), "Rotation: 0°"); break;
            case ROTATE_90: snprintf(rottext, sizeof(rottext), "Rotation: 90°"); break;
            case ROTATE_180: snprintf(rottext, sizeof(rottext), "Rotation: 180°"); break;
            case ROTATE_270: snprintf(rottext, sizeof(rottext), "Rotation: 270°"); break;
        }
        draw_text(g_panel, detail_x, detail_y + 2 * line_height(), detail_w, rottext, text_secondary, card_b);
        // hint to tap to cycle
        draw_card(detail_x + 20, detail_y + detail_h - 84, 300, 48, accent_blue, rgb565(255,255,255), accent_blue);
        draw_text(g_panel, detail_x + 30, detail_y + detail_h - 76, 260, "Tap here to cycle rotation", rgb565(0,0,0), accent_blue);
        // show axis toggles in smaller cards above the rotate hint
        int toggle_w = 100;
        int toggle_h = 48;
        int tx = detail_x + 20;
        int ty = detail_y + detail_h - 84 - 64;
        // Swap XY
        draw_card(tx, ty, toggle_w, toggle_h, gui_get_swapxy() ? accent_blue : card_b, border, gui_get_swapxy() ? accent_blue : 0);
        draw_text(g_panel, tx + 8, ty + 12, toggle_w - 16, gui_get_swapxy() ? "Swap XY: ON" : "Swap XY: OFF", rgb565(0,0,0), gui_get_swapxy() ? accent_blue : card_b);
        // Flip X
        tx += toggle_w + 12;
        draw_card(tx, ty, toggle_w, toggle_h, gui_get_flipx() ? accent_blue : card_b, border, gui_get_flipx() ? accent_blue : 0);
        draw_text(g_panel, tx + 8, ty + 12, toggle_w - 16, gui_get_flipx() ? "Flip X: ON" : "Flip X: OFF", rgb565(0,0,0), gui_get_flipx() ? accent_blue : card_b);
        // Flip Y
        tx += toggle_w + 12;
        draw_card(tx, ty, toggle_w, toggle_h, gui_get_flipy() ? accent_blue : card_b, border, gui_get_flipy() ? accent_blue : 0);
        draw_text(g_panel, tx + 8, ty + 12, toggle_w - 16, gui_get_flipy() ? "Flip Y: ON" : "Flip Y: OFF", rgb565(0,0,0), gui_get_flipy() ? accent_blue : card_b);
    }
}

esp_lcd_panel_handle_t gui_init(void)
{
    g_panel = init_rgb_panel_internal();
    if (!g_panel) {
        return NULL;
    }
    enable_backlight();

    g_linebuf = static_cast<uint16_t*>(heap_caps_calloc(LCD_H_RES, sizeof(uint16_t), MALLOC_CAP_DMA | MALLOC_CAP_INTERNAL));
    if (!g_linebuf) {
        g_linebuf = static_cast<uint16_t*>(heap_caps_calloc(LCD_H_RES, sizeof(uint16_t), MALLOC_CAP_INTERNAL));
    }
    if (!g_linebuf) {
        ESP_LOGE(TAG, "Failed to allocate line buffer");
        return g_panel;
    }

    fill_rect(g_panel, 0, 0, LCD_H_RES, LCD_V_RES, rgb565(0, 0, 0));
    ESP_LOGI(TAG, "Dashboard surface ready");
    // Log the glyph rotation mode so we can verify orientation on boot
    switch (g_glyph_rotation) {
        case ROTATE_0: ESP_LOGI(TAG, "Glyph rotation mode: ROTATE_0"); break;
        case ROTATE_90: ESP_LOGI(TAG, "Glyph rotation mode: ROTATE_90"); break;
        case ROTATE_180: ESP_LOGI(TAG, "Glyph rotation mode: ROTATE_180"); break;
        case ROTATE_270: ESP_LOGI(TAG, "Glyph rotation mode: ROTATE_270"); break;
    }
    return g_panel;
}

// Runtime rotation getters/setters
void gui_set_rotation(GlyphRotationMode rotation)
{
    g_glyph_rotation = rotation;
    ESP_LOGI(TAG, "Set glyph rotation to %d", (int)rotation);
}

GlyphRotationMode gui_get_rotation(void)
{
    return g_glyph_rotation;
}

void gui_set_swapxy(bool swap_xy)
{
    g_swap_xy = swap_xy;
    ESP_LOGI(TAG, "Set swap_xy=%d", (int)swap_xy);
}

bool gui_get_swapxy(void)
{
    return g_swap_xy;
}

void gui_set_flipx(bool flip_x)
{
    g_flip_x = flip_x;
    ESP_LOGI(TAG, "Set flip_x=%d", (int)flip_x);
}

bool gui_get_flipx(void)
{
    return g_flip_x;
}

void gui_set_flipy(bool flip_y)
{
    g_flip_y = flip_y;
    ESP_LOGI(TAG, "Set flip_y=%d", (int)flip_y);
}

bool gui_get_flipy(void)
{
    return g_flip_y;
}
