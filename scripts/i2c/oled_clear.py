#!/usr/bin/env python3
"""OLED clear helper for shutdown.

This script explicitly clears the SSD1306 OLED using Adafruit libraries.
It is intended to be called from systemd ExecStopPost so that the display
is blanked even when the main i2c_manager exits during shutdown.
"""

import time
import board
import busio
import adafruit_ssd1306

# Optional debug log (best-effort)
try:
    with open("/tmp/oled_clear_log.txt", "a") as f:
        f.write("oled_clear.py started\n")
except Exception:
    pass

try:
    # Initialize I2C and OLED (SSD1306 128x32 @ 0x3C)
    i2c = busio.I2C(board.SCL, board.SDA)
    oled = adafruit_ssd1306.SSD1306_I2C(128, 32, i2c)

    # Clear display
    oled.fill(0)
    oled.show()

    # Small delay to ensure command is sent before shutdown continues
    time.sleep(0.2)

    try:
        with open("/tmp/oled_clear_log.txt", "a") as f:
            f.write("OLED cleared successfully\n")
    except Exception:
        pass

except Exception as e:
    try:
        with open("/tmp/oled_clear_log.txt", "a") as f:
            f.write(f"ERROR: {e}\n")
    except Exception:
        pass