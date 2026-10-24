#include<Arduino.h>
#include "display.h"
#include "nfc_reader.h"
#include "storage.h"
#include "buttons.h"
#include <Adafruit_GFX.h>
#include <Adafruit_ILI9341.h>
#include <MFRC522.h>
#include <SPI.h>
#include "network.h"
#include <WiFi.h>

#define TFT_CS 27
#define TFT_DC 2
#define TFT_RST 4

    enum STATE
{
  IDLE,
  SCAN,
  LOOKUP,
  DISP,
  CONFIRM,
  LOG,
  SUGGEST,
  ENROLL,
  SHOW
};
const int WEAR_THRESHOLD = 155;
const unsigned long SCREEN_TIMEOUT = 20000; // 20 seconds, in milliseconds

int currentState = IDLE;
unsigned long screenTimer = 0; // when the current screen appeared
String currentUID;
String currentName;
String currentNotes;
String currentRemindsMeOf;

void resetCurrentState()
{
  currentName = "";
  currentNotes = "";
  currentRemindsMeOf = "";
}

MFRC522 rfid(21, 22);
Adafruit_ILI9341 display(TFT_CS, TFT_DC, TFT_RST);

// Clear everything and show the home screen.
void goHome()
{
  resetCurrentState();
  showHome();
  currentState = IDLE;
}

void setup()
{
  Serial.begin(9600);
  delay(500);
  Serial.println("Booting...");
  SPI.begin();
  display.begin();
  rfid.PCD_Init();
  rfid.PCD_DumpVersionToSerial();
  initButtons();
  display.setRotation(2);
  goHome();
}

void loop()
{
  switch (currentState)
  {
  case IDLE:
    if (tagPresent())
    {
      currentUID = getScannedUID();
      Serial.println("UID: " + currentUID);
      currentState = SCAN;
    }
    break;

  case SCAN:
    Serial.println("Tag scanned");
    currentState = LOOKUP;
    break;

  case LOOKUP:
  {
    Serial.println("looking up");
    currentState = DISP;
    bool found = false;
    Bottle result = lookupBottle(currentUID, found);
    if (found)
    {
      currentName = result.name;
      currentNotes = result.notes;
      currentRemindsMeOf = result.remindsMeOf;
      Serial.println("Found: " + currentName);
    }
    else
    {
      Serial.println("New bottle - not in database.");
    }
    break;
  }

  case DISP:
    if (currentName.length() > 0)
    {
      showResult(currentName, currentNotes);
      Serial.println("Press wear (GPIO 25) or view (GPIO 26)");
      screenTimer = millis(); // start the 20 s countdown
      currentState = CONFIRM;
    }
    else
    {
      currentState = ENROLL;
    }
    break;

  case CONFIRM:
  {
    char choice = readButton();
    if (choice == 'w')
    {
      Serial.println("wear pressed");
      currentState = LOG;
      delay(300);
    }
    else if (choice == 'v')
    {
      Serial.println("view pressed");
      showSuggestions(currentName, currentRemindsMeOf, getWearCount(currentUID));
      screenTimer = millis(); // result screen stays up for 20 s
      currentState = SHOW;
      delay(300);
    }
    else if (millis() - screenTimer >= SCREEN_TIMEOUT)
    {
      Serial.println("timed out, back to home");
      goHome(); // no button pressed in time
    }
    break;
  }

  case LOG:
    Serial.println("logging the scan");
    saveLogEntry(currentUID, "fake stamp");
    incrementWearCount(currentUID);
    showLogged(currentName, getWearCount(currentUID));
    screenTimer = millis(); // LOGGED screen stays up for 20 s

    if (getWearCount(currentUID) >= WEAR_THRESHOLD)
    {
      currentState = SUGGEST;
    }
    else
    {
      currentState = SHOW;
    }
    break;

  case SUGGEST:
    Serial.println("You'd also like this: " + currentRemindsMeOf);
    currentState = SHOW; // keep the LOGGED screen up, then time out
    break;

  case SHOW:
    // A result screen is showing. A new tag interrupts it; otherwise wait 20 s.
    if (tagPresent())
    {
      resetCurrentState();
      currentUID = getScannedUID();
      Serial.println("UID: " + currentUID);
      currentState = SCAN;
    }
    else if (millis() - screenTimer >= SCREEN_TIMEOUT)
    {
      goHome();
    }
    break;

  case ENROLL:
  {
    showMessage("New bottle", "Type the name in the\nSerial Monitor and\npress Enter.");
    Serial.println("Enter cologne name (60 s):");

    while (Serial.available())
    {
      Serial.read(); // throw away leftover typed characters
    }

    // Read one line, accepting CR, LF or CRLF as "Enter".
    String typed = "";
    unsigned long start = millis();
    while (millis() - start < 60000)
    {
      if (Serial.available())
      {
        char c = Serial.read();
        if (c == '\n' || c == '\r')
        {
          if (typed.length() > 0)
            break;  // finished a line
          continue; // ignore a stray empty Enter before the name
        }
        typed += c;
      }
      delay(5);
    }
    typed.trim();

    if (typed.length() == 0)
    {
      showMessage("Cancelled", "Nothing typed.");
      delay(1500);
      goHome();
      break;
    }

    showMessage("Looking up...", typed); // can take up to ~15 s
    String notes, rmo;
    bool ok = fetchNotes(typed, notes, rmo);
    if (!ok)
    {
      notes = ""; // save the name anyway; notes can be filled in later
      rmo = "";
    }

    Bottle b = {currentUID, typed, notes, rmo, "unknown", 0};
    saveBottle(b);

    Serial.println(ok ? "Saved with notes" : "Saved without notes");
    showMessage(ok ? "Saved!" : "Saved (no notes)", typed);
    delay(2000);
    goHome();
    break;
  }
  }
  delay(50);
}