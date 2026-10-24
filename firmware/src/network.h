#ifndef NETWORK_H
#define NETWORK_H
#include <Arduino.h>
bool connectWiFi();
bool fetchNotes(String name, String &notes, String &rmo);

#endif