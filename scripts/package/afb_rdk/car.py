# car.py
"""Car control API (STM32 firmware: CAR mode).

This module is a thin wrapper around `afb._spi_bus`.
It does NOT open SPI directly; all SPI configuration lives in `_spi_bus.py`.

Public API:
- servo(angle=90, ch=0): set steering servo
- motor(speed=0, inverse=1): set drive motor speed

Notes:
- `inverse` is kept for backward compatibility with legacy GPIO control.
- This module auto-selects CAR mode (mode=0) before sending commands.
"""

from __future__ import annotations

from typing import List

from . import _spi_bus


def servo(angle: int = 90) -> List[int]:
    """Set steering servo angle.

    Args:
        angle: 0..180 degrees
        ch: servo channel (default 0 for steering)

    Returns:
        The 6-byte STM32 response as list[int].
    """
    return _spi_bus.servo_set(0, angle)


def motor(speed: int = 0, inverse: int = 1) -> List[int]:
    """Set drive motor speed.

    Args:
        speed: -255..255 (sign indicates direction)
        inverse: 1 keeps sign as-is, -1 flips sign (legacy compatibility)

    Returns:
        The 6-byte STM32 response as list[int].
    """
    s = int(speed) * int(inverse)

    return _spi_bus.motor_speed(s)


def stop() -> None:
    """Convenience: stop the car."""
    motor(0)
    servo(90)
