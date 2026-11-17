// bench_adc_i2c.ino  --  Bench Hardware Validation Test
// Matches circuit diagram with 10k pull-down resistors
// Verifies:
// 1. All 5 flex sensors on ADC1 (GPIO 36=Thumb, 33=Index, 32=Middle, 35=Ring, 34=Pinky)
// 2. 10k divider voltage swing (~1170 flat -> ~480 bent)
// 3. MPU6050 I2C bus scan, WHO_AM_I register (0x68), and 3-axis accelerometer readings

#include <Wire.h>

// Pins strictly on ADC1 (safe with Wi-Fi active):
// Thumb (VP=36), Index (D33=33), Middle (D32=32), Ring (D35=35), Pinky (D34=34)
const uint8_t FLEX[5] = {36, 33, 32, 35, 34};
const char* const FINGER_NAMES[5] = {"Thumb(36)", "Index(33)", "Middle(32)", "Ring(35)", "Pinky(34)"};

void setup() {
  Serial.begin(115200);
  delay(1000);
  
  Serial.println("\n========================================================");
  Serial.println("  SIGN LANGUAGE GLOVE -- HARDWARE BENCH TEST (10k DIVIDERS)");
  Serial.println("========================================================");
  
  // Set ADC resolution (12-bit = 0..4095) and 11dB attenuation (~0 to 3.3V range)
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);
  for (int i = 0; i < 5; i++) {
    analogSetPinAttenuation(FLEX[i], ADC_11db);
  }
  
  // Initialize I2C bus (SDA=21, SCL=22)
  Wire.begin(21, 22);
  Wire.setClock(400000);
  delay(100);
  
  Serial.println("\n[1] Scanning I2C Bus (SDA=21, SCL=22)...");
  uint8_t count = 0;
  for (uint8_t a = 1; a < 127; a++) {
    Wire.beginTransmission(a);
    if (Wire.endTransmission() == 0) {
      Serial.printf("    -> Found I2C device at address: 0x%02X\n", a);
      count++;
    }
  }
  if (count == 0) {
    Serial.println("    [WARNING] No I2C devices found! Check MPU6050 wiring (VCC=3.3V, GND, SDA=21, SCL=22).");
  }
  
  // Verify MPU6050 WHO_AM_I register (0x75)
  Wire.beginTransmission(0x68);
  Wire.write(0x75);
  Wire.endTransmission(false);
  Wire.requestFrom((int)0x68, 1);
  if (Wire.available()) {
    uint8_t id = Wire.read();
    Serial.printf("[2] MPU6050 WHO_AM_I = 0x%02X (Expected: 0x68) -> %s\n", 
      id, (id == 0x68 || id == 0x70 || id == 0x72) ? "PASSED" : "UNEXPECTED ID");
  } else {
    Serial.println("[2] MPU6050 WHO_AM_I -> FAILED to read from 0x68");
  }
  
  // Wake up MPU6050 from sleep mode
  Wire.beginTransmission(0x68);
  Wire.write(0x6B); // PWR_MGMT_1
  Wire.write(0x00); // Clear sleep bit
  Wire.endTransmission();
  
  Serial.println("\n[3] Starting Live Sensor Telemetry (10 readings/sec)");
  Serial.println("    FLEX COUNTS: Expected ~1170 when FLAT -> drops to ~480 when BENT");
  Serial.println("----------------------------------------------------------------------------------");
  Serial.println("   Thumb(36) |   Index(33) |  Middle(32) |    Ring(35) |   Pinky(34) | Accel [ax, ay, az] g");
  Serial.println("----------------------------------------------------------------------------------");
}

void loop() {
  // 1. Read 5 flex sensors with 4x hardware oversampling
  int raw[5];
  for (int i = 0; i < 5; i++) {
    int s = 0;
    for (int k = 0; k < 4; k++) s += analogRead(FLEX[i]);
    raw[i] = s / 4;
  }
  
  // 2. Read 6 bytes of accelerometer data from register 0x3B
  int16_t ax = 0, ay = 0, az = 0;
  Wire.beginTransmission(0x68);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) == 0 && Wire.requestFrom((int)0x68, 6) == 6) {
    uint8_t ax_h = Wire.read(); uint8_t ax_l = Wire.read();
    uint8_t ay_h = Wire.read(); uint8_t ay_l = Wire.read();
    uint8_t az_h = Wire.read(); uint8_t az_l = Wire.read();
    ax = (int16_t)((ax_h << 8) | ax_l);
    ay = (int16_t)((ay_h << 8) | ay_l);
    az = (int16_t)((az_h << 8) | az_l);
  }
  
  // 3. Print aligned tabular output
  Serial.printf("     %4d    |     %4d    |     %4d    |     %4d    |     %4d    | [%5.2f, %5.2f, %5.2f]\n",
    raw[0], raw[1], raw[2], raw[3], raw[4],
    ax / 16384.0f, ay / 16384.0f, az / 16384.0f);
    
  delay(100);
}
