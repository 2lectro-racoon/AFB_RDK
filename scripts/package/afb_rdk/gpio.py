# gpio.py
"""
GPIO helper for STM32 NRST reset.

This module is now focused on a single job:
- drive the STM32 NRST line from the host SBC

Motor/servo control is handled by STM32 over SPI.

RDK X5 note:
- The previous Raspberry Pi-specific mmap backend (/dev/gpiomem, /dev/mem,
  BCM GPIO register base) is not suitable as the primary path here.
- Prefer character-device GPIO backends such as lgpio or gpiod.
"""

import time
from . import _spi_bus

# ================== Configuration ==================
# GPIO line connected to STM32 NRST
# NOTE:
# - This value must match the actual host-side GPIO line used on RDK X5.
# - Update this if the NRST wiring is moved to a different header pin/line.
NRST_GPIO = 23
RESET_PULSE = 0.20      # Reset low time (seconds)
POST_RESET_DELAY = 0.20 # Time to wait after releasing reset (seconds)
# ===================================================


def reset() -> None:
    """Hardware reset for STM32 via NRST GPIO.

    Backend selection order:
        1) lgpio (preferred)
        2) gpiod/libgpiod (fallback)

    This function asserts NRST low, then releases it high.
    For reset usage that is usually sufficient and is the most portable
    approach across non-Raspberry-Pi SBCs such as RDK X5.
    """

    # 1) Prefer lgpio when available.
    try:
        import lgpio  # type: ignore

        h = lgpio.gpiochip_open(0)
        try:
            lgpio.gpio_claim_output(h, NRST_GPIO, 1)

            # Idle high
            lgpio.gpio_write(h, NRST_GPIO, 1)
            time.sleep(0.05)

            # Assert reset (LOW)
            lgpio.gpio_write(h, NRST_GPIO, 0)
            time.sleep(RESET_PULSE)

            # Release reset (HIGH)
            lgpio.gpio_write(h, NRST_GPIO, 1)
            time.sleep(POST_RESET_DELAY)
            return
        finally:
            try:
                lgpio.gpio_free(h, NRST_GPIO)
            except Exception:
                pass
            lgpio.gpiochip_close(h)

    except Exception:
        pass

    # 2) Fallback to gpiod/libgpiod.
    try:
        import gpiod  # type: ignore

        # Try common modern API first.
        if hasattr(gpiod, "request_lines"):
            req = gpiod.request_lines(
                "/dev/gpiochip0",
                consumer="afb_rdk_reset",
                config={
                    NRST_GPIO: gpiod.LineSettings(
                        direction=gpiod.line.Direction.OUTPUT,
                        output_value=gpiod.line.Value.ACTIVE,
                    )
                },
            )
            try:
                # Idle high
                req.set_value(NRST_GPIO, gpiod.line.Value.ACTIVE)
                time.sleep(0.05)

                # Assert reset (LOW)
                req.set_value(NRST_GPIO, gpiod.line.Value.INACTIVE)
                time.sleep(RESET_PULSE)

                # Release reset (HIGH)
                req.set_value(NRST_GPIO, gpiod.line.Value.ACTIVE)
                time.sleep(POST_RESET_DELAY)
                return
            finally:
                req.release()

        # Fallback for older python-gpiod API.
        chip = gpiod.Chip("gpiochip0")
        line = chip.get_line(NRST_GPIO)
        try:
            line.request(consumer="afb_rdk_reset", type=gpiod.LINE_REQ_DIR_OUT, default_vals=[1])
            line.set_value(1)
            time.sleep(0.05)
            line.set_value(0)
            time.sleep(RESET_PULSE)
            line.set_value(1)
            time.sleep(POST_RESET_DELAY)
            return
        finally:
            try:
                line.release()
            except Exception:
                pass

    except Exception as e:
        raise RuntimeError(
            "Failed to toggle STM32 NRST GPIO. Install/use either lgpio or gpiod, "
            "and verify NRST_GPIO matches the correct host GPIO line on RDK X5."
        ) from e


def getMode():
    """Deprecated. GPIO-based mode detection is no longer used."""
    _spi_bus.get_mode()
    time.sleep(0.005)
    rx = _spi_bus.status_request()
    return rx

def stm_release():
    _spi_bus.close()