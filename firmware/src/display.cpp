#include <Arduino.h>
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include "display.h"

extern Adafruit_ILI9341 display;

void showResult(String name, String notes)
{
    display.fillScreen(ILI9341_BLACK);

    display.setTextColor(ILI9341_WHITE);
    display.setTextSize(2);
    display.setCursor(10, 20);
    display.println(name);

    display.setTextColor(ILI9341_CYAN);
    display.setTextSize(1);
    display.setCursor(10, 80);
    display.println("Notes:");
    display.setCursor(10, 95);
    display.println(notes);

    display.setTextColor(ILI9341_GREEN);
    display.setCursor(10, 290);
    display.println("Wear (L)      View (R)");
}

void showSuggestions(String name, String remindsMeOf, int wears)
{
    display.fillScreen(ILI9341_BLACK);

    display.setTextColor(ILI9341_WHITE);
    display.setTextSize(2);
    display.setCursor(10, 20);
    display.println(name);

    display.setTextColor(ILI9341_CYAN);
    display.setTextSize(1);
    display.setCursor(10, 80);
    display.println("Similar scents:");
    display.setCursor(10, 95);
    display.println(remindsMeOf.length() ? remindsMeOf : "(none saved yet)");

    display.setTextColor(ILI9341_GREEN);
    display.setCursor(10, 150);
    display.println("Wear number: " + String(wears));
}
void showMessage(String title, String line2)
{
    display.fillScreen(ILI9341_BLACK);
    display.setTextColor(ILI9341_YELLOW);
    display.setTextSize(2);
    display.setCursor(10,20);
    display.println(title);
    display.setTextColor(ILI9341_WHITE);
    display.setTextSize(1);
    display.setCursor(12,70);
    display.println(line2);
}

void showHome()
{
    display.fillScreen(ILI9341_BLACK);
    display.setTextColor(ILI9341_WHITE);
    display.setTextSize(2);
    display.setCursor(10, 120);
    display.println("Fragrance Stand");

    display.setTextColor(ILI9341_CYAN);
    display.setTextSize(1);
    display.setCursor(10, 160);
    display.println("Tap a bottle to begin");
}

void showLogged(String name, int wears)
{
    display.fillScreen(ILI9341_BLACK);

    display.setTextColor(ILI9341_GREEN);
    display.setTextSize(2);
    display.setCursor(10, 30);
    display.println("LOGGED");

    display.setTextColor(ILI9341_WHITE);
    display.setTextSize(2);
    display.setCursor(10, 80);
    display.println(name);

    display.setTextColor(ILI9341_CYAN);
    display.setTextSize(1);
    display.setCursor(10, 130);
    display.println("Worn " + String(wears) + " times");
}
void showUnknown()
{
    display.fillScreen(ILI9341_BLACK);
    display.setTextColor(ILI9341_YELLOW);
    display.setTextSize(2);
    display.setCursor(10, 20);
    display.println("New bottle");
    display.setTextSize(1);
    display.setCursor(10, 60);
    display.println("Not in database yet.");
}