#include "storage.h"
#include <Preferences.h>

Preferences prefs;
LogEntry LogArray[30];
int logCount = 0;

Bottle lookupBottle(String uid, bool &found)
{
    Bottle result;
    found = false;
    
    //new code
    if(prefs.begin(uid.c_str(),true))
    {
        if(prefs.isKey("name"))
        {
            result.uid=uid;
            result.name=prefs.getString("name", "");
            result.dateAdded=prefs.getString("date", "");
            result.notes=prefs.getString("notes", "");
            result.remindsMeOf=prefs.getString("rmo", "");
            result.wearCount=prefs.getInt("wears",0);
            found= true;
        }
        prefs.end();
    }
    return result;
}

void incrementWearCount(String uid)
{
    if(prefs.begin(uid.c_str(),false))
    {
        int n=prefs.getInt("wears",0);
        prefs.putInt("wears",n+1);
        prefs.end();
    }
    
}

int getWearCount(String uid)
{
    int count = 0;
    if(prefs.begin(uid.c_str(),true))
    {
        count=prefs.getInt("wears",0);
        prefs.end();
    }
    
    return count;
}

void saveBottle(Bottle b)
{
    prefs.begin(b.uid.c_str(), false);
    prefs.putString("name", b.name);
    prefs.putString("notes", b.notes);
    prefs.putString("rmo", b.remindsMeOf);
    prefs.putString("date", b.dateAdded);
    prefs.putInt("wears", b.wearCount);
    prefs.end();
}
void saveLogEntry(String uid, String timestamp)
{
    if (logCount < 30)
    {
        LogArray[logCount].uid = uid;
        LogArray[logCount].timestamp = timestamp;
        logCount++;
    }
    else
    {
        Serial.println("Database full");
    }
}
void seedBottles()
{
    bool found = false;
    lookupBottle("21fafc3e", found);
    if (!found)
    {
        saveBottle({"21fafc3e", "Aventus", "pineapple, birch, musk", "Aventus-like", "2026-10-10", 0});
    }
}