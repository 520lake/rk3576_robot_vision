#include <Wire.h>
#include <Adafruit_SSD1306.h>

#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Declaration for an SSD1306 display connected to I2C (SDA, SCL pins)
#define OLED_RESET     -1 // Reset pin # (or -1 if sharing Arduino reset pin)
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// Memory check helper for AVR (Arduino Uno R3)
// If you are using Uno R4, you can comment this function out if it causes errors,
// but R4 has 32KB RAM so memory is rarely the issue.
int freeRam () {
  extern int __heap_start, *__brkval;
  int v;
  return (int) &v - (__brkval == 0 ? (int) &__heap_start : (int) __brkval);
}

void setup() {
  Serial.begin(115200);
  
  // 1. Ultra-Low Speed I2C for Stability
  // Lowering to 50kHz helps with long wires or noise
  Wire.begin();
  Wire.setClock(50000); 
  Serial.println(F("I2C Clock set to 50kHz (High Stability Mode)"));
  
  // 2. RAM Check
  Serial.print(F("Free RAM before display init: "));
  Serial.println(freeRam());
  
  // 3. Robust Display Init
  // Try 0x3C first, then 0x3D
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) { 
    Serial.println(F("Address 0x3C failed, trying 0x3D..."));
    if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      Serial.println(F("[FATAL] SSD1306 allocation failed (Both addresses)"));
      // Blink LED to indicate failure
      pinMode(13, OUTPUT);
      while(1) {
        digitalWrite(13, HIGH); delay(100);
        digitalWrite(13, LOW); delay(100);
      }
    } else {
      Serial.println(F("SSD1306 found at 0x3D"));
    }
  } else {
    Serial.println(F("SSD1306 found at 0x3C"));
  }

  Serial.print(F("Free RAM after display init: "));
  Serial.println(freeRam());

  // 4. Visual Init & Test Prep
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  display.setCursor(0,0);
  display.println(F("I2C STABILITY TEST"));
  display.println(F("Speed: 50kHz"));
  display.println(F("----------------"));
  display.println(F("Check for blink..."));
  display.display();
}

void loop() {
  // Visual Heartbeat: Invert Colors
  // If the screen freezes or shows static, I2C is crashing.
  // If it blinks black/white rhythmically, I2C is healthy.
  
  Serial.println(F("Inverting: TRUE (White Background)"));
  display.invertDisplay(true);
  delay(1000); 
  
  Serial.println(F("Inverting: FALSE (Black Background)"));
  display.invertDisplay(false);
  delay(1000);
}
