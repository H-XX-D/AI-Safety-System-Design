#include <stdio.h>
#include <stdint.h>
#include <string.h>

#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/uart.h"
#include "driver/gpio.h"
#include "driver/sdmmc_host.h"
#include "esp_heap_caps.h"
#include "esp_log.h"
#include "esp_system.h"
#include "esp_timer.h"
#include "nvs_flash.h"

#include "gui.h"
#include "esp_vfs_fat.h"
#include "sdmmc_cmd.h"
#include <dirent.h>
#include <sys/stat.h>

#include <sys/unistd.h>
#include "bitpacked_decoder.h"
#include "ft5x06.h"
#include "driver/touch_pad.h"
#include "esp_err.h"

static const char* TAG = "translator";

// Configuration
static constexpr bool kEnableTestPattern = false;  // Set to false for translator mode
static constexpr int kMaxMessages = 50;  // Ring buffer size
static constexpr uart_port_t kUartPort = UART_NUM_0;
static constexpr int kUartBaudRate = 115200;
static constexpr int kUartRxBufferSize = 2048;

// Message ring buffer
static gui_decoded_message_t g_message_buffer[kMaxMessages];
static int g_message_head = 0;
static int g_message_count = 0;
static uint32_t g_total_messages = 0;
static uint32_t g_error_count = 0;

// Decoder instance
static BitPackedDecoder g_decoder;

// UI state
static gui_ui_state_t g_ui_state = { .active_tab = GUI_TAB_INBOX, .selected_index = 0, .detail_scroll_lines = 0, .list_scroll_index = 0 };
static portMUX_TYPE g_ui_mux = portMUX_INITIALIZER_UNLOCKED;
// Incremented whenever UI state changes to trigger a redraw
static volatile uint32_t g_ui_change_counter = 0;

// Touch pad mapping: change these pad numbers if hardware pads are wired differently
static const touch_pad_t TOUCH_PAD_UP = TOUCH_PAD_NUM0;
static const touch_pad_t TOUCH_PAD_DOWN = TOUCH_PAD_NUM1;
static const touch_pad_t TOUCH_PAD_SELECT = TOUCH_PAD_NUM2;
static const touch_pad_t TOUCH_PAD_VERIFY = TOUCH_PAD_NUM3;
static const touch_pad_t TOUCH_PAD_ESCALATE = TOUCH_PAD_NUM4;

// Escalation buffer (quarantine)
static gui_decoded_message_t g_escalation_buffer[kMaxMessages];
static int g_escalation_count = 0;

static void add_message(const char* text, const char* timestamp, uint8_t confidence, uint8_t risk, uint8_t msg_type, const char* file_path = NULL)
{
    gui_decoded_message_t* msg = &g_message_buffer[g_message_head];
    snprintf(msg->text, sizeof(msg->text), "%s", text);
    snprintf(msg->timestamp, sizeof(msg->timestamp), "%s", timestamp);
    msg->confidence = confidence;
    msg->risk_flag = risk;
    msg->message_type = msg_type;
    msg->sequence = g_total_messages;
    if (file_path && strlen(file_path) > 0) {
        snprintf(msg->file_path, sizeof(msg->file_path), "%s", file_path);
    } else {
        msg->file_path[0] = '\0';
    }

    g_message_head = (g_message_head + 1) % kMaxMessages;
    if (g_message_count < kMaxMessages) {
        g_message_count++;
    }
    g_total_messages++;
}

// Copy messages from ring buffer to a contiguous buffer for display/UI
static gui_decoded_message_t g_display_buffer[kMaxMessages];
static const gui_decoded_message_t* get_display_messages(int* out_count)
{
    int count = g_message_count;
    int head = g_message_head;
    int start = (head - count + kMaxMessages) % kMaxMessages;
    for (int i = 0; i < count; ++i) {
        int idx = (start + i) % kMaxMessages;
        g_display_buffer[i] = g_message_buffer[idx];
    }
    *out_count = count;
    return g_display_buffer;
}

static bool remove_message_at_index(int pos)
{
    if (pos < 0 || pos >= g_message_count) return false;
    int count = g_message_count;
    int head = g_message_head;
    int start = (head - count + kMaxMessages) % kMaxMessages;
    // Physical index of element to remove
    int idx = (start + pos) % kMaxMessages;
    // Shift elements left in the circular buffer
    for (int i = 0; i < count - 1; ++i) {
        int from_idx = (idx + 1 + i) % kMaxMessages;
        int to_idx = (idx + i) % kMaxMessages;
        g_message_buffer[to_idx] = g_message_buffer[from_idx];
    }
    // Adjust head and count
    g_message_head = (g_message_head - 1 + kMaxMessages) % kMaxMessages;
    g_message_count--;
    return true;
}

// Remove and shift an element from the escalation buffer
static bool remove_escalation_at_index(int pos)
{
    if (pos < 0 || pos >= g_escalation_count) return false;
    for (int i = pos; i < g_escalation_count - 1; ++i) {
        g_escalation_buffer[i] = g_escalation_buffer[i + 1];
    }
    g_escalation_count--;
    return true;
}

static void process_uart_data(const uint8_t* data, size_t len)
{
    // Get timestamp
    char timestamp[32];
    uint32_t uptime = (uint32_t)(esp_timer_get_time() / 1000000ULL);
    snprintf(timestamp, sizeof(timestamp), "%02lu:%02lu:%02lu",
             (uptime / 3600) % 24, (uptime / 60) % 60, uptime % 60);

    char decoded[256];
    bool success = false;

    // Try secure format first (6 bytes)
    if (len == 6 && data[0] == BitPackedDecoder::SECURE_METHOD_BYTE) {
        success = g_decoder.decompress_secure(data, len, decoded, sizeof(decoded));
        if (success) {
            // Extract metadata from control byte
            uint8_t control = data[1];
            uint8_t confidence = (control >> 1) & 0b11;
            uint8_t risk = control & 0b1;
            uint8_t msg_type = (control >> 5) & 0b111;
                        add_message(decoded, timestamp, confidence, risk, msg_type, NULL);
            ESP_LOGI(TAG, "Decoded secure: %s", decoded);
        } else {
            g_error_count++;
            ESP_LOGW(TAG, "CRC check failed for secure message");
        }
    }
    // Try standard format (4 bytes)
    else if (len == 4 && data[0] == BitPackedDecoder::METHOD_BYTE) {
        success = g_decoder.decompress(data, len, decoded, sizeof(decoded));
        if (success) {
            uint8_t control = data[1];
            uint8_t confidence = (control >> 1) & 0b11;
            uint8_t risk = control & 0b1;
            uint8_t msg_type = (control >> 5) & 0b111;
                add_message(decoded, timestamp, confidence, risk, msg_type, NULL);
            ESP_LOGI(TAG, "Decoded: %s", decoded);
        } else {
            g_error_count++;
            ESP_LOGE(TAG, "Failed to decode standard message");
        }
    }
    else {
        g_error_count++;
        ESP_LOGE(TAG, "Invalid message format: len=%d, byte0=0x%02X", len, data[0]);
    }
}

static void uart_receive_task(void* arg)
{
    (void)arg;
    uint8_t* rx_buffer = (uint8_t*)malloc(kUartRxBufferSize);
    if (!rx_buffer) {
        ESP_LOGE(TAG, "Failed to allocate UART RX buffer");
        vTaskDelete(NULL);
        return;
    }

    ESP_LOGI(TAG, "UART receive task started");

    while (true) {
        int len = uart_read_bytes(kUartPort, rx_buffer, kUartRxBufferSize, pdMS_TO_TICKS(100));
        if (len > 0) {
            ESP_LOGD(TAG, "Received %d bytes", len);
            // Process messages (4 or 6 bytes each)
            int offset = 0;
            while (offset < len) {
                if (len - offset >= 6 && rx_buffer[offset] == BitPackedDecoder::SECURE_METHOD_BYTE) {
                    process_uart_data(&rx_buffer[offset], 6);
                    offset += 6;
                } else if (len - offset >= 4 && rx_buffer[offset] == BitPackedDecoder::METHOD_BYTE) {
                    process_uart_data(&rx_buffer[offset], 4);
                    offset += 4;
                } else {
                    // Skip invalid byte
                    ESP_LOGW(TAG, "Skipping invalid byte: 0x%02X", rx_buffer[offset]);
                    offset++;
                    g_error_count++;
                }
            }
        }
    }
}

// Helper to write a log line to a file on the SD card (append)
static bool sd_append_log(const char* path, const char* line)
{
    FILE* f = fopen(path, "a");
    if (!f) {
        ESP_LOGE(TAG, "Failed to open log file %s", path);
        return false;
    }
    fprintf(f, "%s\n", line);
    fclose(f);
    return true;
}

// Verify message at index: delete underlying SD file and log verification
static void ui_verify_selected_message(void)
{
    // Snapshot the selected message under lock so we operate on stable data.
    gui_decoded_message_t msg_copy = {};
    size_t sel_idx = 0;
    gui_tab_t active_tab = GUI_TAB_INBOX;
    portENTER_CRITICAL(&g_ui_mux);
    active_tab = g_ui_state.active_tab;
    if (g_ui_state.selected_index >= (size_t)((active_tab == GUI_TAB_ESCALATIONS) ? g_escalation_count : g_message_count)) {
        portEXIT_CRITICAL(&g_ui_mux);
        return;
    }
    sel_idx = g_ui_state.selected_index;
    if (active_tab == GUI_TAB_ESCALATIONS) {
        msg_copy = g_escalation_buffer[sel_idx];
    } else {
        msg_copy = g_message_buffer[sel_idx];
    }
    portEXIT_CRITICAL(&g_ui_mux);

    if (strlen(msg_copy.file_path) == 0) {
        ESP_LOGW(TAG, "No file associated with message, just removing from inbox");
        portENTER_CRITICAL(&g_ui_mux);
        if (active_tab == GUI_TAB_ESCALATIONS) {
            remove_escalation_at_index((int)sel_idx);
        } else {
            remove_message_at_index((int)sel_idx);
        }
        // Adjust selection index if needed
        if (g_message_count == 0) {
            g_ui_state.selected_index = 0;
        } else if (g_ui_state.selected_index >= (size_t)g_message_count) {
            g_ui_state.selected_index = (size_t)g_message_count - 1;
        }
        g_ui_change_counter++;
        portEXIT_CRITICAL(&g_ui_mux);
        return;
    }

    char logline[1024];
    snprintf(logline, sizeof(logline), "VERIFIED %.*s: seq=%lu text=%.*s", (int)sizeof(msg_copy.file_path) - 1, msg_copy.file_path, (unsigned long)msg_copy.sequence, (int)sizeof(msg_copy.text) - 1, msg_copy.text);
    sd_append_log("/sdcard/logs/verified.log", logline);
    int rc = unlink(msg_copy.file_path);
    if (rc != 0) {
        ESP_LOGE(TAG, "Failed to delete file %s: %d", msg_copy.file_path, rc);
    }

    portENTER_CRITICAL(&g_ui_mux);
    if (active_tab == GUI_TAB_ESCALATIONS) {
        remove_escalation_at_index((int)sel_idx);
    } else {
        remove_message_at_index((int)sel_idx);
    }
    // Ensure selected_index stays in range for current tab
    if ((active_tab == GUI_TAB_ESCALATIONS && g_escalation_count == 0) || (active_tab != GUI_TAB_ESCALATIONS && g_message_count == 0)) {
        g_ui_state.selected_index = 0;
    } else {
        size_t cur_count = (active_tab == GUI_TAB_ESCALATIONS) ? g_escalation_count : g_message_count;
        if (g_ui_state.selected_index >= cur_count) {
            g_ui_state.selected_index = (cur_count > 0) ? (cur_count - 1) : 0;
        }
    }
    g_ui_change_counter++;
    portEXIT_CRITICAL(&g_ui_mux);
}

// Escalate selected message: move file to /sdcard/escalations and log
static void ui_escalate_selected_message(void)
{
    char oldpath[128] = {0};
    char text_copy[256] = {0};
    uint32_t seq = 0;

    // Only escalate from Inbox; Escalations tab should not call this.
    // Snapshot the selected message and remove it under lock.
    portENTER_CRITICAL(&g_ui_mux);
    if (g_ui_state.active_tab != GUI_TAB_INBOX) {
        ESP_LOGW(TAG, "Escalate pressed while not on Inbox tab; ignoring");
        portEXIT_CRITICAL(&g_ui_mux);
        return;
    }
    if ((int)g_ui_state.selected_index < 0 || g_ui_state.selected_index >= (size_t)g_message_count) {
        // Nothing selected
        portEXIT_CRITICAL(&g_ui_mux);
        return;
    }
    const gui_decoded_message_t mcopy = g_message_buffer[g_ui_state.selected_index];
    strncpy(oldpath, mcopy.file_path, sizeof(oldpath) - 1);
    strncpy(text_copy, mcopy.text, sizeof(text_copy) - 1);
    seq = mcopy.sequence;
    // remove from inbox and adjust selection
    remove_message_at_index((int)g_ui_state.selected_index);
    if (g_message_count == 0) {
        g_ui_state.selected_index = 0;
    } else if (g_ui_state.selected_index >= (size_t)g_message_count) {
        g_ui_state.selected_index = (size_t)g_message_count - 1;
    }
    g_ui_change_counter++;
    portEXIT_CRITICAL(&g_ui_mux);
    if (strlen(oldpath) == 0) {
        ESP_LOGW(TAG, "No file associated with message, nothing to escalate");
        return;
    }
    char newpath[256];
    const char* basename = strrchr(oldpath, '/');
    if (!basename) basename = oldpath; else basename++;
    int max_basename_len = (int)(sizeof(newpath) - strlen("/sdcard/escalations/") - 1);
    if (max_basename_len < 0) max_basename_len = 0;
    snprintf(newpath, sizeof(newpath), "/sdcard/escalations/%.*s", max_basename_len, basename);
    int rc = rename(oldpath, newpath);
    if (rc != 0) {
        ESP_LOGE(TAG, "Failed to move file to escalations %s => %s: %d", oldpath, newpath, rc);
    } else {
        char logline[1024];
        snprintf(logline, sizeof(logline), "ESCALATED %.*s => %.*s: seq=%lu text=%.*s", (int)sizeof(oldpath) - 1, oldpath, (int)sizeof(newpath) - 1, newpath, (unsigned long)seq, (int)sizeof(text_copy) - 1, text_copy);
        sd_append_log("/sdcard/logs/escalations.log", logline);
        // add to escalation buffer (copy of original message)
        if (g_escalation_count < kMaxMessages) {
            gui_decoded_message_t esc = {};
            strncpy(esc.text, text_copy, sizeof(esc.text) - 1);
            esc.sequence = seq;
            strncpy(esc.file_path, newpath, sizeof(esc.file_path) - 1);
            esc.confidence = 0; esc.risk_flag = 0; esc.message_type = 0;
            g_escalation_buffer[g_escalation_count++] = esc;
        }
    }
}

// SD card mounting and scanning
static esp_err_t mount_sdcard(void)
{
    esp_err_t ret;
    sdmmc_card_t* card = NULL;
    const char* mount_point = "/sdcard";
    sdmmc_host_t host = SDMMC_HOST_DEFAULT();
    sdmmc_slot_config_t slot_config = SDMMC_SLOT_CONFIG_DEFAULT();
    esp_vfs_fat_sdmmc_mount_config_t mount_config = {
        .format_if_mount_failed = false,
        .max_files = 5,
        .allocation_unit_size = 16 * 1024
    };

    ret = esp_vfs_fat_sdmmc_mount(mount_point, &host, &slot_config, &mount_config, &card);
    if (ret != ESP_OK) {
        ESP_LOGE(TAG, "Failed to mount SD card (0x%x)", ret);
        return ret;
    }
    sdmmc_card_print_info(stdout, card);
    // Ensure directories exist
    mkdir("/sdcard/inbox", 0777);
    mkdir("/sdcard/escalations", 0777);
    mkdir("/sdcard/logs", 0777);
    return ESP_OK;
}

static bool is_file_in_buffer(const char* path)
{
    for (int i = 0; i < g_message_count; ++i) {
        const gui_decoded_message_t* m = &g_message_buffer[i];
        if (strcmp(m->file_path, path) == 0) return true;
    }
    return false;
}

static void process_sd_file(const char* path)
{
    if (is_file_in_buffer(path)) return;
    FILE* f = fopen(path, "rb");
    if (!f) {
        ESP_LOGE(TAG, "Failed to open %s", path);
        return;
    }
    fseek(f, 0, SEEK_END);
    long len = ftell(f);
    rewind(f);
    uint8_t* buf = (uint8_t*)malloc(len);
    if (!buf) { fclose(f); return; }
    fread(buf, 1, len, f);
    fclose(f);

    uint32_t offset = 0;
    while (offset < (uint32_t)len) {
        if ((len - offset) >= 6 && buf[offset] == BitPackedDecoder::SECURE_METHOD_BYTE) {
            char decoded[256];
            if (g_decoder.decompress_secure(buf + offset, 6, decoded, sizeof(decoded))) {
                gui_decoded_message_t msg = {};
                snprintf(msg.text, sizeof(msg.text), "%s", decoded);
                snprintf(msg.timestamp, sizeof(msg.timestamp), "%02lu:%02lu:%02lu",
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) / 3600) % 24,
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) / 60) % 60,
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) % 60));
                    uint8_t control = buf[offset + 1];
                    msg.confidence = (control >> 1) & 0x3;
                    msg.risk_flag = control & 0x1;
                    msg.message_type = (control >> 5) & 0x7;
                msg.sequence = g_total_messages;
                snprintf(msg.file_path, sizeof(msg.file_path), "%s", path);
                add_message(msg.text, msg.timestamp, msg.confidence, msg.risk_flag, msg.message_type, path);
            }
            offset += 6;
        } else if ((len - offset) >= 4 && buf[offset] == BitPackedDecoder::METHOD_BYTE) {
            char decoded[256];
            if (g_decoder.decompress(buf + offset, 4, decoded, sizeof(decoded))) {
                gui_decoded_message_t msg = {};
                snprintf(msg.text, sizeof(msg.text), "%s", decoded);
                snprintf(msg.timestamp, sizeof(msg.timestamp), "%02lu:%02lu:%02lu",
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) / 3600) % 24,
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) / 60) % 60,
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) % 60));
                uint8_t control = buf[offset + 1];
                msg.confidence = (control >> 1) & 0x3;
                msg.risk_flag = control & 0x1;
                msg.message_type = (control >> 5) & 0x7;
                msg.sequence = g_total_messages;
                snprintf(msg.file_path, sizeof(msg.file_path), "%s", path);
                add_message(msg.text, msg.timestamp, msg.confidence, msg.risk_flag, msg.message_type, path);
            }
            offset += 4;
        } else {
            // treat as text file - read entire contents and add as single message
            char* text = (char*)malloc(len - offset + 1);
            if (text) {
                size_t tlen = len - offset;
                memcpy(text, buf + offset, tlen);
                text[tlen] = '\0';
                gui_decoded_message_t msg = {};
                snprintf(msg.text, sizeof(msg.text), "%s", text);
                snprintf(msg.timestamp, sizeof(msg.timestamp), "%02lu:%02lu:%02lu",
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) / 3600) % 24,
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) / 60) % 60,
                         (unsigned long)((esp_timer_get_time() / 1000000ULL) % 60));
                msg.confidence = 2; // default to high
                msg.risk_flag = 0;
                msg.message_type = 0;
                msg.sequence = g_total_messages;
                snprintf(msg.file_path, sizeof(msg.file_path), "%s", path);
                add_message(msg.text, msg.timestamp, msg.confidence, msg.risk_flag, msg.message_type, path);
                free(text);
            }
            break; // entire file consumed
        }
    }
    free(buf);
}

static void sd_card_scan_task(void* arg)
{
    (void)arg;
    if (mount_sdcard() != ESP_OK) {
        vTaskDelete(NULL);
        return;
    }
    struct dirent* de;
    DIR* d = NULL;
    while (true) {
        d = opendir("/sdcard/inbox");
        if (d) {
            while ((de = readdir(d)) != NULL) {
                if (de->d_type == DT_REG) {
                    char path[512];
                    snprintf(path, sizeof(path), "/sdcard/inbox/%s", de->d_name);
                    process_sd_file(path);
                }
            }
            closedir(d);
        } else {
            ESP_LOGW(TAG, "No /sdcard/inbox directory or mount yet");
        }
        vTaskDelay(pdMS_TO_TICKS(2000));
    }
}

// Prototype for touch input task
static void touch_input_task(void* arg);

static void on_touch_coords(int x, int y, bool pressed)
{
    ESP_LOGI(TAG, "Touch coords: x=%d y=%d pressed=%d", x, y, pressed);
    if (!pressed) return; // only handle tap events for now
    // UI coordinates mapping - must mirror gui_render_ui layout
    const int header_height = 60;
    const int tab_height = 28;
    const int log_start_y = header_height + tab_height + 20;
    const int log_height = GUI_LCD_V_RES - log_start_y - 10;
    const int line_h = 32;
    const int max_visible = (log_height - 20) / line_h;
    const int detail_x = GUI_LCD_H_RES - 360;
    const int detail_y = log_start_y;
    const int detail_h = GUI_LCD_V_RES - detail_y - 20;

    // Tab tap detection
    if (y >= header_height && y <= header_height + tab_height + 6) {
        for (int t = 0; t < 3; ++t) {
            int tx = 15 + t * 120;
            int tw = 110;
            if (x >= tx && x <= tx + tw) {
                portENTER_CRITICAL(&g_ui_mux);
                g_ui_state.active_tab = (gui_tab_t)t;
                g_ui_state.selected_index = 0;
                g_ui_state.list_scroll_index = 0;
                g_ui_change_counter++;
                portEXIT_CRITICAL(&g_ui_mux);
                return;
            }
        }
    }

    // Message list tap - check which tab is active and use the appropriate count
    int list_left = 15;
    int list_right = detail_x - 20; // same right margin used in GUI layout
    if (x >= list_left && x <= list_right && y >= log_start_y && y <= log_start_y + log_height) {
        int row = (y - log_start_y - 10) / line_h;
        if (row < 0) row = 0;
        int start_idx = 0;
        int current_count = 0;
        portENTER_CRITICAL(&g_ui_mux);
        start_idx = (int)g_ui_state.list_scroll_index;
        current_count = (g_ui_state.active_tab == GUI_TAB_ESCALATIONS) ? g_escalation_count : g_message_count;
        portEXIT_CRITICAL(&g_ui_mux);
        int selected = start_idx + row;
        if (selected >= 0 && selected < current_count) {
            portENTER_CRITICAL(&g_ui_mux);
            g_ui_state.selected_index = (size_t)selected;
            // Recompute scroll so selected stays visible
            g_ui_state.list_scroll_index = (selected >= max_visible) ? selected - max_visible + 1 : 0;
            if ((int)g_ui_state.list_scroll_index < 0) g_ui_state.list_scroll_index = 0;
            // Clamp list_scroll_index so it does not exceed allowable range
            int max_start = (current_count > max_visible) ? (current_count - max_visible) : 0;
            if ((int)g_ui_state.list_scroll_index > max_start) g_ui_state.list_scroll_index = max_start;
            g_ui_change_counter++;
            portEXIT_CRITICAL(&g_ui_mux);
        }
        return;
    }

    // Detail overlay buttons
    const int detail_card_left = detail_x - 10;
    const int detail_card_right = GUI_LCD_H_RES - 10; // derived from draw_card(...)
    if (x >= detail_card_left && x <= detail_card_right) {
        int vy = detail_y + detail_h - 84; // top of the action buttons area
        int btn_y0 = vy;
        int btn_y1 = vy + 48;
        // VERIFY button
        int v_x0 = detail_x + 20;
        int v_x1 = v_x0 + 140;
        // ESCALATE button
        int e_x0 = detail_x + 180;
        int e_x1 = e_x0 + 140;
        if (y >= btn_y0 && y <= btn_y1) {
            if (x >= v_x0 && x <= v_x1) {
                ui_verify_selected_message();
                portENTER_CRITICAL(&g_ui_mux);
                g_ui_change_counter++;
                portEXIT_CRITICAL(&g_ui_mux);
            } else if (x >= e_x0 && x <= e_x1) {
                ui_escalate_selected_message();
                portENTER_CRITICAL(&g_ui_mux);
                g_ui_change_counter++;
                portEXIT_CRITICAL(&g_ui_mux);
            }
        }
        return;
    }

    // Settings overlay tap region: if Active Tab is Settings and user taps on the hint
    portENTER_CRITICAL(&g_ui_mux);
    gui_tab_t current_tab = g_ui_state.active_tab;
    portEXIT_CRITICAL(&g_ui_mux);
    if (current_tab == GUI_TAB_SETTINGS) {
        int cycle_btn_x0 = detail_x + 20;
        int cycle_btn_x1 = cycle_btn_x0 + 300; // width used when rendering settings card
        int cycle_btn_y0 = detail_y + detail_h - 84;
        int cycle_btn_y1 = cycle_btn_y0 + 48;
        if (x >= cycle_btn_x0 && x <= cycle_btn_x1 && y >= cycle_btn_y0 && y <= cycle_btn_y1) {
            // Cycle rotation
            GlyphRotationMode cur = gui_get_rotation();
            GlyphRotationMode next = (GlyphRotationMode)(((int)cur + 1) % 4);
            gui_set_rotation(next);
            portENTER_CRITICAL(&g_ui_mux);
            g_ui_change_counter++;
            portEXIT_CRITICAL(&g_ui_mux);
            return;
        }
        // detect toggles above the hint
        int toggle_w = 100;
        int toggle_h = 48;
        int tx = detail_x + 20;
        int ty = detail_y + detail_h - 84 - 64;
        // Swap XY
        if (x >= tx && x <= tx + toggle_w && y >= ty && y <= ty + toggle_h) {
            bool cur = gui_get_swapxy();
            gui_set_swapxy(!cur);
            portENTER_CRITICAL(&g_ui_mux);
            g_ui_change_counter++;
            portEXIT_CRITICAL(&g_ui_mux);
            return;
        }
        // Flip X
        tx += toggle_w + 12;
        if (x >= tx && x <= tx + toggle_w && y >= ty && y <= ty + toggle_h) {
            bool cur = gui_get_flipx();
            gui_set_flipx(!cur);
            portENTER_CRITICAL(&g_ui_mux);
            g_ui_change_counter++;
            portEXIT_CRITICAL(&g_ui_mux);
            return;
        }
        // Flip Y
        tx += toggle_w + 12;
        if (x >= tx && x <= tx + toggle_w && y >= ty && y <= ty + toggle_h) {
            bool cur = gui_get_flipy();
            gui_set_flipy(!cur);
            portENTER_CRITICAL(&g_ui_mux);
            g_ui_change_counter++;
            portEXIT_CRITICAL(&g_ui_mux);
            return;
        }
    }
}

static void translator_display_task(void* arg)
{
    (void)arg;
    const TickType_t delay_ticks = pdMS_TO_TICKS(250);  // Check every 250ms but only update when needed

    // Track previous state to avoid unnecessary redraws
    static uint32_t last_message_count = 0;
    static uint32_t last_error_count = 0;
    static uint32_t last_uptime_seconds = 0;
    static uint32_t last_ui_change_counter = 0;

    while (true) {
        uint32_t current_uptime = (uint32_t)(esp_timer_get_time() / 1000000ULL);
        
        // Only redraw if something actually changed
        bool needs_update = (g_total_messages != last_message_count) ||
                   (g_error_count != last_error_count) ||
                   (g_ui_change_counter != last_ui_change_counter);

        if (needs_update) {
            gui_translator_state_t state = {};
            
            // Determine connection status
            if (g_total_messages > 0) {
                state.connection_status = "RECEIVING";
            } else {
                state.connection_status = "WAITING";
            }

            state.message_count = g_total_messages;
            state.error_count = g_error_count;
            state.uptime_seconds = current_uptime;
            
            // Provide message buffer access
            state.messages = g_message_buffer;
            state.num_messages = g_message_count;
            state.escalations = g_escalation_buffer;
            state.num_escalations = g_escalation_count;

            // Copy UI state under protection to avoid races
            gui_ui_state_t ui_snapshot;
            portENTER_CRITICAL(&g_ui_mux);
            ui_snapshot = g_ui_state;
            portEXIT_CRITICAL(&g_ui_mux);
            gui_render_ui(&state, &ui_snapshot);
            
            // Update tracking
            last_message_count = g_total_messages;
            last_error_count = g_error_count;
            last_uptime_seconds = current_uptime;
            last_ui_change_counter = g_ui_change_counter;
        }
        
        vTaskDelay(delay_ticks);
    }
}

extern "C" void app_main(void)
{
    esp_err_t ret = nvs_flash_init();
    if (ret == ESP_ERR_NVS_NO_FREE_PAGES || ret == ESP_ERR_NVS_NEW_VERSION_FOUND) {
        ESP_ERROR_CHECK(nvs_flash_erase());
        ret = nvs_flash_init();
    }
    ESP_ERROR_CHECK(ret);

    ESP_LOGI(TAG, "AURA Translator booting");

    // Initialize LCD
    esp_lcd_panel_handle_t panel = gui_init();
    if (!panel) {
        ESP_LOGE(TAG, "GUI init failed");
        return;
    }

    // Register coordinate-based touch handler so platform-specific touch drivers can forward
    // raw (x,y) events directly into the UI.
    gui_register_touch_handler(on_touch_coords);
    // Initialize FT5x06 touchscreen driver and start its polling task.
    // Use I2C0 with SDA=GPIO8/SCL=GPIO9 for common ESP32-S3 LCD boards
    bool ft_driver_ok = false;
    if (ft5x06_init(I2C_NUM_0, (gpio_num_t)8, (gpio_num_t)9, (gpio_num_t)-1) == ESP_OK) {
        if (ft5x06_start_task() != ESP_OK) {
            ESP_LOGW(TAG, "FT5x06 polling task not started");
        } else {
            ft_driver_ok = true;
        }
    } else {
        ESP_LOGW(TAG, "FT5x06 not present or failed to init");
    }

    if (kEnableTestPattern) {
        gui_render_test_pattern();
        ESP_LOGW(TAG, "Test pattern mode active; translator disabled");
        vTaskDelete(nullptr);
        return;
    }

    // Configure UART for message reception
    uart_config_t uart_config = {
        .baud_rate = kUartBaudRate,
        .data_bits = UART_DATA_8_BITS,
        .parity = UART_PARITY_DISABLE,
        .stop_bits = UART_STOP_BITS_1,
        .flow_ctrl = UART_HW_FLOWCTRL_DISABLE,
        .rx_flow_ctrl_thresh = 122,
        .source_clk = UART_SCLK_DEFAULT,
    };

    ESP_ERROR_CHECK(uart_param_config(kUartPort, &uart_config));
    ESP_ERROR_CHECK(uart_driver_install(kUartPort, kUartRxBufferSize, 0, 0, NULL, 0));

    ESP_LOGI(TAG, "UART initialized on port %d at %d baud", kUartPort, kUartBaudRate);

    // Show initial translator screen
    gui_translator_state_t initial_state = {};
    initial_state.connection_status = "INITIALIZING";
    initial_state.message_count = 0;
    initial_state.error_count = 0;
    initial_state.uptime_seconds = 0;
    initial_state.messages = g_message_buffer;
    initial_state.num_messages = 0;
    gui_render_ui(&initial_state, &g_ui_state);

    // Add a test message to verify display
    // add_message("Translator initialized - awaiting messages", "00:00:00", 3, 0, 0, NULL);

    // Start UART receive task
    if (xTaskCreatePinnedToCore(uart_receive_task, "uart_rx", 4096, nullptr, 5, nullptr, tskNO_AFFINITY) != pdPASS) {
        ESP_LOGE(TAG, "Failed to start UART receive task");
        return;
    }

    // Start display update task
    if (xTaskCreatePinnedToCore(translator_display_task, "display", 4096, nullptr, 4, nullptr, tskNO_AFFINITY) != pdPASS) {
        ESP_LOGE(TAG, "Failed to start display task");
        return;
    }

    // Start SD card scan task
    if (xTaskCreatePinnedToCore(sd_card_scan_task, "sd_scan", 8192, nullptr, 3, nullptr, tskNO_AFFINITY) != pdPASS) {
        ESP_LOGW(TAG, "Failed to start SD card scan task");
    }

    // If FT5x06 driver is not present, start touch pad fallback
    if (!ft_driver_ok) {
        if (xTaskCreatePinnedToCore(touch_input_task, "touch", 4096, nullptr, 4, nullptr, tskNO_AFFINITY) != pdPASS) {
            ESP_LOGW(TAG, "Failed to start touch input task; continuing without touch support");
        }
    }

    ESP_LOGI(TAG, "Translator running");
    vTaskDelete(nullptr);
}

// Translate a touch-action into UI state changes. Simple actions: up/down/select/verify/escalate
static void handle_touch_action(const char* action)
{
    portENTER_CRITICAL(&g_ui_mux);
    int current_count = (g_ui_state.active_tab == GUI_TAB_ESCALATIONS) ? g_escalation_count : g_message_count;
    const int UI_MAX_VISIBLE = 10; // approximate visible rows; adjust if UI layout changes
    if (strcmp(action, "UP") == 0) {
        if (g_ui_state.selected_index > 0) {
            g_ui_state.selected_index--;
            // Ensure selected is visible
            if ((int)g_ui_state.selected_index < (int)g_ui_state.list_scroll_index) {
                g_ui_state.list_scroll_index = (g_ui_state.selected_index > 0) ? g_ui_state.selected_index : 0;
            }
            // clamp start index so it does not go negative or exceed allowable range
            int max_start = (current_count > UI_MAX_VISIBLE) ? (current_count - UI_MAX_VISIBLE) : 0;
            if ((int)g_ui_state.list_scroll_index > max_start) g_ui_state.list_scroll_index = max_start;
            g_ui_change_counter++;
            ESP_LOGI(TAG, "Touch UP -> selected_index=%lu", (unsigned long)g_ui_state.selected_index);
        }
    } else if (strcmp(action, "DOWN") == 0) {
        // clamp to current message count (esc vs inbox)
        if (current_count > 0 && g_ui_state.selected_index + 1 < (size_t)current_count) {
            g_ui_state.selected_index++;
            // Ensure selected is visible - if it is below visible window, scroll down
            if ((int)g_ui_state.selected_index >= (int)g_ui_state.list_scroll_index + UI_MAX_VISIBLE) {
                g_ui_state.list_scroll_index = (int)g_ui_state.selected_index - UI_MAX_VISIBLE + 1;
                if ((int)g_ui_state.list_scroll_index < 0) g_ui_state.list_scroll_index = 0;
            }
            // clamp start index so it does not exceed allowable range
            int max_start = (current_count > UI_MAX_VISIBLE) ? (current_count - UI_MAX_VISIBLE) : 0;
            if ((int)g_ui_state.list_scroll_index > max_start) g_ui_state.list_scroll_index = max_start;
            g_ui_change_counter++;
            ESP_LOGI(TAG, "Touch DOWN -> selected_index=%lu", (unsigned long)g_ui_state.selected_index);
        }
    } else if (strcmp(action, "SELECT") == 0) {
        // Cycle active tab on select
        g_ui_state.active_tab = (gui_tab_t)(((int)g_ui_state.active_tab + 1) % 3);
        // reset selection index when switching tab
        g_ui_state.selected_index = 0;
        g_ui_state.list_scroll_index = 0;
        g_ui_change_counter++;
        ESP_LOGI(TAG, "Touch SELECT -> active_tab=%d", (int)g_ui_state.active_tab);
    } else if (strcmp(action, "VERIFY") == 0) {
        ui_verify_selected_message();
        ESP_LOGI(TAG, "Touch VERIFY -> processed selected_index=%lu", (unsigned long)g_ui_state.selected_index);
        g_ui_change_counter++;
    } else if (strcmp(action, "ESCALATE") == 0) {
        ui_escalate_selected_message();
        ESP_LOGI(TAG, "Touch ESCALATE -> processed selected_index=%lu", (unsigned long)g_ui_state.selected_index);
        g_ui_change_counter++;
    }
    portEXIT_CRITICAL(&g_ui_mux);
}

static void touch_input_task(void* arg)
{
    (void)arg;
    ESP_LOGI(TAG, "Touch input task starting");

    // Initialize touch pad
    if (touch_pad_init() != ESP_OK) {
        ESP_LOGW(TAG, "touch_pad_init failed; skipping touch support");
        vTaskDelete(NULL);
        return;
    }

    // Configure the pads we want to use - start with defaults; we'll calibrate later
    // Configure the pads we want to use - start with defaults; we'll calibrate later
    touch_pad_config(TOUCH_PAD_UP);
    touch_pad_config(TOUCH_PAD_DOWN);
    touch_pad_config(TOUCH_PAD_SELECT);
    touch_pad_config(TOUCH_PAD_VERIFY);
    touch_pad_config(TOUCH_PAD_ESCALATE);

    // Read baseline raw values to establish thresholds (no filter for now)
    uint32_t baselines[5] = {0};
    const touch_pad_t pads[5] = {TOUCH_PAD_UP, TOUCH_PAD_DOWN, TOUCH_PAD_SELECT, TOUCH_PAD_VERIFY, TOUCH_PAD_ESCALATE};
    for (int i = 0; i < 5; ++i) {
        uint32_t val = 0;
        touch_pad_read_raw_data(pads[i], &val);
        baselines[i] = val;
    }

    // Set thresholds (a simple fraction of baseline). Lower filtered value indicates touch.
    // Store thresholds for local press detection (do not rely on older API that set threshold via touch_pad_config)
    uint32_t thresholds[5] = {0};
    for (int i = 0; i < 5; ++i) {
        uint32_t thr = (baselines[i] > 0) ? (baselines[i] * 60 / 100) : 0;
        if (thr == 0) thr = 1000; // fallback
        thresholds[i] = thr;
    }

    bool last_pressed[5] = {false};

    while (true) {
        for (int i = 0; i < 5; ++i) {
            uint32_t val = 0;
            touch_pad_read_raw_data(pads[i], &val);
            bool pressed = (val < (uint32_t)((baselines[i] * 75) / 100)); // heuristics: if filtered value drops enough
            if (pressed && !last_pressed[i]) {
                // rising edge - execute action
                switch (i) {
                    case 0: handle_touch_action("UP"); break;
                    case 1: handle_touch_action("DOWN"); break;
                    case 2: handle_touch_action("SELECT"); break;
                    case 3: handle_touch_action("VERIFY"); break;
                    case 4: handle_touch_action("ESCALATE"); break;
                }
            }
            last_pressed[i] = pressed;
        }
        vTaskDelay(pdMS_TO_TICKS(100));
    }
}
