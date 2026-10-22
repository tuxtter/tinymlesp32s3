#include "mpu6050.h"
#include "driver/i2c_master.h"
#include "esp_log.h"

#define MPU_ADDR 0x68
static const char *TAG = "mpu6050";
static i2c_master_dev_handle_t dev;

static esp_err_t log_error(const char *operation, esp_err_t error) {
    ESP_LOGE(TAG, "%s failed: %s", operation, esp_err_to_name(error));
    return error;
}

static esp_err_t wr(uint8_t reg, uint8_t v) {
    uint8_t b[2] = {reg, v};
    return i2c_master_transmit(dev, b, 2, 100);
}

esp_err_t mpu6050_init(void) {
    i2c_master_bus_handle_t bus;
    i2c_master_bus_config_t bc = {
        .clk_source = I2C_CLK_SRC_DEFAULT, .i2c_port = I2C_NUM_0,
        .sda_io_num = MPU_SDA_GPIO, .scl_io_num = MPU_SCL_GPIO,
        .glitch_ignore_cnt = 7, .flags.enable_internal_pullup = true,
    };
    esp_err_t e = i2c_new_master_bus(&bc, &bus);
    if (e != ESP_OK) return log_error("create I2C bus", e);
    e = i2c_master_probe(bus, MPU_ADDR, 100);
    if (e == ESP_ERR_NOT_FOUND) {
        ESP_LOGE(TAG, "no device at I2C address 0x%02x; check power, SDA/SCL, and AD0", MPU_ADDR);
        return e;
    }
    if (e != ESP_OK) return log_error("probe I2C address", e);
    i2c_device_config_t dc = {.dev_addr_length = I2C_ADDR_BIT_LEN_7, .device_address = MPU_ADDR, .scl_speed_hz = 400000};
    e = i2c_master_bus_add_device(bus, &dc, &dev);
    if (e != ESP_OK) return log_error("add MPU6050 to I2C bus", e);
    uint8_t who = 0, reg = 0x75;
    e = i2c_master_transmit_receive(dev, &reg, 1, &who, 1, 100);
    if (e != ESP_OK) return log_error("read WHO_AM_I", e);
    if (who != 0x68 && who != 0x70 && who != 0x72) {
        ESP_LOGE(TAG, "unexpected WHO_AM_I value 0x%02x", who);
        return ESP_ERR_NOT_FOUND;
    }
    if ((e = wr(0x6B, 0x01)) != ESP_OK) return log_error("wake sensor", e);
    if ((e = wr(0x1A, 0x03)) != ESP_OK) return log_error("configure low-pass filter", e);
    if ((e = wr(0x1B, 0x00)) != ESP_OK) return log_error("configure gyroscope", e);
    e = wr(0x1C, 0x00);
    if (e != ESP_OK) return log_error("configure accelerometer", e);
    ESP_LOGI(TAG, "MPU6050 detected (WHO_AM_I=0x%02x)", who);
    return ESP_OK;
}

esp_err_t mpu6050_read(float out[6]) {
    uint8_t reg = 0x3B, b[14];
    esp_err_t e = i2c_master_transmit_receive(dev, &reg, 1, b, 14, 100);
    if (e) return e;
    // b: AX AY AZ TEMP GX GY GZ (big endian)
    int16_t r[7];
    for (int i = 0; i < 7; i++) r[i] = (int16_t)((b[2 * i] << 8) | b[2 * i + 1]);
    out[0] = r[0]; out[1] = r[1]; out[2] = r[2];
    out[3] = r[4]; out[4] = r[5]; out[5] = r[6];
    return ESP_OK;
}
