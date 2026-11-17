# Testing, Calibration & Troubleshooting Guide

This document outlines the validation procedures, calibration routines, and common diagnostic resolutions for the Sign Language Glove system.

---

## 1. Bench Validation Sequence (Build Order)

Follow this 4-stage checklist on a breadboard before soldering anything to the fabric glove:

### Stage 1: ESP32 Baseline
- Upload a standard LED blink sketch targeting `GPIO 2`.
- Verify serial communication at `115200` baud.

### Stage 2: 10k Voltage Dividers (All 5 Fingers)
- Wire flex sensors to ADC1 channels: Thumb (`GPIO 36`), Index (`GPIO 33`), Middle (`GPIO 32`), Ring (`GPIO 35`), Pinky (`GPIO 34`).
- Add 10 kΩ pull-down resistors from each pin to `GND`.
- Upload `firmware/bench/bench_adc_i2c.ino`.
- **Pass Check**: Resting flat counts read $\sim 1170$. Bending to 90° causes readings to drop to $\sim 480$ (a healthy swing of $\sim 690$ counts).

### Stage 3: MPU6050 Accelerometer & Gyroscope
- Connect `SDA` to `GPIO 21`, `SCL` to `GPIO 22`, and `VCC`/`GND` to `3V3`/`GND`.
- **Pass Check**: Serial monitor logs `WHO_AM_I = 0x68 -> PASSED`. With the sensor flat, gravity vector reads approximately $[0, 0, 1.0]\,g$.

### Stage 4: Live 3D Visualizer & Speech Synthesis
- Run `python firmware/tools/udp_3d_server.py` on your computer.
- Open `http://localhost:8080`.
- **Pass Check**: 3D holographic hand moves in real time matching your physical finger flexion and hand orientation.

---

## 2. Troubleshooting Matrix

| Fault Code | Observed Symptom | Probable Cause | Remediation Step |
|---|---|---|---|
| **E-01** | ADC values read constant 0 or 4095 counts | Miswired divider, open ground, or short to 3.3V rail | Check resistor continuity with multimeter. Confirm flex sensor is between 3V3 and pin, with 10 kΩ to GND. |
| **E-02** | Flex readings freeze when Wi-Fi connects | Flex sensors connected to ADC2 pins | Move all flex sensors to ADC1 channels (GPIO 32, 33, 34, 35, 36). ADC2 cannot operate concurrently with Wi-Fi. |
| **E-03** | Serial monitor says `MPU6050 MISSING` | Loose I2C lines or mismatched address | Verify SDA is on GPIO 21 and SCL on GPIO 22. Ensure `AD0` pin on MPU6050 is pulled to GND for address `0x68`. |
| **E-04** | UDP listener receives 0 frames | IP address mismatch or subnet routing block | Ensure laptop is connected to phone hotspot. Set `TARGET_IP_OVERRIDE` in `glove_esp32.ino` to laptop's Wi-Fi IP address. Allow port 4210 in firewall. |
| **E-05** | Gestures misclassified between two signs | Gestures share identical finger bend and differ only in yaw | MPU6050 lacks a magnetometer (pitch/roll only). Ensure vocabulary gestures differ by finger poses or by $\ge 60^\circ$ pitch/roll tilt. |

---

## 3. Session Calibration Procedure

Because flex sensor resistance shifts slightly with temperature, fabric tension, and hand temperature, the firmware includes an **Auto-Tare** routine:

1. **Automatic Boot Tare**:
   - Keep hand flat on the table when powering on or resetting the ESP32.
   - The firmware averages 40 samples during the first 600 ms and automatically establishes `calibOpen`.
2. **Manual Serial Tare**:
   - Send `'t'` or `'0'` in the Arduino Serial Monitor at 115200 baud anytime while wearing the glove to re-zero the baseline.
3. **Span Verification**:
   - The system uses $\Delta = |\text{raw} - \text{baseline}|$.
   - A drop of $\ge 200$ counts registers as a noticeable flex, with full 100% curl occurring around $\Delta \approx 600-690$ counts.
