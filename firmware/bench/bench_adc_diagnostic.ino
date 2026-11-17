// bench_adc_diagnostic.ino  --  Instant ADC Diagnostic & Voltage Tester
// Upload this sketch to test your ESP32 analog pins directly.

void setup() {
  Serial.begin(115200);
  delay(1000);
  Serial.println("\n=======================================================");
  Serial.println("  ESP32 ADC HARDWARE DIAGNOSTIC TEST");
  Serial.println("=======================================================");
  Serial.println("Expected counts:");
  Serial.println("  - When flex sensor is flat (unbent): ~1170 counts");
  Serial.println("  - When flex sensor is bent (fist):   ~480 counts");
  Serial.println("  - If all read 0: Flex sensors have NO 3.3V POWER!");
  Serial.println("-------------------------------------------------------\n");
}

void loop() {
  // Read all ADC1 pins directly (12-bit, default 0..4095 counts)
  int g36 = analogRead(36); // VP
  int g39 = analogRead(39); // VN
  int g34 = analogRead(34);
  int g35 = analogRead(35);
  int g32 = analogRead(32);
  int g33 = analogRead(33);

  Serial.printf("GPIO36(VP): %4d | GPIO33: %4d | GPIO32: %4d | GPIO35: %4d | GPIO34: %4d | GPIO39: %4d\n",
    g36, g33, g32, g35, g34, g39);
    
  delay(250);
}
