# TinyML gesture recognition: ESP32-S3 + MPU6050

Classifies **circle, punch, swipe left, swipe right** on-device (int8 1D-CNN, TFLite Micro).
Dataset: Kaggle `prabhatlodhi/mpu6050-hand-gesture-recognition-dataset`.

## Components
| Qty | Part | Notes |
|---|---|---|
| 1 | ESP32-S3 dev board (e.g. ESP32-S3-DevKitC-1) | any S3 module works |
| 1 | MPU6050 breakout (GY-521) | 3.3 V-safe; has pull-ups on board |
| 4 | Dupont jumper wires | female-female |
| 1 | USB-C cable | power + flashing |
| opt | LiPo + charger / small breadboard | for a wearable |

## Wiring
```
 MPU6050 (GY-521)              ESP32-S3 DevKit
 ┌────────┐                    ┌──────────────┐
 │ VCC    ├────────────────────┤ 3V3          │
 │ GND    ├────────────────────┤ GND          │
 │ SDA    ├────────────────────┤ GPIO 8 (SDA) │
 │ SCL    ├────────────────────┤ GPIO 9 (SCL) │
 │ AD0    ├── GND (addr 0x68)  │              │
 │ INT    │   (not used)       │              │
 └────────┘                    └──────────────┘
```
Pins are set in `firmware/main/mpu6050.h`. If your GY-521 lacks pull-ups, the driver enables the internal ones (add 4.7 kΩ to 3V3 for reliability).

## 1. Train
```bash
cd train
python3.11 -m venv .venv && source .venv/bin/activate   # TF needs Python <=3.12
pip install -r requirements.txt
# Kaggle credentials: ~/.kaggle/kaggle.json (or KAGGLE_USERNAME/KAGGLE_KEY)
python train.py            # or: python train.py --data /path/to/extracted/dataset
cp out/gesture_model.h ../firmware/main/
```
Prints per-class report, confusion matrix and int8 accuracy.

**Important:** the CSV layout of the dataset could not be inspected when this was written. `train.py` auto-detects
per-gesture folders/filenames or a label column, and treats the first 6 numeric columns as ax ay az gx gy gz.
If it errors or finds odd data, adapt `load_segments()`. Also match `--rate` (and `--window`) to the dataset's
sampling rate, and the sensor range (raw counts vs g/deg/s is auto-detected and baked into the header).

## 2. Flash (ESP-IDF >= 5.2)
```bash
cd firmware
idf.py set-target esp32s3
idf.py build flash monitor
```
Detected gestures print as `>>> punch (93%)`. Tune `kMinConf` / `kCooldownMs` in `main.cc`.
Mount the sensor in the same orientation used in the dataset.
