/*
 * ref_beacon - ESP8266 fixed reference access point for WiFi radio mapping.
 *
 * Board B: park it anywhere in the room on a power bank. It beacons a known
 * SSID on a fixed channel at maximum TX power, so Board A (the sensor) can
 * measure its RSSI from a known transmitter. Beacons are sent ~10x/second by
 * the SDK, which the sensor sniffs at high rate.
 *
 * Emits one JSON status line per ~5 s so a tethered unit still reports itself.
 * WPA2 (not open) keeps phones from auto-connecting and adding load.
 */

#include <ESP8266WiFi.h>

#define REF_SSID "mq-ref"
#define REF_PASS "mqref12345"
#define REF_CHANNEL 6
#define FW_NAME "ref_beacon"
#define FW_VERSION "0.1.0"

static unsigned long lastStatus = 0;

void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);            // off (active low)
  Serial.begin(115200);
  Serial.setDebugOutput(false);
  delay(100);

  WiFi.persistent(false);
  WiFi.mode(WIFI_AP);
  WiFi.setOutputPower(20.5);                  // max 2.4 GHz TX power (dBm)
  WiFi.softAP(REF_SSID, REF_PASS, REF_CHANNEL, 0 /*not hidden*/, 4 /*max clients*/);

  const IPAddress ip = WiFi.softAPIP();
  Serial.printf("{\"t\":\"boot\",\"fw\":\"%s\",\"v\":\"%s\",\"ssid\":\"%s\","
                "\"channel\":%d,\"mac\":\"%s\",\"ip\":\"%s\"}\n",
                FW_NAME, FW_VERSION, REF_SSID, REF_CHANNEL,
                WiFi.softAPmacAddress().c_str(), ip.toString().c_str());
  Serial.println("{\"t\":\"ready\"}");
}

void loop() {
  // slow blink so a human can see it is alive; fast-blink is unnecessary here
  static bool on = false;
  static unsigned long lastBlink = 0;
  if (millis() - lastBlink >= 1000) {
    lastBlink = millis();
    on = !on;
    digitalWrite(LED_BUILTIN, on ? LOW : HIGH);
  }

  if (millis() - lastStatus >= 5000) {
    lastStatus = millis();
    const int stations = WiFi.softAPgetStationNum();
    Serial.printf("{\"t\":\"ref\",\"ms\":%lu,\"ssid\":\"%s\",\"channel\":%d,"
                  "\"mac\":\"%s\",\"stations\":%d}\n",
                  (unsigned long)millis(), REF_SSID, REF_CHANNEL,
                  WiFi.softAPmacAddress().c_str(), stations);
  }
}
