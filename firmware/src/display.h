#ifndef DISPLAY_H
#define DISPLAY_H
#include <Arduino.h>
void showResult(String name, String notes);

void showUnknown();
void showSuggestions(String name, String remindsMeOf, int wears);
void showLogged(String name, int wears);
void showMessage(String title, String line2);
void showHome();
#endif
