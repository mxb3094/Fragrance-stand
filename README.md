# Fragrance Stand

An ESP32 cologne tracker. Stick an NFC tag on each bottle, tap it on the stand, and
the TFT shows the bottle's name and notes. Press a button to log a wear or to see
similar scents. New bottles are enrolled by typing a name; a small Python server
looks up the notes on Fragrantica. Everything is saved in the ESP32's flash, so
wear counts survive power loss.

## Features
- NFC tag identification (MFRC522 + NTAG215 stickers)
- 2.4" TFT display with a home screen, bottle screen, wear confirmation and similar-scents screen
- Wear and View buttons, with screens returning to home after 20 seconds
- Wear counts and bottle data stored in ESP32 flash (NVS), surviving reboots
- Enrollment: tap an unknown tag, type the cologne name, notes are fetched automatically
- Python Flask server with Fragrantica lookup, caching, retries and automatic API-key refresh

## Hardware
- ESP32 DevKitC (CP2102)
- MFRC522 RFID reader and NTAG215 stickers
- 2.4" ILI9341 SPI TFT
- 2 push buttons, breadboard, jumper wires

## Pins
| Device | Signal | ESP32 GPIO |
|---|---|---|
| TFT | CS | 27 |
| TFT | DC | 2 |
| TFT | RST | 4 |
| RFID | SDA/SS | 21 |
| RFID | RST | 22 |
| Shared SPI | SCK | 18 |
| Shared SPI | MOSI | 23 |
| Shared SPI | MISO | 19 |
| Button | Wear | 25 |
| Button | View | 26 |

Wiring notes:
- The TFT and the RFID reader share the SPI bus. Only their CS/SS pins differ.
- Power the RFID reader from 3.3V, never 5V.
- Leave the TFT's SDO pin unconnected, or it can block the RFID's MISO line.
- Each button connects its GPIO pin to GND. The code uses the internal pull-ups.
- GPIO 2 is a strapping pin. Holding it in the wrong state at reset causes
  "wrong boot mode" upload errors. Moving TFT DC to another pin such as GPIO 14
  (change `TFT_DC` in `main.cpp`) avoids this.
- Avoid GPIO 0, 2, 12 and 15 for buttons, and 34 to 39 (input-only, no pull-ups).

## Setup

### 1. Firmware (`firmware/`, built with PlatformIO)
1. Create `firmware/src/priv.h`. It is not in the repo because it holds WiFi
   details. It must contain:
   ```cpp
   #pragma once
   #define WIFI_SSID "your wifi name"
   #define WIFI_PASS "your wifi password"
   #define SERVER_URL "http://192.168.1.xxx:5000"
   ```
   `SERVER_URL` is the address of the computer running the server (see below).
   The ESP32 only joins 2.4 GHz WiFi networks.
2. Build and upload with PlatformIO. If the upload fails with "wrong boot mode",
   hold the BOOT button while the terminal shows `Connecting......`.
3. Open the Serial Monitor at 9600 baud. The boot line should read
   `Firmware Version: 0x92 = v2.0`, which means the RFID reader is working. A
   value like `0x00`, `0xFF` or `0xEE` means a wiring problem.

### 2. Server (`server/`, Python and Flask)
```
cd server
python -m venv venv
venv\Scripts\activate
pip install flask cloudscraper beautifulsoup4 requests
python app.py
```
- The second "Running on" address that prints is the one to use in `SERVER_URL`.
  The server must listen on `0.0.0.0` so the ESP32 can reach it, and Windows
  Firewall must allow Python on private networks.
- The server is only needed when enrolling a new bottle. Scanning, wearing and
  viewing work without it.
- Fragrantica search goes through an Algolia API key that expires.
  `algolia_key.py` checks the key's expiry, refreshes it automatically and saves
  it to `algolia_key.txt` (not in the repo). Run `python algolia_key.py` to check
  the key status.

## Using it
- **Known bottle:** tap its tag. The screen shows the name and notes. Press Wear
  (GPIO 25) to log a wear, or View (GPIO 26) to see similar scents and the wear count.
- **Unknown tag:** the stand asks for a name. Type the cologne name in the Serial
  Monitor and press Enter. The stand fetches the notes from the server and saves
  the bottle. If the server is unreachable, the bottle is saved without notes.
- Result screens return to the home screen after 20 seconds, and tapping another
  tag interrupts them.

## Project layout
```
firmware/src/
    main.cpp        state machine (IDLE, SCAN, LOOKUP, DISP, CONFIRM, LOG, SHOW, ENROLL)
    nfc_reader.*    RFID tag detection and UID reading
    display.*       all TFT screens
    storage.*       bottle data and wear counts in flash (Preferences/NVS)
    buttons.*       wear and view buttons
    network.*       WiFi and the call to the server
server/
    app.py          Flask endpoint: GET /notes?name=<cologne>
    algolia_key.py  Fragrantica search through Algolia, with automatic key refresh
```

## Server endpoint
`GET /notes?name=<cologne name>` returns JSON:
```json
{"name": "Aventus", "notes": "Bergamot, Black Currant, Apple", "remindsMeOf": "A, B, C"}
```
A failed lookup returns `"not found"` or `"unavailable"` in place of the notes. If the
Algolia key cannot be refreshed, it returns HTTP 503 with an error message.

## Known limitations
- Timestamps are placeholders ("fake stamp") until real time is added over NTP.
- The wear-threshold suggestion (155 wears) only prints to the Serial Monitor.
- Notes come from scraping Fragrantica, so a layout change on their site can break
  the lookup.
