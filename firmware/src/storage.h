#ifndef STORAGE_H
#define STORAGE_H

#include <Arduino.h>

struct Bottle
{
    String uid;
    String name;
    String notes;
    String remindsMeOf;
    String dateAdded;
    int wearCount;
};

struct LogEntry
{
    String uid;
    String timestamp;
};

Bottle lookupBottle(String uid,bool &found);
void incrementWearCount(String uid);
int getWearCount(String uid) ;
void saveLogEntry(String uid, String timestamp);
void seedBottles();
void saveBottle(Bottle b);
#endif