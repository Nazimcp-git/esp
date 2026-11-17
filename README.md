# Sign Language Glove: Real-Time Hand Gesture Speech System

A complete wearable sign language translation system featuring:
1. **Wearable Layer**: ESP32 DevKit V1 microcontroller, 5 finger flex sensors, and MPU6050 6-DOF IMU (lightweight, low-power design).
2. **Onboard TinyML Edge AI**: Standalone 60-tree Random Forest classifier running directly in ESP32 Flash memory (< 1 ms latency) with an accept/lock recognition engine and automatic boot tare.
3. **Interactive 3D WebGL & Cloud Platform**: Zero-latency UDP streaming to a 3D hand visualizer, live Firebase Realtime Database cloud sync, and natural text-to-speech announcement via Web Speech API.

> [!NOTE]
> **Mobile App Architecture**: Per design specifications, all firmware, machine learning tools, web portals, cloud security rules, and integration scripts are provided directly in this repository.

---

## Repository Directory Structure

```
signlanguage/
├── firmware/
│   ├── glove_esp32/
│   │   ├── glove_esp32.ino         # Primary ESP32 firmware (Edge AI, Auto-Tare, UDP stream)
│   │   └── model_data.h            # Auto-generated C++ Random Forest model for ESP32 Flash
│   ├── bench/
│   │   └── bench_adc_i2c.ino       # Hardware validation sketch for flex sensors & MPU6050
│   └── tools/
│       ├── glove_3d_viewer.html    # Interactive 3D WebGL hand model with live flex oscilloscope
│       ├── udp_3d_server.py        # Zero-dependency Python UDP -> WebGL bridge (< 15 ms latency)
│       └── udp_listen.py           # Diagnostic script to test telemetry stream on PC
│
├── ml/
│   ├── vocab.json                  # Single source of truth for vocabulary, phrases, and categories
│   ├── features.py                 # Feature extraction & calibration normalization
│   ├── collect.py                  # Interactive training data recording over UDP
│   ├── train.py                    # Grouped cross-validation & export to model.json
│   ├── forest.py                   # Pure Python runtime evaluator matching scikit-learn
│   ├── recognizer.py               # 3-state accept/lock recognition state machine
│   ├── export_to_c.py              # Compiles trained Python Random Forest into C++ PROGMEM
│   ├── parity_test.py              # Exact numerical verification against embedded test vector
│   ├── replay.py                   # Playback simulator to measure firing speed and false fires
│   ├── fake_data.py                # Synthetic dataset generator for dry-run validation
│   ├── requirements.txt            # Python dependencies
│   ├── data/                       # Recorded CSV sessions and calibration JSONs
│   └── models/                     # Exported model.json, confusion matrix PNG & CSV
│
├── web/
│   ├── firebase.json               # Firebase Hosting & Realtime Database deployment configuration
│   ├── README.md                   # Cloud deployment instructions
│   └── public/
│       ├── index.html              # Responsive web portal (Reader, 3D Hand, Phrase Stream)
│       ├── style.css               # Modern slate-900 cyberpunk UI stylesheet
│       ├── hand3d.js               # Three.js 3D hand visualizer with forward kinematics
│       └── app.js                  # Frontend client with Web Speech API & Firebase RTDB sync
│
└── docs/
    ├── architecture.md             # 3-layer architecture, sequence diagram, state machines
    ├── hardware_schematic.md       # Pinout table, 10k resistor derivation, wiring instructions
    └── troubleshooting_and_testing.md # 4-stage bench test, error matrix, calibration steps
```

---

## Hardware Quick Reference

### Pin Assignments
- **Flex Sensors (ADC1 only, 10 kΩ pull-down resistors to GND)**:
  - **Thumb**: GPIO 36 (VP / ADC1_CH0)
  - **Index**: GPIO 33 (ADC1_CH5)
  - **Middle**: GPIO 32 (ADC1_CH4)
  - **Ring**: GPIO 35 (ADC1_CH7)
  - **Pinky**: GPIO 34 (ADC1_CH6)
- **MPU6050 (I2C)**: SDA $\to$ GPIO 21, SCL $\to$ GPIO 22, VCC $\to$ 3.3V, AD0 $\to$ GND (Address `0x68`)

---

## Machine Learning & Classification Pipeline

### 1. Install Dependencies
```bash
cd ml
pip install -r requirements.txt
```

### 2. Parity & Replay Testing
```bash
python parity_test.py     # Verify exported model matches scikit-learn
python replay.py fake1    # Simulate streaming playback & accept/lock rule
```

### 3. Live 3D Holographic Hand Visualization
```bash
python firmware/tools/udp_3d_server.py
```
Open `http://localhost:8080` to watch the 3D hand animate with real-time finger kinematics and IMU orientation.
