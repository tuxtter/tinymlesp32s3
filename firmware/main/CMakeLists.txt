idf_component_register(SRCS "main.cc" "mpu6050.c"
                       INCLUDE_DIRS "."
                       REQUIRES driver esp_timer espressif__esp-tflite-micro)
