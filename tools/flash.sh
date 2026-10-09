#!/usr/bin/env bash
# Compile and flash the wifi_mapper firmware using the project venv's esptool.
#
# arduino-cli's bundled esptool (v3.0, x86 python under Rosetta) fails on this
# mac with `termios ... Invalid argument`, so we flash with .venv/bin/esptool.
#
# Usage: tools/flash.sh [port] [sketch_dir]
#   default port      /dev/cu.usbserial-0001
#   default sketch    firmware/wifi_mapper
set -euo pipefail

PORT="${1:-/dev/cu.usbserial-0001}"
SKETCH="${2:-firmware/wifi_mapper}"
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "$ROOT"

NAME="$(basename "$SKETCH")"
arduino-cli compile -b esp8266:esp8266:nodemcuv2 --output-dir "build/$NAME" "$SKETCH"
.venv/bin/esptool --port "$PORT" --baud 115200 write-flash 0x0 "build/$NAME/$NAME.ino.bin"
echo "flashed $SKETCH to $PORT"
