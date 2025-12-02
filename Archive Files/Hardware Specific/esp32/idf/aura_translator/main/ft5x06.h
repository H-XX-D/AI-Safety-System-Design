// Simple FT5x06 touchscreen driver
#ifndef FT5X06_H
#define FT5X06_H

#include "sdkconfig.h"
#include "driver/i2c.h"
#include "driver/gpio.h"
#include "esp_err.h"

// Initialize FT5x06 driver on the specified I2C bus and pins.
// irq_pin is optional and may be set to -1 if unused.
#ifdef __cplusplus
extern "C" {
#endif

esp_err_t ft5x06_init(i2c_port_t i2c_num, gpio_num_t sda_pin, gpio_num_t scl_pin, gpio_num_t irq_pin);

// Start FT5x06 polling task
esp_err_t ft5x06_start_task(void);

// Stop FT5x06 polling task and release resources
esp_err_t ft5x06_stop(void);

#ifdef __cplusplus
}
#endif

#endif // FT5X06_H
