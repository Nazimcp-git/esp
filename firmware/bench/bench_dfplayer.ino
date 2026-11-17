// bench_dfplayer.ino  (Stage 5 bench validation)
// Verifies:
// 1. DFPlayer Mini serial communication over Serial2 (GPIO 16 RX, GPIO 17 TX via 1k resistor)
// 2. FAT32 microSD card recognition and /MP3/0001.mp3 playback
// 3. Audio clarity and power stability without ESP32 brownouts

#include <DFRobotDFPlayerMini.h>

HardwareSerial dfSerial(2);
DFRobotDFPlayerMini dfp;

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("=== DFPlayer Mini Bench Test ===");
  
  dfSerial.begin(9600, SERIAL_8N1, 16, 17);   // RX=16, TX=17
  
  if (!dfp.begin(dfSerial)) {
    Serial.println("DFPlayer NOT found!");
    Serial.println("Troubleshooting checks:");
    Serial.println("1. 1k resistor placed in series on ESP32 TX (GPIO 17) -> DFPlayer RX");
    Serial.println("2. TX/RX not swapped");
    Serial.println("3. MicroSD card formatted as FAT32 with /MP3/0001.mp3 file present");
    Serial.println("4. 5V (VIN) rail powered properly with 470uF + 100nF decoupling capacitors");
    while (true) delay(1000);
  }
  
  Serial.println("DFPlayer Mini initialized successfully.");
  dfp.volume(20);          // Volume range: 0 to 30
  delay(500);
  Serial.println("Playing track 1: /MP3/0001.mp3 ...");
  dfp.playMp3Folder(1);    // Plays /MP3/0001.mp3
}

void loop() {
  // Idle loop
}

