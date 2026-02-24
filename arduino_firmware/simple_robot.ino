#include <Arduino.h>
#include <Wire.h>
#include <Servo.h>
#include <Adafruit_SSD1306.h>

#include "common.h"
#include "emoji.h"
#include "head.h"

// --- Global Instances ---
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);
Servo servo_x;
Servo servo_y;

// --- Communication ---
String inputString = "";
bool stringComplete = false;

// --- Idle State ---
unsigned long last_cmd_time = 0;
const unsigned long IDLE_TIMEOUT = 5000;
bool is_idle = true; // Start in idle

// --- Saccade State ---
unsigned long last_saccade_time = 0;
int saccade_interval = 3000;

void setup() {
  // Step 0: LED Debug (Check MCU Liveness)
  pinMode(13, OUTPUT);
  digitalWrite(13, HIGH); // LED ON = Booting
  
  // Step 1: Serial & Screen Init
  Serial.begin(115200);
  setup_emoji();
  
  // Step 2: Visual Feedback
  display.clearDisplay();
  display.setCursor(0, 0);
  display.println(F("System Init..."));
  display.display();
  
  // Step 3: Power Stabilization (Charge capacitors)
  delay(2000); 
  digitalWrite(13, LOW); // LED OFF = Power Stable, Moving Servos
  
  // Step 4: Staggered Servo Start (Prevent Brown-out)
  // X Axis First
  servo_x.attach(X_PIN);
  servo_x.write(90);
  delay(500); // Wait for X current to settle
  
  // Y Axis Second
  servo_y.attach(Y_PIN);
  servo_y.write(70); // 70 is safe angle
  
  // Sync Internal State (Limits & Position)
  head_trim(0, 0);   // Forces update_limits()
  head_test(90, 70); // Syncs current_x/y variables
  
  Serial.println(F("Robot Ready"));
  inputString.reserve(50);
  last_cmd_time = millis();
}

void parseCommand(String cmd) {
  cmd.trim();
  
  if (cmd.startsWith("Move:")) {
    // Move:10,-20 (Relative or Absolute? Let's assume absolute target for simplicity in new logic, 
    // OR relative if that's what the python app sends. The previous code did relative constrain.
    // Let's stick to the previous behavior: Python sent offsets? 
    // Previous code: moveServos(xStr.toInt(), yStr.toInt()) which did current + off.
    // Let's support Absolute for better control or Relative?
    // Let's assume the Python script sends RELATIVE offsets as per previous "Move:10,-20".
    
    int firstColon = cmd.indexOf(':');
    int comma = cmd.indexOf(',');
    if (firstColon > 0 && comma > firstColon) {
      int dx = cmd.substring(firstColon + 1, comma).toInt();
      int dy = cmd.substring(comma + 1).toInt();
      
      // Get current target, add offset, set new target
      // We need to access current target from head? 
      // Or just get current pos.
      // Better to have head_move_rel exposed? 
      // For now, let's just get current position and add.
      head_set_target(head_get_x() + dx, head_get_y() + dy);
    }
  } 
  else if (cmd.startsWith("Emoji:")) {
    String name = cmd.substring(cmd.indexOf(':') + 1);
    set_mood(name);
  } else if (cmd.startsWith("Test:")) {
    // Test:90,90
    int firstColon = cmd.indexOf(':');
    int comma = cmd.indexOf(',');
    if (firstColon > 0 && comma > firstColon) {
      int tx = cmd.substring(firstColon + 1, comma).toInt();
      int ty = cmd.substring(comma + 1).toInt();
      head_test(tx, ty);
      Serial.print(F("Test Angle: "));
      Serial.print(tx);
      Serial.print(",");
      Serial.println(ty);
    }
  } else if (cmd.startsWith("Trim:")) {
    // Trim:0,-10
    int firstColon = cmd.indexOf(':');
    int comma = cmd.indexOf(',');
    if (firstColon > 0 && comma > firstColon) {
      int tx = cmd.substring(firstColon + 1, comma).toInt();
      int ty = cmd.substring(comma + 1).toInt();
      head_trim(tx, ty);
      Serial.print(F("Trim Applied: "));
      Serial.print(tx);
      Serial.print(",");
      Serial.println(ty);
    }
  }
}

void idle_behavior() {
  unsigned long now = millis();
  
  // 1. Breathing (Sine Wave)
  // Period 3s = 3000ms. 2PI in 3000ms.
  float angle = (now % 3000) / 3000.0 * 2.0 * PI;
  int y_offset = 3 * sin(angle); // Amplitude +/- 3 degrees
  head_set_breathing(y_offset);
  
  // 2. Saccades (Random Glances)
  if (now - last_saccade_time > saccade_interval) {
    last_saccade_time = now;
    saccade_interval = random(2000, 6000);
    
    // 30% chance to move head, 70% chance to just move eyes
    int r = random(0, 100);
    
    if (r < 30) {
      // Move Head slightly
      int rand_x = X_CENTER + random(-15, 16);
      int rand_y = Y_CENTER + random(-10, 11);
      head_set_target(rand_x, rand_y);
      // Reset eyes
      look_at(0, 0);
    } else {
      // Just move eyes
      int ex = random(-10, 11);
      int ey = random(-5, 6);
      look_at(ex, ey);
      // Center head slowly
      head_set_target(X_CENTER, Y_CENTER);
    }
  }
}

void loop() {
  // 1. Serial Input (Non-blocking)
  while (Serial.available()) {
    char inChar = (char)Serial.read();
    inputString += inChar;
    if (inChar == '\n') {
      stringComplete = true;
    }
  }
  
  if (stringComplete) {
    parseCommand(inputString);
    inputString = "";
    stringComplete = false;
    last_cmd_time = millis();
    
    if (is_idle) {
      is_idle = false;
      set_mood("normal");
      head_set_breathing(0); // Stop breathing offset
      head_set_target(X_CENTER, Y_CENTER);
      Serial.println(F("Wakeup"));
    }
  }
  
  // 2. Idle Check
  if (!is_idle && (millis() - last_cmd_time > IDLE_TIMEOUT)) {
    is_idle = true;
    set_mood("normal");
    Serial.println(F("Idle"));
  }
  
  // 3. Logic Update
  if (is_idle) {
    idle_behavior();
  }
  
  // 4. Hardware Update (Animation & Servo)
  head_update();
  emoji_update();
}
