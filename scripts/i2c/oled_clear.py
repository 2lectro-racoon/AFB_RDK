#!/usr/bin/env python3
"""OLED clear helper using smbus2 for SSD1306 128x32."""

import time
from smbus2 import SMBus, i2c_msg

I2C_BUS_NUM = 5
OLED_ADDR = 0x3C
OLED_WIDTH = 128
OLED_HEIGHT = 32
OLED_PAGES = OLED_HEIGHT // 8


def write_cmd(bus: SMBus, cmd: int) -> None:
    bus.write_byte_data(OLED_ADDR, 0x00, cmd & 0xFF)


def write_data(bus: SMBus, data: bytes) -> None:
    chunk_size = 16
    for i in range(0, len(data), chunk_size):
        chunk = data[i:i + chunk_size]
        msg = i2c_msg.write(OLED_ADDR, bytes([0x40]) + bytes(chunk))
        bus.i2c_rdwr(msg)


# Optional debug log (best-effort)
try:
    with open("/tmp/oled_clear_log.txt", "a") as f:
        f.write("oled_clear.py started\n")
except Exception:
    pass

try:
    with SMBus(I2C_BUS_NUM) as bus:
        # Create empty buffer
        buffer = bytes([0x00] * (OLED_WIDTH * OLED_PAGES))

        for page in range(OLED_PAGES):
            write_cmd(bus, 0xB0 + page)  # Set page address
            write_cmd(bus, 0x00)         # Set lower column
            write_cmd(bus, 0x10)         # Set higher column

            start = page * OLED_WIDTH
            end = start + OLED_WIDTH
            write_data(bus, buffer[start:end])

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