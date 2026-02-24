#ifndef EMOJI_H
#define EMOJI_H

#include <Adafruit_SSD1306.h>
#include "common.h"

extern Adafruit_SSD1306 display;

// Init
void setup_emoji();

// Core Update Loop
void emoji_update();

// Control API
void set_mood(String mood); // happy, sleep, confused, normal
void look_at(int x, int y); // Move eyes relative to center (-10 to 10)

#endif
