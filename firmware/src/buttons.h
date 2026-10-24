#ifndef BUTTONS_H
#define BUTTONS_H

#include <Arduino.h>

#define WEAR_PIN 25
#define VIEW_PIN 26

void initButtons();
char readButton();

#endif