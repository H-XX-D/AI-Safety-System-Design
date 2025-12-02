/* Minimal FT5x06 I2C touchscreen support.
 * This module polls the controller and forwards touch coordinate events
 * to the registered GUI touch handler using gui_fire_touch_coords.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "ft5x06.h"
#include "freertos/FreeRTOS.h"
#include "freertos/task.h"
#include "driver/i2c.h"
#include "esp_log.h"
#include "esp_err.h"
#include "driver/gpio.h"

#include "gui.h"

static const char* TAG = "ft5x06";

// Default I2C parameters; can be overridden in ft5x06_init
static i2c_port_t s_i2c_port = I2C_NUM_0;
static gpio_num_t s_sda_pin = (gpio_num_t)21;
static gpio_num_t s_scl_pin = (gpio_num_t)22;
static gpio_num_t s_irq_pin = (gpio_num_t) -1;

// FT5x06 default I2C address (7-bit)
static const uint8_t FT5X06_ADDR = 0x38;

// Polling task handle
static TaskHandle_t s_task_handle = NULL;

// Track last touch state to forward press/release
static bool s_prev_pressed = false;
static int s_prev_x = 0;
static int s_prev_y = 0;

// Read register bytes from device
static esp_err_t i2c_read_regs(i2c_port_t i2c_num, uint8_t dev_addr, uint8_t reg, uint8_t* buf, size_t len)
{
    esp_err_t err = i2c_master_write_read_device(i2c_num, dev_addr, &reg, 1, buf, len, pdMS_TO_TICKS(100));
    return err;
}

// Polling task that queries FT5x06 and forwards the first touch contact
static void ft5x06_task(void* arg)
{
    (void)arg;
    ESP_LOGI(TAG, "FT5x06 polling task started");
    while (1) {
        uint8_t status = 0;
        esp_err_t err = i2c_read_regs(s_i2c_port, FT5X06_ADDR, 0x02, &status, 1);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "i2c_read_regs status failed: %s", esp_err_to_name(err));
            vTaskDelay(pdMS_TO_TICKS(50));
            continue;
        }
        uint8_t points = status & 0x0F;
        if (points == 0) {
            if (s_prev_pressed) {
                // send release event at previous coordinates
                    {
                        int ui_x = 0, ui_y = 0;
                        gui_map_coords_raw_to_ui(s_prev_x, s_prev_y, 4095, 4095, &ui_x, &ui_y);
                        ESP_LOGD(TAG, "FT5x06 release -> raw=(%d,%d) ui=(%d,%d)", s_prev_x, s_prev_y, ui_x, ui_y);
                        gui_fire_touch_coords(ui_x, ui_y, false);
                    }
                s_prev_pressed = false;
            }
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        // Read touch point data starting at 0x03
        uint8_t buf[32];
        size_t to_read = (size_t)points * 6U; // 6 bytes per point (FT5x06 style)
        if (to_read > sizeof(buf)) to_read = sizeof(buf);
        err = i2c_read_regs(s_i2c_port, FT5X06_ADDR, 0x03, buf, to_read);
        if (err != ESP_OK) {
            ESP_LOGW(TAG, "Failed to read touch data: %s", esp_err_to_name(err));
            vTaskDelay(pdMS_TO_TICKS(20));
            continue;
        }

        // Parse the first touch point
        // Format (6 bytes): XH, XL, YH, YL, ID, reserved
        // X = ((XH & 0x0F) << 8) | XL
        // Y = ((YH & 0x0F) << 8) | YL
        uint8_t xh = buf[0];
        uint8_t xl = buf[1];
        uint8_t yh = buf[2];
        uint8_t yl = buf[3];
        int x = (((int)(xh & 0x0F) << 8) | (int)xl);
        int y = (((int)(yh & 0x0F) << 8) | (int)yl);

        // Bound coordinates to display extents 0..800 and 0..480 (approx), but leave so the GUI mapping does the rest
        if (x < 0) { x = 0; }
        if (x > GUI_LCD_H_RES) { x = GUI_LCD_H_RES; }
        if (y < 0) { y = 0; }
        if (y > GUI_LCD_V_RES) { y = GUI_LCD_V_RES; }

        // Map raw coords to UI coords and forward press event
        {
            int ui_x = 0, ui_y = 0;
            gui_map_coords_raw_to_ui(x, y, 4095, 4095, &ui_x, &ui_y);
            ESP_LOGD(TAG, "FT5x06 press -> raw=(%d,%d) ui=(%d,%d)", x, y, ui_x, ui_y);
            gui_fire_touch_coords(ui_x, ui_y, true);
            s_prev_x = x; s_prev_y = y; s_prev_pressed = true;
        }
        s_prev_x = x; s_prev_y = y; s_prev_pressed = true;

        vTaskDelay(pdMS_TO_TICKS(10));
    }
}

esp_err_t ft5x06_init(i2c_port_t i2c_num, gpio_num_t sda_pin, gpio_num_t scl_pin, gpio_num_t irq_pin)
{
    s_i2c_port = i2c_num;
    s_sda_pin = sda_pin;
    s_scl_pin = scl_pin;
    s_irq_pin = irq_pin;

    i2c_config_t conf = {0};
    conf.mode = I2C_MODE_MASTER;
    conf.sda_io_num = s_sda_pin;
    conf.scl_io_num = s_scl_pin;
    conf.sda_pullup_en = GPIO_PULLUP_ENABLE;
    conf.scl_pullup_en = GPIO_PULLUP_ENABLE;
    conf.master.clk_speed = 100000; // 100k default
    esp_err_t err = i2c_param_config(s_i2c_port, &conf);
    if (err != ESP_OK) return err;

    err = i2c_driver_install(s_i2c_port, conf.mode, 0, 0, 0);
    if (err != ESP_OK) {
        ESP_LOGE(TAG, "i2c_driver_install failed: %s", esp_err_to_name(err));
        return err;
    }

    // Try reading device id or status to validate; if this fails, return error
    uint8_t status = 0;
    err = i2c_read_regs(s_i2c_port, FT5X06_ADDR, 0x02, &status, 1);
    if (err != ESP_OK) {
        ESP_LOGW(TAG, "ft5x06 probing read failed: %s", esp_err_to_name(err));
        i2c_driver_delete(s_i2c_port);
        return ESP_ERR_NOT_FOUND;
    }
    return ESP_OK;
}

esp_err_t ft5x06_start_task(void)
{
    if (s_task_handle) return ESP_OK; // already running
    BaseType_t rc = xTaskCreatePinnedToCore(ft5x06_task, "ft5x06", 4096, NULL, 5, &s_task_handle, tskNO_AFFINITY);
    if (rc != pdPASS) {
        s_task_handle = NULL;
        return ESP_ERR_NO_MEM;
    }
    return ESP_OK;
}

esp_err_t ft5x06_stop(void)
{
    if (!s_task_handle) return ESP_OK;
    vTaskDelete(s_task_handle);
    s_task_handle = NULL;
    i2c_driver_delete(s_i2c_port);
    return ESP_OK;
}
