#include <Arduino.h>
#include "buttons.h"

void initButtons()
{
    pinMode(WEAR_PIN, INPUT_PULLUP);
    pinMode(VIEW_PIN, INPUT_PULLUP);
}

char readButton()
{
    if (digitalRead(WEAR_PIN) == LOW)
    {
        delay(30);
        if (digitalRead(WEAR_PIN) == LOW)
            return 'w';
    }
    if (digitalRead(VIEW_PIN) == LOW)
    {
        delay(30);
        if (digitalRead(VIEW_PIN) == LOW)
            return 'v';
    }
    if (Serial.available() > 0)
    {
        char c = Serial.read();
        if (c == 'w' || c == 'v')
            return c;
    }
    return 0;
}
