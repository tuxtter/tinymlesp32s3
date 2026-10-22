"""Download the Kaggle MPU6050 gesture dataset, train a small 1D-CNN, export int8 TFLite + C header.

Usage:  python train.py [--data DIR] [--rate 50] [--window 64]
Dataset loader is format-tolerant: it accepts either
  (a) many CSVs, label taken from parent folder or file name, or
  (b) one CSV with a label column.
Numeric columns are interpreted in order as ax ay az gx gy gz (extra non-label columns such as
timestamps are dropped when there are more than 6).
"""
import argparse, json, re
from pathlib import Path
import numpy as np, pandas as pd

CLASSES = ["circle", "punch", "swipe_left", "swipe_right"]
ALIASES = {"circle": "circle", "punch": "punch",
           "swiftleft": "swipe_left", "swipeleft": "swipe_left", "left": "swipe_left",
           "swiftright": "swipe_right", "swiperight": "swipe_right", "right": "swipe_right"}
LABEL_COLS = {"label", "gesture", "class", "target", "activity"}
TIME_COLS = {"time", "timestamp", "t", "index", "id", "unnamed: 0"}


def norm_label(s):
    key = re.sub(r"[^a-z]", "", str(s).lower())
    for a, c in ALIASES.items():
        if a in key:
            return c
    return None


def sensor_matrix(df):
    cols = [c for c in df.columns if str(c).strip().lower() not in LABEL_COLS | TIME_COLS]
    df = df[cols].apply(pd.to_numeric, errors="coerce").dropna(axis=1, how="all").dropna()
    if df.shape[1] < 6:
        raise ValueError(f"need 6 sensor columns, got {list(df.columns)}")
    return df.iloc[:, :6].to_numpy(np.float32)


def load_segments(root):
    """Return list of (matrix[N,6], class_name)."""
    segs = []
    for f in sorted(Path(root).rglob("*.csv")):
        df = pd.read_csv(f)
        lab_col = next((c for c in df.columns if str(c).strip().lower() in LABEL_COLS), None)
        try:
            if lab_col is not None:
                for lab, g in df.groupby(lab_col):
                    c = norm_label(lab)
                    if c:
                        segs.append((sensor_matrix(g), c))
            else:
                c = norm_label(f.parent.name) or norm_label(f.stem)
                if c:
                    segs.append((sensor_matrix(df), c))
        except ValueError as e:
            print("skip", f, e)
    if not segs:
        raise SystemExit(f"No usable CSV data found in {root}. Inspect the dataset and adapt load_segments().")
    return segs


def windows(segs, win, stride):
    X, y = [], []
    for m, c in segs:
        if len(m) < win:
            m = np.pad(m, ((0, win - len(m)), (0, 0)), mode="edge")
        for s in range(0, len(m) - win + 1, stride):
            X.append(m[s:s + win]); y.append(CLASSES.index(c))
    return np.stack(X), np.array(y)


def build(win, n):
    import tensorflow as tf
    L = tf.keras.layers
    return tf.keras.Sequential([
        L.Input((win, 6)),
        L.Conv1D(16, 5, padding="same", activation="relu"), L.MaxPool1D(2),
        L.Conv1D(32, 5, padding="same", activation="relu"), L.MaxPool1D(2),
        L.Conv1D(32, 3, padding="same", activation="relu"),
        L.GlobalAveragePooling1D(), L.Dropout(0.3),
        L.Dense(32, activation="relu"), L.Dense(n, activation="softmax")])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data"); ap.add_argument("--window", type=int, default=64)
    ap.add_argument("--stride", type=int, default=16); ap.add_argument("--rate", type=int, default=50)
    ap.add_argument("--epochs", type=int, default=60); ap.add_argument("--out", default="out")
    a = ap.parse_args()

    import tensorflow as tf
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import classification_report, confusion_matrix

    out = Path(a.out); out.mkdir(exist_ok=True)
    root = a.data
    if not root:
        import kagglehub
        root = kagglehub.dataset_download("prabhatlodhi/mpu6050-hand-gesture-recognition-dataset")
    print("dataset:", root)
    segs = load_segments(root)
    X, y = windows(segs, a.window, a.stride)
    print("windows:", X.shape, "per class:", np.bincount(y, minlength=len(CLASSES)))

    # Raw MPU6050 counts have |value| in the thousands; physical units (g, dps) are much smaller.
    raw = bool(np.abs(X[..., :3]).max() > 20)
    print("detected", "raw counts" if raw else "physical units (g, deg/s)")
    mean = X.reshape(-1, 6).mean(0); std = X.reshape(-1, 6).std(0) + 1e-6
    Xn = (X - mean) / std

    Xtr, Xte, ytr, yte = train_test_split(Xn, y, test_size=0.2, stratify=y, random_state=1)
    model = build(a.window, len(CLASSES))
    model.compile("adam", "sparse_categorical_crossentropy", metrics=["accuracy"])
    model.fit(Xtr, ytr, validation_split=0.15, epochs=a.epochs, batch_size=32, verbose=2,
              callbacks=[tf.keras.callbacks.EarlyStopping(patience=10, restore_best_weights=True)])
    pred = model.predict(Xte, verbose=0).argmax(1)
    print(classification_report(yte, pred, target_names=CLASSES)); print(confusion_matrix(yte, pred))

    # Keras 3 + from_keras_model can crash MLIR on Conv1D variables; convert via a SavedModel instead.
    model.export(str(out / "saved_model"))
    conv = tf.lite.TFLiteConverter.from_saved_model(str(out / "saved_model"))
    conv.optimizations = [tf.lite.Optimize.DEFAULT]
    conv.representative_dataset = lambda: ([Xtr[i:i + 1].astype(np.float32)] for i in range(min(300, len(Xtr))))
    conv.target_spec.supported_ops = [tf.lite.OpsSet.TFLITE_BUILTINS_INT8]
    conv.inference_input_type = tf.int8; conv.inference_output_type = tf.int8
    tfl = conv.convert()

    # Check int8 accuracy
    it = tf.lite.Interpreter(model_content=tfl); it.allocate_tensors()
    i, o = it.get_input_details()[0], it.get_output_details()[0]
    sc, zp = i["quantization"]; ok = 0
    for x, t in zip(Xte, yte):
        it.set_tensor(i["index"], np.clip(np.round(x[None] / sc + zp), -128, 127).astype(np.int8))
        it.invoke(); ok += it.get_tensor(o["index"]).argmax() == t
    print(f"int8 test accuracy: {ok / len(yte):.3f}, model size {len(tfl)} bytes")

    (out / "gesture.tflite").write_bytes(tfl)
    body = ",".join(f"0x{b:02x}" for b in tfl)
    hdr = f"""// Auto-generated by train/train.py
#pragma once
#include <stdint.h>
#include <stdalign.h>
#define GESTURE_WINDOW {a.window}
#define GESTURE_SAMPLE_RATE_HZ {a.rate}
#define GESTURE_NUM_CLASSES {len(CLASSES)}
#define GESTURE_USE_RAW_COUNTS {1 if raw else 0}
static const float kFeatMean[6] = {{{",".join(f"{v:.6f}f" for v in mean)}}};
static const float kFeatStd[6] = {{{",".join(f"{v:.6f}f" for v in std)}}};
static const char *const kGestureNames[GESTURE_NUM_CLASSES] = {{{",".join(f'"{c}"' for c in CLASSES)}}};
alignas(16) static const unsigned char g_gesture_model[] = {{{body}}};
static const unsigned int g_gesture_model_len = {len(tfl)};
"""
    (out / "gesture_model.h").write_text(hdr)
    (out / "meta.json").write_text(json.dumps(dict(classes=CLASSES, window=a.window, rate=a.rate, raw=raw)))
    print("wrote", out / "gesture_model.h", "-> copy to firmware/main/")


if __name__ == "__main__":
    main()
