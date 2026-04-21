# quad.py
"""Quad control API (STM32 firmware: Quad mode).

This module is a thin wrapper around `afb._spi_bus`.
It does NOT open SPI directly; all SPI configuration lives in `_spi_bus.py`.

Public API:
- servo(ch, angle): set each servo angle
- leg(ch, angle0, angle1, angle2): set leg angle

Notes:
"""

from __future__ import annotations

import threading
import time
from typing import List, Optional

from . import _spi_bus

# Last-sent servo angles cache (debug purpose).
# Index: channel 0..11, Value: angle int (0..180) or None if never sent.
_last_angles: List[Optional[int]] = [None] * 12
_last_angles_lock = threading.Lock()


def _cache_set_one(ch: int, angle: int) -> None:
    """Update cache for a single channel.

    This is based on 'send attempt' semantics (we cache the value before sending).
    """
    if 0 <= ch < 12:
        _last_angles[ch] = int(angle)


def _cache_set_leg(leg_idx: int, a0: int, a1: int, a2: int) -> None:
    """Update cache for a leg (3 channels) atomically as one bundle."""
    base = int(leg_idx) * 3
    if 0 <= base < 12:
        # Update all three under one lock so readers see a consistent snapshot.
        _cache_set_one(base + 0, a0)
        _cache_set_one(base + 1, a1)
        _cache_set_one(base + 2, a2)


def _servo_set_cached(ch: int, angle: int) -> List[int]:
    """Cache angle (send-attempt semantics) then send via SPI."""
    with _last_angles_lock:
        _cache_set_one(int(ch), int(angle))
    return _spi_bus.servo_set(int(ch), int(angle))


def servo(ch, angle) -> List[int]:
    """Set a single servo channel angle.

    This updates the last-sent cache before attempting the SPI transfer.
    """
    return _servo_set_cached(ch, angle)


def getAngle() -> List[Optional[int]]:
    """Return a snapshot of the last-sent angles (length 12)."""
    with _last_angles_lock:
        return list(_last_angles)


def clearAngle() -> None:
    """Clear the last-sent angles cache (set all to None)."""
    with _last_angles_lock:
        for i in range(12):
            _last_angles[i] = None


# Motor direction + speed
def leg(ch, a0, a1, a2) -> None:
    """Set a 3-DOF leg (3 channels).

    Cache update is done as a single bundle so the UI sees all three values together.
    SPI transfers are still sent sequentially.
    """
    leg_idx = int(ch)
    a0 = int(a0)
    a1 = int(a1)
    a2 = int(a2)

    with _last_angles_lock:
        _cache_set_leg(leg_idx, a0, a1, a2)

    _spi_bus.leg_set(leg_idx, a0, a1, a2)

def legReset() -> None:

    time.sleep(0.5)
    _servo_set_cached(0, 40)
    _servo_set_cached(3, 135)
    _servo_set_cached(6, 40)
    _servo_set_cached(9, 135)
    time.sleep(0.5)
    _servo_set_cached(1, 0)
    _servo_set_cached(4, 180)
    _servo_set_cached(7, 0)
    _servo_set_cached(10, 180)
    time.sleep(0.5)
    _servo_set_cached(2, 180)
    _servo_set_cached(5, 0)
    _servo_set_cached(8, 180)
    _servo_set_cached(11, 0)
    time.sleep(0.5)

def stand() -> None:

    time.sleep(0.5)
    _servo_set_cached(0, 90)
    _servo_set_cached(3, 90)
    _servo_set_cached(6, 90)
    _servo_set_cached(9, 90)
    time.sleep(0.5)
    _servo_set_cached(1, 60)
    _servo_set_cached(4, 140)
    _servo_set_cached(7, 40)
    _servo_set_cached(10, 120)
    time.sleep(0.5)
    _servo_set_cached(2, 70)
    _servo_set_cached(5, 110)
    _servo_set_cached(8, 70)
    _servo_set_cached(11, 110)
    time.sleep(0.5)