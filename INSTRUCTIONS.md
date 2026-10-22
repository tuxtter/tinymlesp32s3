# Setup Instructions

See [README.md](./README.md) for the component list and wiring diagram.

## 1. Wire the hardware

| MPU6050 | ESP32-S3 |
|---|---|
| VCC | 3V3 |
| GND | GND |
| SDA | GPIO8 |
| SCL | GPIO9 |
| AD0 | GND |

## 2. Train the model

TensorFlow has no wheels for Python 3.14, so use Python 3.10–3.12.

```bash
cd train
python3.11 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Add Kaggle credentials (`~/.kaggle/kaggle.json`, or set `KAGGLE_USERNAME` and `KAGGLE_KEY`), then:

```bash
python train.py            # downloads prabhatlodhi/mpu6050-hand-gesture-recognition-dataset
# or: python train.py --data /path/to/extracted/dataset --rate 50 --window 64
cp out/gesture_model.h ../firmware/main/
```

Check the printed classification report and int8 accuracy. If the CSV layout differs from what the script
expects, adapt `load_segments()` in `train.py`, and set `--rate` to the dataset's sampling rate.

## 3. Build and flash (ESP-IDF >= 5.2)

```bash
cd firmware
idf.py set-target esp32s3
idf.py build flash monitor
```

## 4. Use it

Gestures (`circle`, `punch`, `swipe_left`, `swipe_right`) print as `>>> punch (93%)`.
Tune `kMinConf` and `kCooldownMs` in `firmware/main/main.cc`. Mount the sensor in the same orientation as in the dataset.
