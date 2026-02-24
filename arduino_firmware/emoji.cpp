#include "emoji.h"

// --- Visual Constants ---
const int EYE_RADIUS = 16;         // Big round eyes
const int EYE_SPACING = 36;        // Distance between centers
const int CENTER_X = 64;
const int CENTER_Y = 32;

// --- State Variables ---
String current_mood = "normal";
int gaze_x = 0; // -15 to 15
int gaze_y = 0; // -10 to 10

// Blink State
unsigned long last_blink_time = 0;
int blink_interval = 3000; // Randomize this later
bool is_blinking = false;
int blink_phase = 0; // 0: Open, 1: Closing, 2: Closed, 3: Opening

// Sleep Animation State
int zzz_frame = 0;
unsigned long last_zzz_time = 0;

void setup_emoji() {
  // Use SSD1306_SWITCHCAPVCC to generate display voltage from 3.3V internally
  // Lower frequency to 100kHz for stability against servo noise
  Wire.setClock(100000); 
  
  // Robust Allocation Strategy: Try 0x3C first, then 0x3D
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    Serial.println(F("Address 0x3C failed, trying 0x3D..."));
    if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3D)) {
       Serial.println(F("[FATAL] SSD1306 Allocation Failed on both addresses."));
       return;
    } else {
       Serial.println(F("SSD1306 found at 0x3D"));
    }
  } else {
     Serial.println(F("SSD1306 found at 0x3C"));
  }
  
  // Force Display ON immediately
  display.ssd1306_command(SSD1306_DISPLAYON);
  
  // Set Color Early
  display.setTextColor(SSD1306_WHITE);
  display.setTextSize(2);
  
  // Safety Clear
  display.clearDisplay();
  display.display();
  
  delay(100); // Wait for screen power
  
  // Brutal Clear: Fill screen with black to overwrite any random RAM noise
  display.fillScreen(SSD1306_BLACK);
  display.display();
  delay(50);
  
  // Clear again via standard method
  display.clearDisplay();
  display.display();

  Serial.println(F("SSD1306 is Ready (Force ON)."));
  
  // REMOVED: display.dim(true) - causing black screen issues
}

void draw_eye_shape(int x, int y, int r, int h_squeeze) {
  // Helper to draw eyes with squeeze (for blinking)
  if (h_squeeze <= 0) {
    // Closed - Draw line
    display.drawLine(x - r, y, x + r, y, SSD1306_WHITE);
    display.drawLine(x - r, y+1, x + r, y+1, SSD1306_WHITE); // Thicker
  } else if (h_squeeze >= r) {
    // Open - Circle
    display.fillCircle(x, y, r, SSD1306_WHITE);
  } else {
    // Ellipse (Simulated by filled round rect or multiple circles? SSD1306 doesn't have fillEllipse)
    // We can use fillRoundRect for oval-ish shape or draw multiple lines
    // Better: fillCircle and clear top/bottom? No.
    // Use fillRect? No.
    // Let's use fillCircle with radius r, but constrained by height?
    // Actually, simple scaling:
    // Adafruit GFX doesn't support scaling.
    // We will draw a flattened circle using lines for performance or just fillRect with rounded corners.
    // Let's use fillRoundRect which looks like an ellipse if w > h
    display.fillRoundRect(x - r, y - h_squeeze, r * 2, h_squeeze * 2, h_squeeze, SSD1306_WHITE);
  }
}

void draw_happy_eye(int x, int y) {
  // Inverted Crescent ^
  // Method: Draw White Circle, Mask Bottom with Black Circle
  // Or: Draw two lines for simple ^
  // High quality: White Circle (R) at (x, y), Black Circle (R-2) at (x, y+3)
  // But we want ^ shape which is an arch.
  // Draw White Circle
  display.fillCircle(x, y, EYE_RADIUS, SSD1306_WHITE);
  // Mask bottom part to make it an arch
  display.fillCircle(x, y + 5, EYE_RADIUS - 2, SSD1306_BLACK); // Shifted down mask
  // Mask bottom flatly?
  display.fillRect(x - EYE_RADIUS, y + 5, EYE_RADIUS * 2, EYE_RADIUS, SSD1306_BLACK);
}

void draw_zzz() {
  if (millis() - last_zzz_time > 500) {
    zzz_frame = (zzz_frame + 1) % 3;
    last_zzz_time = millis();
  }
  
  int start_x = 100;
  int start_y = 20;
  
  if (zzz_frame >= 0) display.setCursor(start_x, start_y);
  if (zzz_frame == 0) display.print("z");
  
  if (zzz_frame >= 1) display.setCursor(start_x + 8, start_y - 8);
  if (zzz_frame == 1) display.print("Z");
  
  if (zzz_frame >= 2) display.setCursor(start_x + 16, start_y - 16);
  if (zzz_frame == 2) display.print("Z");
}

void emoji_update() {
  display.clearDisplay();
  
  int lx = CENTER_X - EYE_SPACING / 2 + gaze_x;
  int rx = CENTER_X + EYE_SPACING / 2 + gaze_x;
  int ly = CENTER_Y + gaze_y;
  int ry = CENTER_Y + gaze_y;
  
  // --- Mood Handling ---
  if (current_mood == "sleep") {
    // Sleep: Closed eyes + Zzz
    draw_eye_shape(lx, ly, EYE_RADIUS, 0); // Closed
    draw_eye_shape(rx, ry, EYE_RADIUS, 0); // Closed
    draw_zzz();
  }
  else if (current_mood == "happy") {
    draw_happy_eye(lx, ly);
    draw_happy_eye(rx, ry);
  }
  else if (current_mood == "confused") {
    // Left eye big, Right eye small
    display.fillCircle(lx, ly, EYE_RADIUS, SSD1306_WHITE);
    display.fillCircle(rx, ry, EYE_RADIUS / 2, SSD1306_WHITE);
    // Maybe one eyebrow raised?
    display.drawLine(lx - 10, ly - 20, lx + 10, ly - 25, SSD1306_WHITE);
  }
  else {
    // Normal / Blinking
    // Handle Blinking Logic
    if (!is_blinking) {
      if (millis() - last_blink_time > blink_interval) {
        is_blinking = true;
        blink_phase = 1;
        blink_interval = random(2000, 5000); // Next blink time
      }
    }
    
    int current_h = EYE_RADIUS;
    
    if (is_blinking) {
      if (blink_phase == 1) { // Closing
        current_h = 4; // Almost closed
        blink_phase = 2;
      } else if (blink_phase == 2) { // Closed
        current_h = 0;
        blink_phase = 3;
      } else if (blink_phase == 3) { // Opening
        current_h = EYE_RADIUS;
        blink_phase = 0;
        is_blinking = false;
        last_blink_time = millis();
      }
    }
    
    draw_eye_shape(lx, ly, EYE_RADIUS, current_h);
    draw_eye_shape(rx, ry, EYE_RADIUS, current_h);
  }
  
  display.display();
}

void set_mood(String mood) {
  current_mood = mood;
  // Reset blink if normal
  if (mood == "normal") {
    last_blink_time = millis();
    is_blinking = false;
  }
}

void look_at(int x, int y) {
  gaze_x = x;
  gaze_y = y;
}
