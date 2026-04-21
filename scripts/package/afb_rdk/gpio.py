# gpio.py
"""
Deprecated GPIO helper (v2.0 transitional).

Currently used only for STM32 NRST reset via Raspberry Pi GPIO.
All motor/servo control has moved to STM32 via SPI.
"""

import mmap
import os
import struct
import time
from . import _spi_bus

# ================== Configuration ==================
# BCM pin connected to STM32 NRST
NRST_GPIO = 23          # BCM numbering
RESET_PULSE = 0.20      # Reset low time (seconds)
POST_RESET_DELAY = 0.20 # Time to wait after releasing reset (seconds)
# ===================================================

# Raspberry Pi 4/5 GPIO base
GPIO_BASE = 0xFE200000
# mmap length must be page-aligned on some kernels/drivers.
# We only need a small subset of registers, but map at least one page.
GPIO_LEN  = 0x1000

# GPIO register offsets
GPFSEL0 = 0x00
GPFSEL1 = 0x04
GPFSEL2 = 0x08
GPSET0  = 0x1C
GPCLR0  = 0x28


# ------------------ Low-level helpers ------------------

def _gpio_set_output(mem, pin: int) -> None:
    reg = GPFSEL0 + (pin // 10) * 4
    shift = (pin % 10) * 3

    val = struct.unpack("I", mem[reg:reg + 4])[0]
    val &= ~(0b111 << shift)     # clear
    val |=  (0b001 << shift)     # output
    mem[reg:reg + 4] = struct.pack("I", val)


def _gpio_set_input(mem, pin: int) -> None:
    """Release NRST line (High-Z)."""
    reg = GPFSEL0 + (pin // 10) * 4
    shift = (pin % 10) * 3

    val = struct.unpack("I", mem[reg:reg + 4])[0]
    val &= ~(0b111 << shift)     # INPUT (000)
    mem[reg:reg + 4] = struct.pack("I", val)


def _gpio_high(mem, pin: int) -> None:
    mem[GPSET0:GPSET0 + 4] = struct.pack("I", 1 << pin)


def _gpio_low(mem, pin: int) -> None:
    mem[GPCLR0:GPCLR0 + 4] = struct.pack("I", 1 << pin)


# ------------------ Public API ------------------

def reset() -> None:
    """Hardware reset for STM32 via NRST GPIO.

    mmap backend selection order:
        1) /dev/gpiomem mmap (preferred when available)
        2) /dev/mem mmap at GPIO_BASE (fallback; typically requires sudo/root)

    This function asserts NRST low, then releases it and finally
    switches the pin to INPUT (High-Z) so STM32 internal pull-up
    takes over.

    Usage:
        >>> import afb.gpio
        >>> afb.gpio.reset()
    """
    fd = None
    mem = None

    # Prefer lgpio when available (reliable across Pi 4/5 and different kernel mappings).
    # This avoids fragile /dev/mem or gpiomem register layouts.
    try:
        import lgpio  # type: ignore

        h = lgpio.gpiochip_open(0)
        try:
            # Drive NRST actively (push-pull) during the pulse.
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

            # Release NRST line (High-Z) so STM32 internal pull-up takes over.
            # Not strictly required, but matches typical NRST wiring expectations.
            lgpio.gpio_free(h, NRST_GPIO)
            lgpio.gpio_claim_input(h, NRST_GPIO)

            return
        finally:
            lgpio.gpiochip_close(h)

    except Exception:
        # Fall back to mmap method below.
        pass

    def _open_mmap() -> tuple[int, mmap.mmap]:
        """Open an mmap for GPIO registers.

        Returns:
            (fd, mem) where mem is positioned at the GPIO register base.

        Notes:
            - /dev/gpiomem maps the GPIO block starting at offset 0.
            - /dev/mem requires mapping the physical GPIO base address.
        """
        # 1) Try gpiomem devices first (no root typically required).
        #
        # On newer kernels (e.g., Raspberry Pi 5), the driver may expose multiple
        # devices like /dev/gpiomem0..N. Only gpiomem0 contains the full GPIO window
        # we need (GPFSEL/GPSET/GPCLR). The other region devices are tiny windows
        # (e.g., 0x20/0x40) and will fail mmap if we request a full page.
        gpiomem_candidates = ["/dev/gpiomem0", "/dev/gpiomem"]

        for path in gpiomem_candidates:
            try:
                _fd = os.open(path, os.O_RDWR | os.O_SYNC)

                # Raspberry Pi 5 gpiomem0 GPIO window size is commonly 0x30000.
                # Try mapping the full window first, then fall back to one page.
                lengths = [0x30000, max(GPIO_LEN, mmap.PAGESIZE)] if path.endswith("gpiomem0") else [max(GPIO_LEN, mmap.PAGESIZE)]

                for length in lengths:
                    try:
                        _mem = mmap.mmap(
                            _fd,
                            length,
                            mmap.MAP_SHARED,
                            mmap.PROT_READ | mmap.PROT_WRITE,
                            offset=0,
                        )
                        return _fd, _mem
                    except OSError:
                        # Try the next length (or next candidate)
                        continue

                os.close(_fd)

            except FileNotFoundError:
                continue
            except PermissionError:
                # If a candidate exists but is not accessible, keep searching.
                continue

        # 2) Fallback to /dev/mem (usually needs root privileges).
        _fd = os.open("/dev/mem", os.O_RDWR | os.O_SYNC)

        # mmap offset must be page-aligned
        page_size = mmap.PAGESIZE
        page_mask = ~(page_size - 1)
        base = GPIO_BASE & page_mask
        delta = GPIO_BASE - base

        _mem_full = mmap.mmap(
            _fd,
            max(GPIO_LEN, mmap.PAGESIZE) + delta,
            mmap.MAP_SHARED,
            mmap.PROT_READ | mmap.PROT_WRITE,
            offset=base,
        )

        effective_len = max(GPIO_LEN, mmap.PAGESIZE)
        _mem = memoryview(_mem_full)[delta:delta + effective_len]

        # Wrap a lightweight object that exposes the same slicing interface
        class _MemWrap:
            def __init__(self, mv, parent):
                self._mv = mv
                self._parent = parent

            def __getitem__(self, key):
                return self._mv.__getitem__(key).tobytes() if isinstance(key, slice) else self._mv[key]

            def __setitem__(self, key, value):
                self._mv.__setitem__(key, value)

            def close(self):
                # Close the parent mmap
                self._parent.close()

        return _fd, _MemWrap(_mem, _mem_full)

    try:
        fd, mem = _open_mmap()

        # 1) Configure as output
        _gpio_set_output(mem, NRST_GPIO)

        # 2) Idle high
        _gpio_high(mem, NRST_GPIO)
        time.sleep(0.05)

        # 3) Assert reset (LOW)
        _gpio_low(mem, NRST_GPIO)
        time.sleep(RESET_PULSE)

        # 4) Release reset (HIGH)
        _gpio_high(mem, NRST_GPIO)
        time.sleep(POST_RESET_DELAY)

        # 5) Release NRST line (High-Z)
        _gpio_set_input(mem, NRST_GPIO)

    except PermissionError as e:
        raise PermissionError(
            "GPIO mmap failed due to insufficient permissions. "
            "If /dev/gpiomem (or /dev/gpiomem0..N) is missing, the fallback uses /dev/mem which typically "
            "requires sudo/root. Try running with sudo, or enable /dev/gpiomem on your system."
        ) from e

    except FileNotFoundError as e:
        raise FileNotFoundError(
            "Neither /dev/gpiomem nor /dev/mem is available. "
            "This environment cannot perform GPIO mmap access."
        ) from e

    finally:
        if mem is not None:
            mem.close()
        if fd is not None:
            os.close(fd)


def getMode():
    """Deprecated. GPIO-based mode detection is no longer used."""
    _spi_bus.get_mode()
    time.sleep(float(0.005))
    rx=_spi_bus.status_request()
    
    return rx

def stm_release():
    _spi_bus.close()