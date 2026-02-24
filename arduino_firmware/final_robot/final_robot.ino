/*
 * FINAL STABLE ROBOT FIRMWARE
 * Architecture: Single File, Blocking Smooth Movement, Safe Startup
 * Hardware: Arduino Uno R4/R3 + SSD1306 OLED + 2x SG90 Servos
 * 
 * Features:
 * - Anti-Brownout Startup Sequence
 * - Blocking Smooth Movement (No current spikes)
 * - USB Serial Communication (115200 baud)
 * - "High Moe" Eyes (fillCircle)
 */

#include <Servo.h>
#include <Wire.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// --- Configuration ---
#define X_PIN 9
#define Y_PIN 10
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64
#define OLED_RESET -1

// --- Global Objects ---
Servo servo_x;
Servo servo_y;
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, OLED_RESET);

// --- State Variables ---
int current_x = 90;
int current_y = 90;
String inputString = "";
unsigned long last_act_time = 0;
String current_mood = "normal";

// --- Function Prototypes ---
void smooth_move(int target_x, int target_y, int speed_delay);
void draw_mood(String mood);

// --- SETUP (Strict Sequencing) ---
void setup() {
  // 1. Power Indicator & Serial
  pinMode(13, OUTPUT);
  digitalWrite(13, HIGH); // LED ON = Booting
  Serial.begin(115200);
  
  // 2. I2C Stability (100kHz)
  Wire.begin();
  Wire.setClock(100000); 

  // 3. Screen Initialization (Try 0x3C, then 0x3D)
  if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    if(!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
      Serial.println(F("[FATAL] OLED Not Found"));
      while(1); // Halt
    }
  }

  // 4. Force Screen ON & Clear
  display.ssd1306_command(SSD1306_DISPLAYON);
  display.clearDisplay();
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  display.setCursor(10, 20);
  display.println(F("Init..."));
  display.display();

  // 5. Capacitor Charge Delay (Crucial for Brown-out prevention)
  delay(2000); 
  digitalWrite(13, LOW); // LED OFF = Ready

  // 6. Attach Servos (Late Attach)
  // Move to center instantly? No, attach at default (usually 90) then sync
  servo_x.attach(X_PIN);
  servo_x.write(90);
  delay(200); // Stagger attach
  servo_y.attach(Y_PIN);
  servo_y.write(90); // Start at 90
  
  current_x = 90;
  current_y = 90;
  
  // 7. Initial Mood
  draw_mood("normal");
  
  Serial.println(F("Robot Ready"));
  last_act_time = millis();
}

// --- MAIN LOOP ---
void loop() {
  // 1. Serial Command Parsing
  while (Serial.available()) {
    char c = (char)Serial.read();
    if (c == '\n') {
      inputString.trim();
      
      if (inputString.startsWith("Move:")) {
        // Format: Move:90,90
        int commaIndex = inputString.indexOf(',');
        if (commaIndex > 0) {
          int tx = inputString.substring(5, commaIndex).toInt();
          int ty = inputString.substring(commaIndex + 1).toInt();
          // Use Blocking Smooth Move (Safe)
          smooth_move(tx, ty, 10); // 10ms/deg speed
        }
      }
      else if (inputString.startsWith("Emoji:")) {
        // Format: Emoji:happy
        String name = inputString.substring(6);
        draw_mood(name);
      }
      
      inputString = "";
      last_act_time = millis(); // Reset idle timer
    } 
    else {
      inputString += c;
    }
  }

  // 2. Idle Behavior (Non-blocking trigger, blocking action)
  if (millis() - last_act_time > 3000) {
    int r = random(0, 100);
    
    // 5% chance to blink
    if (r < 5) {
      draw_mood("blink");
      delay(100);
      draw_mood(current_mood); // Restore previous mood
    }
    // 2% chance to micro-move (Saccade)
    else if (r < 7) {
      int dx = random(-5, 6); // -5 to +5 degrees
      int dy = random(-5, 6);
      
      // Calculate safe target
      int tx = constrain(current_x + dx, 20, 160);
      int ty = constrain(current_y + dy, 20, 160);
      
      smooth_move(tx, ty, 20); // Slower for subtle movement
    }
    
    last_act_time = millis(); // Reset timer
  }
}

// --- CORE: Blocking Smooth Movement ---
// Moves 1 degree at a time with delay to limit current
void smooth_move(int target_x, int target_y, int speed_delay) {
  // Safety Constraints
  target_x = constrain(target_x, 0, 180);
  target_y = constrain(target_y, 0, 180);

  // Move until both axes reach target
  while (current_x != target_x || current_y != target_y) {
    
    // Step X
    if (current_x < target_x) current_x++;
    else if (current_x > target_x) current_x--;
    
    // Step Y
    if (current_y < target_y) current_y++;
    else if (current_y > target_y) current_y--;

    // Hardware Write
    servo_x.write(current_x);
    servo_y.write(current_y);
    
    // Wait (Current Limiting)
    delay(speed_delay);
  }
}

// --- VISUAL: Mood Rendering ---
void draw_eyes(int open_h) {
  display.clearDisplay();
  
  int eye_r = 16;
  int eye_y = 32;
  int left_x = 32;
  int right_x = 96;
  
  // Draw Left Eye
  if (open_h >= eye_r) display.fillCircle(left_x, eye_y, eye_r, SSD1306_WHITE);
  else display.fillRect(left_x - eye_r, eye_y - open_h, eye_r * 2, open_h * 2, SSD1306_WHITE);
  
  // Draw Right Eye
  if (open_h >= eye_r) display.fillCircle(right_x, eye_y, eye_r, SSD1306_WHITE);
  else display.fillRect(right_x - eye_r, eye_y - open_h, eye_r * 2, open_h * 2, SSD1306_WHITE);
  
  display.display();
}

void draw_mood(String mood) {
  current_mood = mood;
  display.clearDisplay();
  
  int eye_y = 32;
  
  if (mood == "normal" || mood == "confused") {
    // Normal Round Eyes
    display.fillCircle(32, eye_y, 16, SSD1306_WHITE);
    display.fillCircle(96, eye_y, 16, SSD1306_WHITE);
    if (mood == "confused") {
      // One eye smaller or eyebrow? Let's offset one eye
      display.fillCircle(96, eye_y, 16, SSD1306_BLACK); // Erase right
      display.fillCircle(96, eye_y - 5, 12, SSD1306_WHITE); // Draw smaller higher
    }
  }
  else if (mood == "blink") {
    // Flat lines
    display.fillRect(16, eye_y, 32, 4, SSD1306_WHITE);
    display.fillRect(80, eye_y, 32, 4, SSD1306_WHITE);
  }
  else if (mood == "happy") {
    // Arches (Circle masked by lower rectangle)
    display.fillCircle(32, eye_y, 16, SSD1306_WHITE);
    display.fillCircle(96, eye_y, 16, SSD1306_WHITE);
    display.fillRect(0, eye_y + 4, 128, 32, SSD1306_BLACK); // Mask bottom
  }
  else if (mood == "sleep") {
    // Zzz text
    display.setTextSize(2);
    display.setCursor(40, 20);
    display.print("z");
    display.setCursor(60, 10);
    display.print("Z");
  }
  
  display.display();
}
