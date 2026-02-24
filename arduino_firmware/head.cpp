#include "head.h"

// --- Servo Settings ---
int X_CENTER = 90;
int Y_CENTER = 90;
int X_MIN = 0; // Calculated in setup
int X_MAX = 180;
int Y_MIN = 0;
int Y_MAX = 180;

// State Variables
float current_x = 90.0;
float current_y = 70.0; // Start slightly down
int target_x = 90;
int target_y = 70;
int breathing_offset_y = 0;

unsigned long last_move_time = 0;
int move_interval = 10; // ms between steps (controls speed)
float move_step = 1.0;  // degrees per step

void update_limits() {
  X_MIN = X_CENTER - X_OFFSET;
  X_MAX = X_CENTER + X_OFFSET;
  Y_MIN = Y_CENTER - Y_OFFSET;
  Y_MAX = Y_CENTER + Y_OFFSET;
}

void setup_head() {
  // Use safe setup instead
  setup_head_safe();
}

void setup_head_safe() {
  // Safe Init Sequence
  servo_x.detach();
  servo_y.detach();
  delay(500); // Wait for power to stabilize
  
  servo_x.attach(X_PIN);
  servo_y.attach(Y_PIN);
  
  // Update limits based on initial center
  update_limits();
  
  // Initial Position (Safe Anti-Stall Angle)
  // 70 degrees is usually "looking down" slightly, away from the 90+ back limit
  servo_x.write(90);
  servo_y.write(70);
  
  current_x = 90;
  current_y = 70;
  target_x = 90;
  target_y = 70;
}

void head_set_target(int x, int y) {
  target_x = constrain(x, X_MIN, X_MAX);
  target_y = constrain(y, Y_MIN, Y_MAX);
}

void head_test(int x, int y) {
  // Emergency: Force write
  servo_x.write(x);
  servo_y.write(y);
  
  // Update state to prevent "jump back"
  current_x = x;
  current_y = y;
  target_x = x;
  target_y = y;
}

void head_trim(int x_offset, int y_offset) {
  X_CENTER += x_offset;
  Y_CENTER += y_offset;
  update_limits(); // Recalculate safe range
}

void head_set_speed(int delay_ms) {
  move_interval = delay_ms;
}

void head_set_breathing(int y_offset) {
  breathing_offset_y = y_offset;
}

void head_update() {
  if (millis() - last_move_time >= move_interval) {
    last_move_time = millis();
    
    // Smooth movement logic (Linear Interpolation)
    // X Axis
    if (abs(current_x - target_x) > 0.5) {
      if (current_x < target_x) current_x += move_step;
      else current_x -= move_step;
      servo_x.write((int)current_x);
    }
    
    // Y Axis (Base + Breathing)
    int final_target_y = target_y + breathing_offset_y;
    final_target_y = constrain(final_target_y, Y_MIN, Y_MAX);
    
    if (abs(current_y - final_target_y) > 0.5) {
      if (current_y < final_target_y) current_y += move_step;
      else current_y -= move_step;
      servo_y.write((int)current_y);
    }
  }
}

void head_center() {
  head_set_target(X_CENTER, Y_CENTER);
}

int head_get_x() { return (int)current_x; }
int head_get_y() { return (int)current_y; }
