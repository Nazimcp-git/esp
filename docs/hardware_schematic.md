# Hardware Schematic, Wiring & Mechanical Guide

This document describes the circuit schematic, component selection, mathematical derivations, and mechanical assembly for the Sign Language Glove.

---

## 1. Pin Assignment Table

| Module / Component | Pin Name | ESP32 GPIO | Pin Role & Hardware Notes |
|---|---|---|---|
| **Flex 1 (Thumb)** | Signal Node | **GPIO 36 (VP)** | ADC1_CH0. Voltage divider with 10 kΩ pull-down to GND. |
| **Flex 2 (Index)** | Signal Node | **GPIO 33** | ADC1_CH5. Voltage divider with 10 kΩ pull-down to GND. |
| **Flex 3 (Middle)** | Signal Node | **GPIO 32** | ADC1_CH4. Voltage divider with 10 kΩ pull-down to GND. |
| **Flex 4 (Ring)** | Signal Node | **GPIO 35** | ADC1_CH7. Input only. 10 kΩ pull-down to GND. |
| **Flex 5 (Pinky)** | Signal Node | **GPIO 34** | ADC1_CH6. Input only. 10 kΩ pull-down to GND. |
| **All 5 Flex Sensors**| Power Rail | **3V3** | Single common 3.3V power bus routed along the fingers. |
| **MPU6050 IMU** | VCC, GND | **3V3, GND** | 3.3V logic and supply rail. AD0 connected to GND (Address `0x68`). |
| **MPU6050 IMU** | SDA | **GPIO 21** | I2C Data bus. |
| **MPU6050 IMU** | SCL | **GPIO 22** | I2C Clock bus. |
| **Onboard Status LED**| Anode | **GPIO 2** | Built-in LED on ESP32 DevKit V1. |
| *DFPlayer & Speaker* | *Removed* | *Unused* | Hardware DFPlayer Mini and speaker removed; audio output is delivered cleanly through Web Speech API on the connected phone/laptop. |

> [!IMPORTANT]
> **ADC Pin Constraint**: All 5 flex sensors MUST use ADC1 pins (GPIO 32–36). ADC2 pins (GPIO 0, 2, 4, 12–15, 25–27) are disabled in hardware by the ESP32 Wi-Fi driver when the radio is transmitting.

---

## 2. Voltage Divider Resistor Analysis

Each finger flex sensor is configured as a voltage divider between the 3.3 V rail and Ground:

```
3.3V ──[ Flex Sensor (R_flex) ]──●── ESP32 ADC1 Pin (GPIO 32..36)
                                 │
                            [ 10 kΩ R_fixed ]
                                 │
GND ─────────────────────────────┴
```

The voltage at the ADC node is given by:

$$V_{\text{out}} = 3.3\,\text{V} \times \frac{R_{\text{fixed}}}{R_{\text{flex}} + R_{\text{fixed}}}$$

Corresponding 12-bit ADC reading (0 to 4095 counts):

$$\text{Counts} = \frac{V_{\text{out}}}{3.3\,\text{V}} \times 4095 = 4095 \times \frac{R_{\text{fixed}}}{R_{\text{flex}} + R_{\text{fixed}}}$$

For standard 2.2-inch flex sensors:
- Flat resistance ($R_{\text{flat}}$) $\approx 25\,\text{k}\Omega$
- 90° bent resistance ($R_{\text{bent}}$) $\approx 75\,\text{k}\Omega$

### Comparison: Why the 200 Ω Resistor in the Initial Circuit Fails

| Fixed Resistor ($R_{\text{fixed}}$) | $V_{\text{out}}$ (Flat) | $V_{\text{out}}$ (Bent) | Voltage Swing ($\Delta V$) | ADC Count Swing | Evaluation |
|---|---|---|---|---|---|
| **200 Ω** (Initial flawed diagram) | 0.026 V | 0.009 V | **0.017 V** | **~21 counts** | **UNUSABLE**: Signal is completely buried under ADC noise. |
| **10 kΩ** (Corrected design) | 0.943 V | 0.388 V | **0.555 V** | **~689 counts** | **EXCELLENT**: Crisp dynamic range with clean SNR. |
| **22 kΩ** (Optimal theoretical) | 1.545 V | 0.748 V | **0.797 V** | **~990 counts** | Maximum possible swing for this resistance curve. |

---

## 3. Power & Filtering Benefits (Speaker Removed)

Removing the hardware DFPlayer Mini and physical 8 Ω speaker provides major advantages:
1. **Zero Brownouts / Resets**: The DFPlayer's 3W class D amplifier used to draw sudden current surges of up to 500–1000 mA on 5V, causing voltage sags on weak power supplies. Without it, the circuit draws < 120 mA total.
2. **Simplified Wiring**: Eliminates 6 wires, the $1\,\text{k}\Omega$ TX resistor, and large bulk decoupling capacitors.
3. **High-Fidelity Audio**: Speech is synthesized using browser Web Speech API on the user's phone or computer with crystal-clear pronunciation.

---

## 4. Glove Mechanical Assembly Guidelines

1. **Joint Positioning**:
   - Mark the flex sensor active region across the proximal interphalangeal (PIP) knuckle joints.
   - Do **NOT** glue the sensor flat along its entire length. Gluing causes buckling, crimping, and eventual sensor fatigue failure.
2. **Floating Sleeve Design**:
   - Sew or fabric-glue an elastic tunnel/sleeve along each finger.
   - Anchor **only the wire terminal end** at the base of each finger; allow the sensor tip to float and slide slightly during bending.
3. **Strain Relief**:
   - Route one common 3.3V wire and five signal lines to the back of the hand.
   - Place all five 10 kΩ pull-down resistors on the central PCB/perfboard, never on the moving fingers.
   - Leave small service loops of slack at the knuckles to avoid tension when forming a fist.
4. **IMU Mounting**:
   - Fix the MPU6050 flat on the rigid dorsal surface (back of hand) using dense foam tape and Velcro.
   - The IMU axes define pitch and roll; ensure the board is securely fixed so it does not shift during use.
