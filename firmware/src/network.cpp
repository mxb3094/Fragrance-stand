#include "network.h"
#include <WiFi.h>
#include <HTTPClient.h>
#include <ArduinoJson.h>
#include "priv.h"


const String SERVER = SERVER_URL;

bool connectWiFi()
{
    if (WiFi.status() == WL_CONNECTED)
        return true;

    WiFi.begin(WIFI_SSID, WIFI_PASS);
    unsigned long start = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - start < 10000)
    {
        delay(250);
    }
    return WiFi.status() == WL_CONNECTED;
}

bool fetchNotes(String name, String &notes, String &rmo)
{
    if (!connectWiFi())
        return false;

    name.replace(" ", "%20"); // spaces are not allowed in URLs

    HTTPClient http;
    http.begin(SERVER + "/notes?name=" + name);
    http.setTimeout(20000); // the server may take up to ~15 s on a new cologne
    int code = http.GET();
    Serial.println("HTTP code: " + String(code));

    if (code != 200)
    {
        http.end();
        return false;
    }

    JsonDocument doc;
    DeserializationError err = deserializeJson(doc, http.getString());
    http.end();
    if (err)
        return false;

    notes = doc["notes"].as<String>();
    rmo = doc["remindsMeOf"].as<String>();
    return notes != "unavailable" && notes != "not found";
}