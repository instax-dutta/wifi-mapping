/*
 * wifi_mapper - ESP8266 WiFi radio-mapping sensor
 *
 * Emits line-delimited JSON. Two sensing modes:
 *   scan  - active scan of ambient APs, one frame per scan
 *   sniff - promiscuous capture of per-packet RSSI from one target BSSID
 *
 * Output goes to serial always, and over UDP when a network + destination are
 * set (untethered operation). Protocol: docs/architecture.md
 *
 * Commands (host -> board, newline terminated):
 *   scan on | scan off
 *   sniff <bssid> [channel] | sniff off
 *   rate <ms>    (sniff emit interval)
 *   period <ms>  (scan interval)
 *   join <ssid> <password>   (connect to a WiFi network; no spaces in fields)
 *   udp <ip> <port> | udp off
 *   net | info | ping
 *
 * The promiscuous callback buffer on ESP8266 begins with an RxControl struct
 * whose first field is a signed 8-bit RSSI, so buf[0] is the RSSI. We avoid
 * depending on the exact struct size by finding the target MAC as a byte
 * sequence inside the captured buffer.
 */

#include <ESP8266WiFi.h>
#include <WiFiUdp.h>
#include "user_interface.h"

#define FW_NAME    "wifi-mapper"
#define FW_VERSION "0.2.0"

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

// ---------- UDP ----------
static WiFiUDP   udp;
static bool      udpOn   = false;
static IPAddress udpIp   = IPAddress(255, 255, 255, 255);
static uint16_t  udpPort = 5005;

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
  if (next == ringTail) return;            // ring full: drop
  ringRssi[ringHead] = rssi;
  ringLen[ringHead]  = (int16_t)len;
  ringHead = next;
}

// ---------- emit (serial + UDP) ----------
static void emitLine(const String &line) {
  Serial.println(line);
  if (udpOn && WiFi.status() == WL_CONNECTED) {
    udp.beginPacket(udpIp, udpPort);
    udp.write((const uint8_t *)line.c_str(), line.length());
    udp.write((uint8_t)'\n');
    udp.endPacket();
  }
}

// ---------- helpers ----------
static void appendJsonStr(String &out, const String &s) {
  out += '"';
  for (size_t i = 0; i < s.length(); i++) {
    const char c = s[i];
    if (c == '"' || c == '\\') { out += '\\'; out += c; }
    else if ((uint8_t)c < 0x20) { char b[8]; snprintf(b, sizeof(b), "\\u%04x", (uint8_t)c); out += b; }
    else out += c;
  }
  out += '"';
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
  digitalWrite(LED_BUILTIN, on ? LOW : HIGH);
}

// ---------- scanning ----------
static void doScan() {
  heartbeat();
  const int n = WiFi.scanNetworks(false, true);   // sync, include hidden
  String out;
  out.reserve(256 + n * 96);
  out += "{\"t\":\"scan\",\"seq\":"; out += (unsigned)seq++;
  out += ",\"ms\":"; out += (unsigned long)millis();
  out += ",\"n\":"; out += n; out += ",\"aps\":[";
  for (int i = 0; i < n; i++) {
    if (i) out += ',';
    const bool hidden = (WiFi.SSID(i).length() == 0);
    out += "{\"b\":";
    appendJsonStr(out, WiFi.BSSIDstr(i));
    out += ",\"s\":";
    appendJsonStr(out, WiFi.SSID(i));
    out += ",\"r\":"; out += WiFi.RSSI(i);
    out += ",\"c\":"; out += WiFi.channel(i);
    out += ",\"e\":"; out += (int)WiFi.encryptionType(i);
    out += ",\"h\":"; out += (hidden ? 1 : 0);
    out += '}';
  }
  out += "]}";
  emitLine(out);
}

// ---------- sniffing ----------
static void setSniff(bool on, const uint8_t *mac, uint8_t ch) {
  if (on) {
    memcpy(sniffBssid, mac, 6);
    sniffChannel = ch;
    scanning = false;
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
  if (!sniffing || ringTail == ringHead) return;
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
  String out = "{\"t\":\"pk\",\"seq\":";
  out += (unsigned)seq++;
  out += ",\"ms\":"; out += (unsigned long)now;
  out += ",\"b\":\""; out += b;
  out += "\",\"r\":"; out += rssi;
  out += ",\"c\":"; out += sniffChannel;
  out += ",\"len\":"; out += len; out += '}';
  emitLine(out);
}

// ---------- commands ----------
static void printInfo() {
  char b[18];
  snprintf(b, sizeof(b), "%02x:%02x:%02x:%02x:%02x:%02x",
           sniffBssid[0], sniffBssid[1], sniffBssid[2],
           sniffBssid[3], sniffBssid[4], sniffBssid[5]);
  String out = "{\"t\":\"info\",\"scan\":"; out += (scanning ? 1 : 0);
  out += ",\"sniff\":\""; out += (sniffing ? b : "");
  out += "\",\"rate\":"; out += (unsigned long)sniffRateMs;
  out += ",\"period\":"; out += (unsigned long)scanPeriodMs;
  out += ",\"udp\":"; out += (udpOn ? 1 : 0);
  out += ",\"wifi\":\""; out += (WiFi.status() == WL_CONNECTED ? WiFi.localIP().toString() : String(""));
  out += "\"}";
  emitLine(out);
}

static void handleCommand(String cmd) {
  cmd.trim();
  if (cmd.length() == 0) return;
  String c = cmd; c.toLowerCase();

  if (c == "ping") { emitLine("{\"t\":\"pong\"}"); return; }
  if (c == "info" || c == "net") { printInfo(); return; }
  if (c == "scan on")  { setSniff(false, sniffBssid, sniffChannel); scanning = true;  emitLine("{\"t\":\"ack\",\"cmd\":\"scan on\"}");  return; }
  if (c == "scan off") { scanning = false; emitLine("{\"t\":\"ack\",\"cmd\":\"scan off\"}"); return; }
  if (c == "sniff off"){ setSniff(false, sniffBssid, sniffChannel); scanning = true; emitLine("{\"t\":\"ack\",\"cmd\":\"sniff off\"}"); return; }
  if (c == "udp off")  { udpOn = false; emitLine("{\"t\":\"ack\",\"cmd\":\"udp off\"}"); return; }

  if (c.startsWith("rate ")) {
    long v = c.substring(5).toInt();
    if (v >= 0 && v <= 60000) { sniffRateMs = (unsigned long)v; emitLine(String("{\"t\":\"ack\",\"cmd\":\"rate\",\"ms\":") + v + "}"); }
    else emitLine("{\"t\":\"err\",\"msg\":\"bad rate\"}");
    return;
  }
  if (c.startsWith("period ")) {
    long v = c.substring(7).toInt();
    if (v >= 200 && v <= 600000) { scanPeriodMs = (unsigned long)v; emitLine(String("{\"t\":\"ack\",\"cmd\":\"period\",\"ms\":") + v + "}"); }
    else emitLine("{\"t\":\"err\",\"msg\":\"bad period\"}");
    return;
  }
  if (c.startsWith("udp ")) {
    String rest = cmd.substring(4); rest.trim();
    if (rest == "off") { udpOn = false; emitLine("{\"t\":\"ack\",\"cmd\":\"udp off\"}"); return; }
    int sp = rest.indexOf(' ');
    if (sp < 0) { emitLine("{\"t\":\"err\",\"msg\":\"udp needs ip and port\"}"); return; }
    String ip = rest.substring(0, sp);
    long port = rest.substring(sp + 1).toInt();
    if (port < 1 || port > 65535) { emitLine("{\"t\":\"err\",\"msg\":\"bad port\"}"); return; }
    IPAddress parsed;
    if (!parsed.fromString(ip)) { emitLine("{\"t\":\"err\",\"msg\":\"bad ip\"}"); return; }
    udpIp = parsed; udpPort = (uint16_t)port; udpOn = true;
    emitLine(String("{\"t\":\"ack\",\"cmd\":\"udp\",\"ip\":\"") + udpIp.toString() + "\",\"port\":" + port + "}");
    return;
  }
  if (c.startsWith("join ")) {
    String rest = cmd.substring(5); rest.trim();
    int sp = rest.indexOf(' ');
    String ssid = (sp < 0) ? rest : rest.substring(0, sp);
    String pass = (sp < 0) ? String("") : rest.substring(sp + 1);
    if (ssid.length() == 0) { emitLine("{\"t\":\"err\",\"msg\":\"join needs ssid\"}"); return; }
    WiFi.begin(ssid.c_str(), pass.c_str());
    unsigned long t0 = millis();
    while (WiFi.status() != WL_CONNECTED && millis() - t0 < 8000) { delay(100); }
    if (WiFi.status() == WL_CONNECTED) {
      emitLine(String("{\"t\":\"ack\",\"cmd\":\"join\",\"ip\":\"") + WiFi.localIP().toString() + "\",\"rssi\":" + WiFi.RSSI() + "}");
    } else {
      emitLine("{\"t\":\"err\",\"msg\":\"join failed\"}");
    }
    return;
  }
  if (c.startsWith("sniff ")) {
    String rest = cmd.substring(6); rest.trim();
    int sp = rest.indexOf(' ');
    String mac = (sp < 0) ? rest : rest.substring(0, sp);
    uint8_t m[6];
    if (!parseMac(mac, m)) { emitLine("{\"t\":\"err\",\"msg\":\"bad bssid\"}"); return; }
    uint8_t ch = sniffChannel;
    if (sp >= 0) { int v = rest.substring(sp + 1).toInt(); if (v >= 1 && v <= 14) ch = (uint8_t)v; }
    setSniff(true, m, ch);
    emitLine(String("{\"t\":\"ack\",\"cmd\":\"sniff\",\"channel\":") + ch + "}");
    return;
  }
  emitLine("{\"t\":\"err\",\"msg\":\"unknown cmd\"}");
}

// ---------- arduino ----------
void setup() {
  pinMode(LED_BUILTIN, OUTPUT);
  digitalWrite(LED_BUILTIN, HIGH);

  Serial.begin(115200);
  Serial.setDebugOutput(false);
  delay(100);

  WiFi.persistent(false);
  WiFi.mode(WIFI_STA);
  WiFi.disconnect();
  delay(100);

  emitLine(String("{\"t\":\"boot\",\"fw\":\"") + FW_NAME + "\",\"v\":\"" + FW_VERSION +
           "\",\"mac\":\"" + WiFi.macAddress() + "\",\"chip\":\"esp8266\"}");
  emitLine("{\"t\":\"ready\"}");
  lastScanMs = millis() - scanPeriodMs;
}

void loop() {
  while (Serial.available()) {
    const char ch = (char)Serial.read();
    if (ch == '\n') { handleCommand(cmdBuf); cmdBuf = ""; }
    else if (ch != '\r') {
      if (cmdBuf.length() < 200) cmdBuf += ch;
      else cmdBuf = "";
    }
  }

  const unsigned long now = millis();
  if (scanning && (now - lastScanMs >= scanPeriodMs)) {
    lastScanMs = now;
    doScan();
  }
  drainSniff();
}
