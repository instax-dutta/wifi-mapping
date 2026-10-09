# Hardware: the board in hand

Everything here was measured from the physical board on this laptop on 2026-10-09,
not copied from a datasheet.

## Identity

| Property | Value | How it was measured |
| --- | --- | --- |
| Chip | ESP8266EX | `esptool flash-id` -> "Chip type: ESP8266EX" |
| Features | Wi-Fi, 160 MHz | `esptool flash-id` |
| Crystal | 26 MHz | `esptool flash-id` |
| MAC (station) | `2c:f4:32:2e:d4:dc` | `esptool flash-id` |
| Flash size | 4 MB (32 Mbit) | `esptool flash-id` -> "Detected flash size: 4MB" |
| Flash id | manufacturer `0x1c`, device `0x3016` | `esptool flash-id` |
| USB-UART bridge | Silicon Labs CP2102 | `ioreg -p IOUSB` -> "CP2102 USB to UART Bridge Controller" |
| USB VID:PID | `0x10C4:0xEA60` (4292:60000) | `ioreg -p IOUSB` |
| Serial port | `/dev/cu.usbserial-0001` | `ls /dev/cu.*` |
| Board class | NodeMCU 1.0 (ESP-12E module) | closest match; FQBN `esp8266:esp8266:nodemcuv2` |
| Arduino core | `esp8266:esp8266` 3.1.2 | `arduino-cli core list` |

The port appears twice: `/dev/cu.usbserial-0001` (call-out, use for tools) and
`/dev/tty.usbserial-0001` (blocking). Always use the `cu.*` device.

## Why it is classed as NodeMCU v2/v3

The CP2102 bridge plus a 4 MB ESP-12E/F module is the NodeMCU 1.0 layout. The
LoLin "V3" board usually ships a CH340 bridge, so a CP2102 strongly implies the
Amica/V2 layout. Either way the FQBN `esp8266:esp8266:nodemcuv2` with 4 MB flash
is correct. Default tool options: `xtal=80`, `baud=115200`, `eesz=4M2M`.

## Radio capabilities that matter for mapping

| Capability | Present? | Consequence for this project |
| --- | --- | --- |
| 2.4 GHz Wi-Fi scan (active + passive), channels 1-14 | Yes | Core primitive: `WiFi.scanNetworks()`. Gives RSSI, BSSID, SSID, channel per AP. |
| Async scan (`scanNetworks(true)` / `scanComplete()`) | Yes | Scan without blocking the main loop. |
| Promiscuous mode / raw packet sniff with per-packet RSSI | Yes | High-rate RSSI stream (tens-hundreds of Hz) from one chosen transmitter. The key to motion-based mapping. |
| Channel State Information (CSI) | **No** | ESP8266 silicon does not expose CSI. Fine-grained multipath/phase features are off the table on this board; those need an ESP32 (`espressif/esp-csi`). |
| Simultaneous AP+STA on different channels | **No** | One radio, one channel at a time. AP+STA must share a channel. Time-division only. |
| USB-serial at 115200 baud | Yes | ~11 KB/s of structured output; enough for scan frames and a throttled sniffer. |

## Memory and I/O budget

- ~80 KB usable DRAM; a full scan of 30+ APs is trivial to buffer.
- 4 MB flash but the default `4M2M` option reserves 2 MB for SPIFFS/LittleFS and
  leaves ~1 MB for OTA. There is no need for a filesystem for this project yet.
- GPIO, one 10-bit ADC (TOUT, 0-1.0 V), I2C, SPI, UART0/UART1 available for the
  later motor/sensor stage.

## Toolchain on this laptop

- `arduino-cli` 1.5.1 (Homebrew) with the `esp8266` core installed.
- Project venv at `.venv` with `esptool` 5.5.0 and `pyserial` for host tooling.
- The ESP8266 core's bundled python 3.8 lacks `pyserial`, so always probe with
  `.venv/bin/esptool`, not the bundled one.

## Reproduction commands

```bash
# identify the bridge
ioreg -p IOUSB -l -w 0 | grep -iE 'Product Name|idProduct|idVendor'

# identify the chip (project venv)
.venv/bin/esptool --port /dev/cu.usbserial-0001 flash-id

# list board options
arduino-cli board details -b esp8266:esp8266:nodemcuv2
```

## Radio observations (2026-10-09, indoors, at the desk)

Measured with the `wifi_mapper` firmware over serial:

| Observation | Value |
| --- | --- |
| Ambient APs visible here | 1 (`home-router`, ch 11, enc=4) |
| Scan cadence at period=1500 ms | one frame per ~2.2 s (a scan itself blocks ~0.7 s) |
| Static RSSI over 15 s / 6 scans | median -59 dBm, scan-to-scan jitter 1 dBm |
| Promiscuous sniff of that AP | 40 packets in 8 s (rate-limited at 5/s; more are available), RSSI -66..-37 dBm, median -62 |

Consequence: only one AP is in range at this spot, so a multi-AP fingerprint
map needs a different location or a second transmitter (for example a phone
hotspot) as a reference. The single-radio design still yields a dense
per-packet RSSI stream from one AP, which is the signal the motion/geometry
work needs.

