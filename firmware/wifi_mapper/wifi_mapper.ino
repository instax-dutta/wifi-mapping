/*
 * wifi_mapper - ESP8266 WiFi radio-mapping sensor
 *
 * Emits line-delimited JSON over serial (115200). Two sensing modes:
 *   scan  - active scan of ambient APs, one frame per scan
 *   sniff - promiscuous capture of per-packet RSSI from one target BSSID
 *
 * Protocol and design: docs/architecture.md
 * Commands (host -> board, newline terminated):
 *   scan on | scan off
 *   sniff <bssid> [channel] | sniff off
 *   rate <ms>    (sniff emit interval)
 *   period <ms>  (scan interval)
 *   info | ping
 *
 * The promiscuous callback buffer on ESP8266 begins with an RxControl struct
 * whose first field is a signed 8-bit RSSI, so buf[0] is the RSSI. We avoid
 * depending on the exact struct size by finding the target MAC as a byte
 * sequence inside the captured buffer.
 */

#include <ESP8266WiFi.h>
#include "user_interface.h"

#define FW_NAME    "wifi-mapper"
#define FW_VERSION "0.1.0"

// ---------- state ----------
static bool          scanning     = true;
static unsigned long scanPeriodMs = 1500;
static unsigned long lastScanMs   = 0;

static bool          sniffing     = false;
static uint8_t       sniffBssid[6] = {0};
static uint8_t       sniffChannel = 6;
static unsigned long sniffRateMs  = 200;
static unsigned long lastEmitMs   = 0;

static uint32_t      seq = 0;
static String        cmdBuf;

// ---------- sniff ring buffer (callback -> loop) ----------
#define RING 32
static volatile int8_t  ringRssi[RING];
static volatile int16_t ringLen[RING];
static volatile uint8_t ringHead = 0;
static volatile uint8_t ringTail = 0;

static void ICACHE_RAM_ATTR snifferCb(uint8_t *buf, uint16_t len) {
  if (!buf || len < 12) return;
  const int8_t rssi = (int8_t)buf[0];
  bool match = false;
  for (uint16_t i = 0; i + 6 <= len; i++) {
    if (buf[i]     == sniffBssid[0] && buf[i + 1] == sniffBssid[1] &&
        buf[i + 2] == sniffBssid[2] && buf[i + 3] == sniffBssid[3] &&
        buf[i + 4] == sniffBssid[4] && buf[i + 5] == sniffBssid[5]) {
      match = true;
      break;
    }
  }
  if (!match) return;
  const uint8_t next = (uint8_t)((ringHead + 1) % RING);
  if (next == ringTail) return;            // ring full: drop oldest-free slot
  ringRssi[ringHead] = rssi;
  ringLen[ringHead]  = (int16_t)len;
  ringHead = next;
}

// ---------- helpers ----------
static void printJsonStr(const String &s) {
  Serial.print('"');
  for (size_t i = 0; i < s.length(); i++) {
    const char c = s[i];
    if (c == '"' || c == '\\') { Serial.print('\\'); Serial.print(c); }
    else if ((uint8_t)c < 0x20) { Serial.printf("\\u%04x", (uint8_t)c); }
    else Serial.print(c);
  }
  Serial.print('"');
}

static int hexNibble(char c) {
  if (c >= '0' && c <= '9') return c - '0';
  if (c >= 'a' && c <= 'f') return c - 'a' + 10;
  if (c >= 'A' && c <= 'F') return c - 'A' + 10;
  return -1;
}

static bool parseMac(const String &s, uint8_t *out) {
  int vals[6];
  if (sscanf(s.c_str(), "%x:%x:%x:%x:%x:%x",
             &vals[0], &vals[1], &vals[2], &vals[3], &vals[4], &vals[5]) != 6) {
    return false;
  }
  for (int i = 0; i < 6; i++) {
    if (vals[i] < 0 || vals[i] > 255) return false;
    out[i] = (uint8_t)vals[i];
  }
  return true;
}

static void heartbeat() {
  static bool on = false;
  on = !on;
  digitalWrite(LED_BUILTIN, on ? LOW : HIGH);   // active-low on NodeMCU
}

// ---------- scanning ----------
static void doScan() {
  heartbeat();
  const int n = WiFi.scanNetworks(false, true);   // sync, include hidden
  Serial.printf("{\"t\":\"scan\",\"seq\":%u,\"ms\":%lu,\"n\":%d,\"aps\":[",
                (unsigned)seq++, (unsigned long)millis(), n);
  for (int i = 0; i < n; i++) {
    if (i) Serial.print(',');
    const bool hidden = (WiFi.SSID(i).length() == 0);
    Serial.print("{\"b\":");
    printJsonStr(WiFi.BSSIDstr(i));
    Serial.print(",\"s\":");
    printJsonStr(WiFi.SSID(i));
    Serial.printf(",\"r\":%d,\"c\":%d,\"e\":%d,\"h\":%d}",
                  WiFi.RSSI(i), WiFi.channel(i),
                  (int)WiFi.encryptionType(i), hidden ? 1 : 0);
  }
  Serial.println("]}");
}

// ---------- sniffing ----------
static void setSniff(bool on, const uint8_t *mac, uint8_t ch) {
  if (on) {
    memcpy(sniffBssid, mac, 6);
    sniffChannel = ch;
    scanning = false;                       // one radio: sniff takes the channel
    wifi_promiscuous_enable(0);
    wifi_set_promiscuous_rx_cb(snifferCb);
    wifi_set_channel(sniffChannel);
    wifi_promiscuous_enable(1);
    sniffing = true;
  } else {
    wifi_promiscuous_enable(0);
    wifi_set_promiscuous_rx_cb(NULL);
    sniffing = false;
    ringHead = ringTail = 0;
  }
}

static void drainSniff() {
  if (!sniffing) return;
  if (ringTail == ringHead) return;
  const unsigned long now = millis();
  if (now - lastEmitMs < sniffRateMs) return;
  lastEmitMs = now;
  const int8_t  rssi = ringRssi[ringTail];
  const int16_t len  = ringLen[ringTail];
  ringTail = (uint8_t)((ringTail + 1) % RING);
  char b[18];
  snprintf(b, sizeof(b), "%02x:%02x:%02x:%02x:%02x:%02x",
           sniffBssid[0], sniffBssid[1], sniffBssid[2],
           sniffBssid[3], sniffBssid[4], sniffBssid[5]);
  Serial.printf("{\"t\":\"pk\",\"seq\":%u,\"ms\":%lu,\"b\":\"%s\",\"r\":%d,\"c\":%d,\"len\":%d}\n",
                (unsigned)seq++, (unsigned long)now, b, rssi, sniffChannel, len);
}

// ---------- commands ----------
static void printInfo() {
  char b[18];
  snprintf(b, sizeof(b), "%02x:%02x:%02x:%02x:%02x:%02x",
           sniffBssid[0], sniffBssid[1], sniffBssid[2],
           sniffBssid[3], sniffBssid[4], sniffBssid[5]);
  Serial.printf("{\"t\":\"info\",\"scan\":%d,\"sniff\":%s,\"rate\":%lu,\"period\":%lu}\n",
                scanning ? 1 : 0, sniffing ? "\"" : "null", (unsigned long)sniffRateMs,
                (unsigned long)scanPeriodMs);
  if (sniffing) {
    Serial.printf("{\"t\":\"info\",\"target\":\"%s\",\"channel\":%d}\n", b, sniffChannel);
  }
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  String c = cmd; c.toLowerCase();

  if (c == "ping") { Serial.println("{\"t\":\"pong\"}"); return; }
  if (c == "info") { printInfo(); return; }
  if (c == "scan on")  { setSniff(false, sniffBssid, sniffChannel); scanning = true;  Serial.println("{\"t\":\"ack\",\"cmd\":\"scan on\"}");  return; }
  if (c == "scan off") { scanning = false; Serial.println("{\"t\":\"ack\",\"cmd\":\"scan off\"}"); return; }
  if (c == "sniff off"){ setSniff(false, sniffBssid, sniffChannel); scanning = true; Serial.println("{\"t\":\"ack\",\"cmd\":\"sniff off\"}"); return; }

  if (c.startsWith("rate ")) {
    long v = c.substring(5).toInt();
    if (v >= 0 && v <= 60000) { sniffRateMs = (unsigned long)v; Serial.printf("{\"t\":\"ack\",\"cmd\":\"rate\",\"ms\":%ld}\n", v); }
    else Serial.println("{\"t\":\"err\",\"msg\":\"bad rate\"}");
    return;
  }
  if (c.startsWith("period ")) {
    long v = c.substring(7).toInt();
    if (v >= 200 && v <= 600000) { scanPeriodMs = (unsigned long)v; Serial.printf("{\"t\":\"ack\",\"cmd\":\"period\",\"ms\":%ld}\n", v); }
    else Serial.println("{\"t\":\"err\",\"msg\":\"bad period\"}");
    return;
  }
  if (c.startsWith("sniff ")) {
    // expected: sniff <mac> [channel]
    String rest = cmd.substring(6); rest.trim();
    int sp = rest.indexOf(' ');
    String mac = (sp < 0) ? rest : rest.substring(0, sp);
    uint8_t m[6];
    if (!parseMac(mac, m)) { Serial.println("{\"t\":\"err\",\"msg\":\"bad bssid\"}"); return; }
    uint8_t ch = sniffChannel;
    if (sp >= 0) { int v = rest.substring(sp + 1).toInt(); if (v >= 1 && v <= 14) ch = (uint8_t)v; }
    setSniff(true, m, ch);
    Serial.printf("{\"t\":\"ack\",\"cmd\":\"sniff\",\"channel\":%d}\n", ch);
    return;
  }
  Serial.println("{\"t\":\"err\",\"msg\":\"unknown cmd\"}");
}

// ---------- arduino ----------
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);            // off (active low)

  Serial.begin(115200);
  Serial.setDebugOutput(false);
  delay(100);

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);                        // promiscuous requires station mode
  WiFi.disconnect();
  delay(100);

  Serial.printf("{\"t\":\"boot\",\"fw\":\"%s\",\"v\":\"%s\",\"mac\":\"%s\",\"chip\":\"esp8266\",\"flash\":%u}\n",
                FW_NAME, FW_VERSION, WiFi.macAddress().c_str(), ESP.getFlashChipRealSize());
  Serial.println("{\"t\":\"ready\"}");
  lastScanMs = millis() - scanPeriodMs;       // scan on first loop
}

void loop() {
  // host commands
  while (Serial.available()) {
    const char ch = (char)Serial.read();
    if (ch == '\n') { handleCommand(cmdBuf); cmdBuf = ""; }
    else if (ch != '\r') {
      if (cmdBuf.length() < 200) cmdBuf += ch;
      else cmdBuf = "";
    }
  }

  // periodic scan
  const unsigned long now = millis();
  if (scanning && (now - lastScanMs >= scanPeriodMs)) {
    lastScanMs = now;
    doScan();
  }

  drainSniff();
}
