# gpio.py
"""
GPIO helper for STM32 NRST reset on RDK X5.

- STM32 NRST is connected to Raspberry Pi BCM GPIO23
- On 40-pin header: physical pin 16
- Uses Hobot.GPIO (RDK 공식 방식)
"""

import time
from . import _spi_bus

try:
    import Hobot.GPIO as GPIO
except Exception:
    GPIO = None

# ================== Configuration ==================
NRST_GPIO_BCM = 23      # BCM numbering (라즈와 동일)
NRST_GPIO_BOARD = 16    # 물리핀
RESET_PULSE = 0.20
POST_RESET_DELAY = 0.20
# ===================================================


def reset():
    """STM32 reset using BCM GPIO23"""

    if GPIO is None:
        raise RuntimeError("Hobot.GPIO not available")

    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(NRST_GPIO_BCM, GPIO.OUT)

        # Idle high
        GPIO.output(NRST_GPIO_BCM, GPIO.HIGH)
        time.sleep(0.05)

        # Reset LOW
        GPIO.output(NRST_GPIO_BCM, GPIO.LOW)
        time.sleep(RESET_PULSE)

        # Release HIGH
        GPIO.output(NRST_GPIO_BCM, GPIO.HIGH)
        time.sleep(POST_RESET_DELAY)

    finally:
        GPIO.cleanup(NRST_GPIO_BCM)


def reset_board():
    """Fallback: use physical pin 16"""

    if GPIO is None:
        raise RuntimeError("Hobot.GPIO not available")

    try:
        GPIO.setwarnings(False)
        GPIO.setmode(GPIO.BOARD)
        GPIO.setup(NRST_GPIO_BOARD, GPIO.OUT)

        GPIO.output(NRST_GPIO_BOARD, GPIO.HIGH)
        time.sleep(0.05)

        GPIO.output(NRST_GPIO_BOARD, GPIO.LOW)
        time.sleep(RESET_PULSE)

        GPIO.output(NRST_GPIO_BOARD, GPIO.HIGH)
        time.sleep(POST_RESET_DELAY)

    finally:
        GPIO.cleanup(NRST_GPIO_BOARD)


def getMode():
    _spi_bus.get_mode()
    time.sleep(0.005)
    return _spi_bus.status_request()


def stm_release():
    _spi_bus.close()