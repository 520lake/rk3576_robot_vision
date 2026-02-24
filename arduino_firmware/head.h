#ifndef HEAD_H
#define HEAD_H

#include <Servo.h>
#include "common.h"

extern Servo servo_x;
extern Servo servo_y;

// Initialize
void setup_head();
void setup_head_safe(); // Explicit safe setup

// Core Update Loop (Must call in loop)
void head_update();

// Control API
void head_set_target(int x, int y); // Set absolute target angle
void head_set_speed(int delay_ms);  // Set speed (lower is faster)
void head_set_breathing(int y_offset); // Additive offset for breathing

// Emergency & Calibration
void head_test(int x, int y); // Force write angle (bypass smoothing)
void head_trim(int x_offset, int y_offset); // Adjust center point

// Legacy/Convenience
void head_center();
int head_get_x();
int head_get_y();

#endif
