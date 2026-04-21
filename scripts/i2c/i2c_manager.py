
#!/usr/bin/env python3

import time
import threading
import signal
from smbus2 import SMBus, i2c_msg
from PIL import Image, ImageDraw, ImageFont

I2C_BUS = 5
OLED_ADDR = 0x3C
INA219_ADDR = 0x40
WIDTH = 128
HEIGHT = 32

class OLED:
    def __init__(self, bus):
        self.bus = bus
        self.pages = HEIGHT // 8
        self.buffer = bytearray(WIDTH * self.pages)
        self.init()

    def cmd(self, c):
        self.bus.write_byte_data(OLED_ADDR, 0x00, c)

    def data(self, data):
        for i in range(0, len(data), 16):
            chunk = data[i:i+16]
            msg = i2c_msg.write(OLED_ADDR, bytes([0x40]) + bytes(chunk))
            self.bus.i2c_rdwr(msg)

    def init(self):
        init_seq = [
            0xAE, 0xD5, 0x80, 0xA8, 0x1F,
            0xD3, 0x00, 0x40, 0x8D, 0x14,
            0x20, 0x00, 0xA1, 0xC8, 0xDA, 0x02,
            0x81, 0x8F, 0xD9, 0xF1, 0xDB, 0x40,
            0xA4, 0xA6, 0x2E, 0xAF
        ]
        for c in init_seq:
            self.cmd(c)
        self.fill(0)
        self.show()

    def fill(self, v):
        self.buffer[:] = [0xFF if v else 0x00] * len(self.buffer)

    def show(self):
        for p in range(self.pages):
            self.cmd(0xB0+p)
            self.cmd(0)
            self.cmd(0x10)
            self.data(self.buffer[p*WIDTH:(p+1)*WIDTH])

class INA219:
    def __init__(self, bus):
        self.bus = bus

    def read_voltage(self):
        raw = self.bus.read_word_data(INA219_ADDR, 2)
        raw = ((raw & 0xFF) << 8) | (raw >> 8)
        return (raw >> 3) * 0.004

class Manager:
    def __init__(self):
        self.bus = SMBus(I2C_BUS)
        self.oled = OLED(self.bus)
        self.ina = INA219(self.bus)
        self.stop = False
        self.voltage = 0.0

    def loop_ina(self):
        while not self.stop:
            try:
                self.voltage = self.ina.read_voltage()
            except Exception as e:
                print("INA error:", e)
            time.sleep(0.1)

    def loop_oled(self):
        font = ImageFont.load_default()
        while not self.stop:
            img = Image.new("1", (WIDTH, HEIGHT))
            draw = ImageDraw.Draw(img)
            draw.text((0,0), f"V:{self.voltage:.2f}", font=font, fill=255)

            # Convert PIL image to OLED buffer
            pixels = img.load()
            buf = bytearray(WIDTH * (HEIGHT // 8))
            for y in range(HEIGHT):
                for x in range(WIDTH):
                    if pixels[x, y]:
                        buf[x + (y//8)*WIDTH] |= 1 << (y % 8)

            self.oled.buffer = buf
            self.oled.show()
            time.sleep(0.5)

    def run(self):
        threading.Thread(target=self.loop_ina, daemon=True).start()
        threading.Thread(target=self.loop_oled, daemon=True).start()
        while not self.stop:
            time.sleep(1)

if __name__ == "__main__":
    m = Manager()
    signal.signal(signal.SIGTERM, lambda s,f: setattr(m, 'stop', True))
    signal.signal(signal.SIGINT, lambda s,f: setattr(m, 'stop', True))
    m.run()
