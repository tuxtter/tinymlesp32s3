#pragma once
#include "esp_err.h"
#include <stdint.h>
#ifdef __cplusplus
extern "C" {
#endif
#define MPU_SDA_GPIO 8
#define MPU_SCL_GPIO 9
esp_err_t mpu6050_init(void);
// Raw counts: accel +-2g (16384 LSB/g), gyro +-250 dps (131 LSB/dps)
esp_err_t mpu6050_read(float out[6]);
#ifdef __cplusplus
}
#endif
