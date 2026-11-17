// glove_esp32.ino  --  Sign Language Glove Firmware
// Microcontroller: ESP32 DevKit V1
// Circuit: 10k pull-down flex dividers (Thumb..Pinky on ADC1), MPU6050 I2C
// (DFPlayer Mini & hardware speaker removed - audio speech synthesis handled via Web Portal / Phone)
//
// FEATURES:
// 1. STANDALONE EDGE AI: 60-tree Random Forest running in ESP32 Flash memory
//    - Zero cloud or phone required for gesture recognition (< 1 ms latency)
//    - Instant recognition output via Serial Monitor
// 2. AUTO-TARE CALIBRATION: Automatically measures resting flat-hand baseline on boot
// 3. LOW-LATENCY UDP STREAMING: 20 Hz telemetry to PC / 3D WebGL viewer (port 4210)
// 4. CLOUD SYNC: Direct HTTPS upload to Firebase Realtime Database (phrases & live telemetry)
//    - Connected phone / laptop web app announces phrases aloud via Web Speech API

#include <WiFi.h>
#include <WiFiUdp.h>
#include <Wire.h>
#include <WiFiClientSecure.h>
#include <HTTPClient.h>

// Include the compiled Random Forest Edge AI model
#include "model_data.h"

// ==============================================================================
// 1. CONFIGURATION & NETWORK SETTINGS
// ==============================================================================
const char*    WIFI_SSID          = "abspl_2.4G";      // 2.4 GHz Wi-Fi or Phone Hotspot
const char*    WIFI_PASS          = "12345678";
const char*    TARGET_IP_OVERRIDE = "192.168.1.16";  // Your laptop IP for 3D viewer (192.168.1.16); "" = auto
const uint16_t PORT_DATA          = 4210;              // ESP32 -> Receiver (UDP)
const uint16_t PORT_CMD           = 4211;              // Receiver -> ESP32 (UDP)
IPAddress      dynamicTargetIp(0, 0, 0, 0);            // Auto-learned when receiver pings PORT_CMD

// ==============================================================================
// 2. HARDWARE PIN DEFINITIONS (Strictly ADC1 for Flex Sensors)
// ==============================================================================
// Matched to circuit wiring:
// Thumb  = GPIO 36 (VP / ADC1_CH0)  [Light Cyan wire]
// Index  = GPIO 33 (ADC1_CH5)        [Magenta wire]
// Middle = GPIO 32 (ADC1_CH4)        [Green wire]
// Ring   = GPIO 35 (ADC1_CH7)        [Slate Blue wire]
// Pinky  = GPIO 34 (ADC1_CH6)        [Peach wire]
const uint8_t FLEX_PINS[5] = {36, 33, 32, 35, 34};
const char* const FINGER_NAMES[5] = {"Thumb", "Index", "Middle", "Ring", "Pinky"};

// I2C Pins for MPU6050
const uint8_t PIN_SDA   = 21;                          // Yellow wire to MPU SDA
const uint8_t PIN_SCL   = 22;                          // Blue wire to MPU SCL
const uint8_t MPU_ADDR  = 0x68;

// Status LED
const uint8_t PIN_LED   = 2;

// ==============================================================================
// 3. CALIBRATION & VOLTAGE DIVIDER CONSTANTS
// ==============================================================================
// With 10k pull-down resistors (flex sensor between 3.3V and ADC, 10k to GND):
// - Flat unbent flex (~25k): V_adc ~ 0.94V -> ADC count ~ 1170
// - Bent fist flex   (~75k): V_adc ~ 0.39V -> ADC count ~ 480
// - Dynamic swing: ~690 counts (voltage drops on bending)
float calibOpen[5] = {1170.0f, 1170.0f, 1170.0f, 1170.0f, 1170.0f};
float calibFist[5] = {480.0f,  480.0f,  480.0f,  480.0f,  480.0f};
const float EXPECTED_BEND_DELTA = 690.0f; // Expected drop from flat to full curl

// ==============================================================================
// 4. FIREBASE REALTIME DATABASE CONFIGURATION
// ==============================================================================
const bool     ENABLE_FIREBASE_UPLOAD = true;
const char*    FIREBASE_DB_URL        = "https://shopping-e284c-default-rtdb.firebaseio.com";
const char*    FIREBASE_AUTH_KEY      = "AIzaSyBXJ_RnfjUDi7qPDATWVnS5lSFw6jVRYgo";
const bool     ENABLE_LIVE_TELEMETRY  = false;         // Disabled during UDP bench testing to eliminate 2s TLS freezes
const uint32_t TELEMETRY_INTERVAL_MS  = 2000;

// ==============================================================================
// 5. TIMING & FILTERING
// ==============================================================================
const uint32_t SAMPLE_MS  = 10;                        // 100 Hz internal sensor sample rate
const uint32_t SEND_MS    = 50;                        // 20 Hz AI inference and UDP tick
const float    ALPHA_FLEX = 0.30f;                     // EMA smoothing (0..1)
const float    ALPHA_IMU  = 0.50f;

// Runtime state
WiFiUDP udp;

bool imuOk  = false;
bool primed = false;
bool wasUp  = false;

float flexS[5] = {0};
float imuS[6]  = {0};

uint32_t seqNo      = 0;
uint32_t tSample    = 0;
uint32_t tSend      = 0;
uint32_t tWifi      = 0;
uint32_t tStat      = 0;
uint32_t tTelemetry = 0;

// Rolling window buffer for TinyML Edge Recognizer
float winBuffer[RF_WINDOW_SIZE][11];
int   winHead     = 0;
int   winFilled   = 0;
int   stepCounter = 0;
EdgeRecognizer recognizer;

// ==============================================================================
// 6. MPU6050 DIRECT I2C DRIVER (No external library required)
// ==============================================================================
bool i2cWrite(uint8_t reg, uint8_t val) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(reg);
  Wire.write(val);
  return Wire.endTransmission() == 0;
}

bool mpuInit() {
  if (!i2cWrite(0x6B, 0x00)) return false; // Wake up device
  i2cWrite(0x1A, 0x03);                     // DLPF ~44 Hz bandwidth
  i2cWrite(0x1B, 0x00);                     // Gyro +/- 250 deg/s
  i2cWrite(0x1C, 0x00);                     // Accel +/- 2 g
  return true;
}

bool mpuRead(float v[6]) {
  Wire.beginTransmission(MPU_ADDR);
  Wire.write(0x3B);
  if (Wire.endTransmission(false) != 0) return false;
  if (Wire.requestFrom((int)MPU_ADDR, 14) != 14) return false;
  
  int16_t r[7];
  for (int i = 0; i < 7; i++) {
    uint8_t hi = Wire.read();
    uint8_t lo = Wire.read();
    r[i] = (int16_t)((hi << 8) | lo);
  }
  
  // Acceleration in g (16384 LSB/g)
  v[0] = r[0] / 16384.0f; // ax
  v[1] = r[1] / 16384.0f; // ay
  v[2] = r[2] / 16384.0f; // az
  
  // Gyroscope in deg/s (131 LSB/(deg/s))
  v[3] = r[4] / 131.0f;   // gx
  v[4] = r[5] / 131.0f;   // gy
  v[5] = r[6] / 131.0f;   // gz
  
  return true;
}

// ==============================================================================
// 7. AUTO-TARE & SENSOR SAMPLING
// ==============================================================================
void tareRestingBaseline() {
  Serial.println("\n[TARE] Calibrating resting open-hand baseline (keep hand flat)...");
  delay(600); // Allow ADC analog lines and power rails to settle
  float sum[5] = {0};
  const int TARE_SAMPLES = 40;
  
  for (int s = 0; s < TARE_SAMPLES; s++) {
    for (int i = 0; i < 5; i++) {
      int a = 0;
      for (int k = 0; k < 4; k++) a += analogRead(FLEX_PINS[i]);
      sum[i] += a / 4.0f;
    }
    delay(15);
  }
  
  for (int i = 0; i < 5; i++) {
    float avg = sum[i] / (float)TARE_SAMPLES;
    if (avg < 150.0f) {
      // Pin is reading near 0 counts -> disconnected or unpowered!
      // Do not zero baseline to 0, use theoretical flat unbent baseline (1170)
      calibOpen[i] = 1170.0f;
      calibFist[i] = 480.0f;
      Serial.printf("[TARE] %s (GPIO %d): DISCONNECTED (0V) -> baseline set to default 1170\n",
        FINGER_NAMES[i], FLEX_PINS[i]);
    } else {
      calibOpen[i] = avg;
      calibFist[i] = calibOpen[i] - EXPECTED_BEND_DELTA;
      if (calibFist[i] < 50.0f) calibFist[i] = 50.0f;
    }
    flexS[i] = avg;
  }
  
  Serial.printf("[TARE] Open Hand Baseline: Th=%.0f, In=%.0f, Mid=%.0f, Rng=%.0f, Pnk=%.0f\n",
    calibOpen[0], calibOpen[1], calibOpen[2], calibOpen[3], calibOpen[4]);
  Serial.println("[TARE] Ready! Bend any connected finger to see Δ and Bends rise.\n");
}

void sampleSensors() {
  for (int i = 0; i < 5; i++) {
    int s = 0;
    for (int k = 0; k < 4; k++) s += analogRead(FLEX_PINS[i]); // 4x oversampling
    float x = s / 4.0f;
    flexS[i] = primed ? flexS[i] + ALPHA_FLEX * (x - flexS[i]) : x;
  }
  
  float v[6];
  if (imuOk && mpuRead(v)) {
    for (int i = 0; i < 6; i++) {
      imuS[i] = primed ? imuS[i] + ALPHA_IMU * (v[i] - imuS[i]) : v[i];
    }
  }
  primed = true;
}

// ==============================================================================
// 8. FIREBASE REALTIME DATABASE DIRECT UPLOAD
// ==============================================================================
void uploadPhraseToFirebase(int classIdx) {
  if (!ENABLE_FIREBASE_UPLOAD || WiFi.status() != WL_CONNECTED) return;
  if (classIdx < 1 || classIdx >= RF_NUM_CLASSES) return;
  
  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(2500);
  
  HTTPClient https;
  String url = String(FIREBASE_DB_URL) + "/records.json";
  if (FIREBASE_AUTH_KEY[0] != '\0') {
    url += "?auth=" + String(FIREBASE_AUTH_KEY);
  }
  
  if (https.begin(client, url)) {
    https.addHeader("Content-Type", "application/json");
    https.setTimeout(2500);
    
    String jsonPayload = "{\"text\":\"" + String(RF_PHRASES[classIdx]) + "\","
                         "\"category\":\"" + String(RF_CATEGORIES[classIdx]) + "\","
                         "\"class\":\"" + String(RF_CLASSES[classIdx]) + "\","
                         "\"track\":" + String(classIdx) + ","
                         "\"status\":\"approved\","
                         "\"source\":\"onboard_ai_esp32\","
                         "\"timestamp\":{\".sv\":\"timestamp\"}}";
                         
    int code = https.POST(jsonPayload);
    if (code > 0) {
      Serial.printf("[FIREBASE] Synced phrase '%s' (HTTP %d)\n", RF_PHRASES[classIdx], code);
    } else {
      Serial.printf("[FIREBASE] Upload error: %s\n", https.errorToString(code).c_str());
    }
    https.end();
  }
}

void uploadTelemetryToFirebase() {
  if (!ENABLE_FIREBASE_UPLOAD || !ENABLE_LIVE_TELEMETRY || WiFi.status() != WL_CONNECTED) return;
  
  WiFiClientSecure client;
  client.setInsecure();
  client.setTimeout(1500);
  
  HTTPClient https;
  String url = String(FIREBASE_DB_URL) + "/live_telemetry.json";
  if (FIREBASE_AUTH_KEY[0] != '\0') {
    url += "?auth=" + String(FIREBASE_AUTH_KEY);
  }
  
  if (https.begin(client, url)) {
    https.addHeader("Content-Type", "application/json");
    https.setTimeout(1500);
    
    char payload[256];
    snprintf(payload, sizeof(payload),
      "{\"f1\":%.0f,\"f2\":%.0f,\"f3\":%.0f,\"f4\":%.0f,\"f5\":%.0f,"
      "\"ax\":%.3f,\"ay\":%.3f,\"az\":%.3f,\"gx\":%.1f,\"gy\":%.1f,\"gz\":%.1f,"
      "\"uptime_ms\":%lu,\"rssi\":%d,\"last_seen\":{\".sv\":\"timestamp\"}}",
      flexS[0], flexS[1], flexS[2], flexS[3], flexS[4],
      imuS[0], imuS[1], imuS[2], imuS[3], imuS[4], imuS[5],
      (unsigned long)millis(), WiFi.RSSI());
      
    https.PUT(payload);
    https.end();
  }
}

// ==============================================================================
// 9. ONBOARD EDGE AI INFERENCE
// ==============================================================================
void runOnboardInference() {
  // Push frame into rolling window
  for (int k = 0; k < 5; k++) winBuffer[winHead][k] = flexS[k];
  for (int k = 0; k < 3; k++) winBuffer[winHead][5 + k] = imuS[k];
  for (int k = 0; k < 3; k++) winBuffer[winHead][8 + k] = imuS[3 + k];
  
  winHead = (winHead + 1) % RF_WINDOW_SIZE;
  if (winFilled < RF_WINDOW_SIZE) {
    winFilled++;
    return;
  }
  
  stepCounter++;
  if (stepCounter < RF_STEP_SIZE) return; // Evaluate every 2 frames (10 times/s)
  stepCounter = 0;
  
  float winSeq[RF_WINDOW_SIZE][11];
  for (int i = 0; i < RF_WINDOW_SIZE; i++) {
    int srcIdx = (winHead + i) % RF_WINDOW_SIZE;
    for (int j = 0; j < 11; j++) {
      winSeq[i][j] = winBuffer[srcIdx][j];
    }
  }
  
  float feat[RF_NUM_FEATURES];
  float motion = 0.0f;
  rf_extract_features(winSeq, calibOpen, calibFist, feat, &motion);
  
  float proba[RF_NUM_CLASSES];
  rf_predict_proba(feat, proba);
  
  int fired = recognizer.update(proba, motion > RF_MOTION_MAX);
  if (fired > 0 && fired < RF_NUM_CLASSES) {
    Serial.println("\n**************************************************************");
    Serial.printf(" [ONBOARD AI] SIGN RECOGNIZED: '%s' -> Spoken: \"%s\"\n",
      RF_CLASSES[fired], RF_PHRASES[fired]);
    Serial.println("**************************************************************\n");
    
    // Direct cloud sync to Firebase RTDB (connected phone / web app speaks phrase aloud)
    uploadPhraseToFirebase(fired);
    
    // Broadcast recognition event over UDP so local 3D visualizer speaks immediately (zero-latency offline TTS)
    sendPhraseUDP(fired);
  }
}

// ==============================================================================
// 10. NETWORKING & UDP STREAMING
// ==============================================================================
void sendPhraseUDP(int classIdx) {
  if (WiFi.status() != WL_CONNECTED || classIdx < 1 || classIdx >= RF_NUM_CLASSES) return;
  char b[64];
  int n = snprintf(b, sizeof(b), "P,%d,%s\n", classIdx, RF_PHRASES[classIdx]);
  udp.beginPacket(targetIp(), PORT_DATA);
  udp.write((const uint8_t*)b, n);
  udp.endPacket();
  
  IPAddress bcast = WiFi.localIP();
  bcast[3] = 255;
  if (bcast != targetIp()) {
    udp.beginPacket(bcast, PORT_DATA);
    udp.write((const uint8_t*)b, n);
    udp.endPacket();
  }
}
IPAddress targetIp() {
  if (dynamicTargetIp[0] != 0) {
    return dynamicTargetIp; // Prioritize live active client that sent a handshake
  }
  IPAddress ip;
  if (TARGET_IP_OVERRIDE[0] != '\0' && ip.fromString(TARGET_IP_OVERRIDE)) {
    return ip;
  }
  return WiFi.gatewayIP(); // Default: phone hotspot host
}

void sendFrame() {
  char b[160];
  int n = snprintf(b, sizeof(b),
    "F,%lu,%lu,%.0f,%.0f,%.0f,%.0f,%.0f,%.3f,%.3f,%.3f,%.1f,%.1f,%.1f\n",
    (unsigned long)seqNo++, (unsigned long)millis(),
    flexS[0], flexS[1], flexS[2], flexS[3], flexS[4],
    imuS[0], imuS[1], imuS[2], imuS[3], imuS[4], imuS[5]);
    
  udp.beginPacket(targetIp(), PORT_DATA);
  udp.write((const uint8_t*)b, n);
  udp.endPacket();

  // Also broadcast across subnet so any computer on the network receives the 3D telemetry
  IPAddress bcast = WiFi.localIP();
  bcast[3] = 255;
  if (bcast != targetIp()) {
    udp.beginPacket(bcast, PORT_DATA);
    udp.write((const uint8_t*)b, n);
    udp.endPacket();
  }
}

void handleCommands() {
  int sz = udp.parsePacket();
  if (sz <= 0) return;
  
  // Auto-learn receiver IP from incoming packet
  IPAddress sender = udp.remoteIP();
  if (sender[0] != 0 && sender != dynamicTargetIp) {
    dynamicTargetIp = sender;
    Serial.printf("[UDP] Adopted active receiver IP: %s\n", dynamicTargetIp.toString().c_str());
  }

  char b[32];
  int n = udp.read(b, sizeof(b) - 1);
  if (n <= 0) return;
  b[n] = '\0';
  
  if (strncmp(b, "TARE", 4) == 0) {
    tareRestingBaseline();
  } else if (strncmp(b, "PLAY,", 5) == 0) {
    int t = atoi(b + 5);
    if (t >= 1 && t <= 99) {
      Serial.printf("[CMD] Remote trigger phrase %d ('%s')\n", t, (t < RF_NUM_CLASSES) ? RF_PHRASES[t] : "");
      uploadPhraseToFirebase(t);
    }
  }
}

void keepWifi(uint32_t now) {
  bool up = (WiFi.status() == WL_CONNECTED);
  if (up && !wasUp) {
    udp.begin(PORT_CMD);
    Serial.printf("\n[WIFI] Connected! Glove IP: %s | Target: %s\n", 
      WiFi.localIP().toString().c_str(), 
      targetIp().toString().c_str());
  }
  if (!up && wasUp) {
    Serial.println("\n[WIFI] Signal lost. Auto-reconnecting...");
  }
  wasUp = up;
  
  if (!up && (now - tWifi > 4000)) {
    tWifi = now;
    WiFi.reconnect(); // Fast hardware reconnection without resetting IP stack
  }
}

void updateLed(uint32_t now) {
  bool on;
  if (WiFi.status() != WL_CONNECTED) {
    on = (now / 200) % 2; // Fast blink = offline standalone mode
  } else if (!imuOk) {
    uint32_t p = now % 2000;
    on = (p < 100) || (p > 250 && p < 350); // Double blink = IMU warning
  } else {
    on = true; // Solid ON = connected and streaming
  }
  digitalWrite(PIN_LED, on);
}

// Check for user keyboard commands in Serial Monitor
void checkSerialInput() {
  if (!Serial.available()) return;
  char ch = Serial.read();
  
  if (ch == 't' || ch == 'T' || ch == 'c' || ch == 'C' || ch == '0') {
    tareRestingBaseline();
  } else if (ch >= '1' && ch <= '9') {
    int track = ch - '0';
    Serial.printf("[MANUAL TRIGGER] Triggered phrase %d ('%s')\n", track, RF_PHRASES[track]);
    uploadPhraseToFirebase(track);
  }
}

// ==============================================================================
// 11. SETUP & INITIALIZATION
// ==============================================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  
  Serial.println("\n========================================================");
  Serial.println("  SIGN LANGUAGE GLOVE FIRMWARE (ESP32 DevKit V1)");
  Serial.println("========================================================");
  
  pinMode(PIN_LED, OUTPUT);
  digitalWrite(PIN_LED, HIGH);
  
  // Configure 12-bit ADC resolution (0..4095 counts) and 11dB attenuation (~0 to 3.3V range)
  analogReadResolution(12);
  analogSetAttenuation(ADC_11db);

  // Set 11dB attenuation individually for each flex sensor pin to guarantee full voltage range
  for (int i = 0; i < 5; i++) {
    analogSetPinAttenuation(FLEX_PINS[i], ADC_11db);
  }
  
  // Initialize I2C bus for MPU6050
  Wire.begin(PIN_SDA, PIN_SCL);
  Wire.setClock(400000);
  imuOk = mpuInit();
  
  Serial.printf("[HARDWARE] IMU MPU6050:   %s (SDA=%d, SCL=%d)\n", imuOk ? "ONLINE" : "MISSING", PIN_SDA, PIN_SCL);
  
  // Verify embedded Edge AI parity
  Serial.print("[AI ENGINE] Testing Onboard Random Forest Flash Parity... ");
  if (run_embedded_parity_test()) {
    Serial.println("PASSED! (Zero drift vs Scikit-Learn)");
  } else {
    Serial.println("WARNING: Parity mismatch!");
  }
  
  // Auto-tare baseline with hand flat
  tareRestingBaseline();
  
  // Connect Wi-Fi with maximum radio power & auto-reconnect
  Serial.printf("[WIFI] Connecting to '%s'...\n", WIFI_SSID);
  WiFi.mode(WIFI_STA);
  WiFi.setSleep(false);
  WiFi.setTxPower(WIFI_POWER_19_5dBm); // Maximum radio transmit power (boosts range & SNR)
  WiFi.setAutoReconnect(true);        // Hardware-level instant auto-reconnect
  WiFi.persistent(true);
  WiFi.begin(WIFI_SSID, WIFI_PASS);
  
  Serial.println("\n[BENCH INSTRUCTIONS]:");
  Serial.println("  - Keep hand flat or send 't' in Serial Monitor to re-zero open hand");
  Serial.println("  - Bend each finger to see counts drop from ~1170 to ~480");
  Serial.println("  - Hold any sign steady for 0.4s to recognize gesture & sync to Firebase");
  Serial.println("----------------------------------------------------------------------------------\n");
}

// ==============================================================================
// 12. MAIN LOOP
// ==============================================================================
void loop() {
  uint32_t now = millis();
  
  // 1. 100 Hz sensor sampling
  if (now - tSample >= SAMPLE_MS) {
    tSample = now;
    sampleSensors();
  }
  
  // 2. 20 Hz tick: Run Edge AI Inference & Stream UDP Telemetry
  if (now - tSend >= SEND_MS) {
    tSend = now;
    
    // Always runs locally on glove (100% offline standalone capable)
    runOnboardInference();
    
    // Stream UDP to 3D visualizer if Wi-Fi connected
    if (WiFi.status() == WL_CONNECTED) {
      sendFrame();
    }
  }
  
  // 3. Network & Cloud Services
  if (WiFi.status() == WL_CONNECTED) {
    handleCommands();
    
    if (ENABLE_FIREBASE_UPLOAD && ENABLE_LIVE_TELEMETRY) {
      if (now - tTelemetry >= TELEMETRY_INTERVAL_MS) {
        tTelemetry = now;
        uploadTelemetryToFirebase();
      }
    }
  }
  
  keepWifi(now);
  updateLed(now);
  checkSerialInput();
  
  // 4. 1 Hz Serial Diagnostic Heartbeat
  if (now - tStat >= 1000) {
    tStat = now;
    
    // Compute bend percentages using Absolute Delta deviation from resting baseline
    int bendPct[5];
    int delta[5];
    char bendStr[5][8];
    for (int i = 0; i < 5; i++) {
      if (flexS[i] < 120.0f) {
        // Disconnected pin reading 0V
        delta[i] = 0;
        bendPct[i] = 0;
        snprintf(bendStr[i], sizeof(bendStr[i]), " DISC");
      } else {
        float d = fabsf(flexS[i] - calibOpen[i]);
        if (d < 35.0f) d = 0.0f; // Deadzone noise filter
        delta[i] = (int)d;
        // 500 counts of deviation = 100% full curl
        float pct = (d / 500.0f) * 100.0f;
        bendPct[i] = constrain((int)pct, 0, 100);
        snprintf(bendStr[i], sizeof(bendStr[i]), "%3d%%", bendPct[i]);
      }
    }
    
    Serial.printf("[DIAG] ADC: [Th:%.0f In:%.0f Mid:%.0f Rng:%.0f Pnk:%.0f] | Δ: [%3d %3d %3d %3d %3d] | Bends: [%s %s %s %s %s] | WiFi: %s\n",
      flexS[0], flexS[1], flexS[2], flexS[3], flexS[4],
      delta[0], delta[1], delta[2], delta[3], delta[4],
      bendStr[0], bendStr[1], bendStr[2], bendStr[3], bendStr[4],
      (WiFi.status() == WL_CONNECTED) ? "CONNECTED" : "OFFLINE");
  }
}
