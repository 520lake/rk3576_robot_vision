#ifndef COMMON_H
#define COMMON_H

#include <Arduino.h>

// --- OLED Settings ---
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64  // Fixed for 0.96" OLED
#define OLED_RESET -1
#define SCREEN_ADDRESS 0x3C

// --- Servo Settings ---
#define X_PIN 9
#define Y_PIN 10
#define STEP 1
#define SERVO_DELAY 10
#define X_OFFSET 20
#define Y_OFFSET 15

// --- Global Variables (Extern) ---
extern int X_CENTER;
extern int Y_CENTER;
extern int X_MIN;
extern int X_MAX;
extern int Y_MIN;
extern int Y_MAX;

#endif
