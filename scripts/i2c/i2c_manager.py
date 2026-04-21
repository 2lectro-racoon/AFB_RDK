#!/usr/bin/env python3
"""I2C Manager (single owner of /dev/i2c-*)

- Reads:
  - INA219 (bus voltage / current / power)
  - VL53L1X (distance)
  - MPU6xxx (MPU6050/MPU6500-class) (accel / gyro / temp) [optional]
- Displays on OLED:
  - Wi-Fi mode (STA/AP), SSID, IP
  - Battery percent (INA219 voltage-based)
- IPC:
  - Unix Domain Socket (datagram) server: /run/afb_i2c.sock
  - Request: JSON bytes (e.g. {"cmd":"get"})
  - Response: JSON dict with latest cached readings

This process should be started by systemd using the venv python:
  ExecStart=/home/pi/.afbvenv/bin/python3 .../i2c_manager.py

Notes:
- Keep this as the ONLY process that touches I2C devices.
- Other processes must read sensor values via IPC (UDS) from this manager.
"""

from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import threading
import time
import csv
import getpass
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

import board
import busio
from PIL import Image, ImageDraw, ImageFont

import adafruit_ssd1306
from adafruit_ina219 import INA219
import adafruit_vl53l1x

try:
    import adafruit_vl53l0x
except Exception:  # pragma: no cover
    adafruit_vl53l0x = None  # type: ignore



# ----------------------------
# Minimal MPU6050/MPU6500 compatible reader
# ----------------------------

class _MPU6xxxCompat:
    """A tiny MPU6050/MPU6500 compatible reader.

    Why this exists:
    - Many "MPU6050" modules ship with MPU6500-class parts.
    - WHO_AM_I differs (MPU6050 -> 0x68, MPU6500 -> 0x70), and some libraries reject it.

    This reader supports both as long as the register map is compatible.
    """

    # Registers
    _REG_WHO_AM_I = 0x75
    _REG_PWR_MGMT_1 = 0x6B
    _REG_ACCEL_XOUT_H = 0x3B

    def __init__(self, i2c: busio.I2C, address: int = 0x68) -> None:
        self.i2c = i2c
        self.address = int(address)

        who = self._read_u8(self._REG_WHO_AM_I)
        # Accept common IDs: MPU6050(0x68), MPU6500(0x70). Keep it permissive.
        if who not in (0x68, 0x70):
            raise ValueError(f"Unsupported MPU WHO_AM_I=0x{who:02x} at 0x{self.address:02x}")

        # Wake up device (clear sleep bit)
        self._write_u8(self._REG_PWR_MGMT_1, 0x00)
        time.sleep(0.05)

    def _write_u8(self, reg: int, val: int) -> None:
        buf = bytes([reg & 0xFF, val & 0xFF])
        self.i2c.writeto(self.address, buf)

    def _read_u8(self, reg: int) -> int:
        """Read a single byte from a register.

        NOTE: `busio.I2C.writeto(..., stop=False)` is not supported on some Blinka versions.
        Use `writeto_then_readfrom` when available (repeated-start), otherwise fall back to
        a separate write+read.
        """
        out = bytearray(1)
        reg_b = bytes([reg & 0xFF])

        if hasattr(self.i2c, "writeto_then_readfrom"):
            # Repeated-start (preferred)
            self.i2c.writeto_then_readfrom(self.address, reg_b, out)
        else:
            # Fallback: write register pointer, then read
            self.i2c.writeto(self.address, reg_b)
            self.i2c.readfrom_into(self.address, out)

        return int(out[0])

    @staticmethod
    def _i16(msb: int, lsb: int) -> int:
        v = ((msb & 0xFF) << 8) | (lsb & 0xFF)
        return v - 65536 if v & 0x8000 else v

    def read(self) -> Tuple[Tuple[float, float, float], Tuple[float, float, float], float]:
        """Return (accel_m_s2, gyro_rad_s, temp_c)."""
        buf = bytearray(14)
        reg_b = bytes([self._REG_ACCEL_XOUT_H])
        if hasattr(self.i2c, "writeto_then_readfrom"):
            self.i2c.writeto_then_readfrom(self.address, reg_b, buf)
        else:
            self.i2c.writeto(self.address, reg_b)
            self.i2c.readfrom_into(self.address, buf)

        ax = self._i16(buf[0], buf[1])
        ay = self._i16(buf[2], buf[3])
        az = self._i16(buf[4], buf[5])
        temp_raw = self._i16(buf[6], buf[7])
        gx = self._i16(buf[8], buf[9])
        gy = self._i16(buf[10], buf[11])
        gz = self._i16(buf[12], buf[13])

        # Assuming default ranges: accel +/-2g, gyro +/-250 dps
        # Accel sensitivity: 16384 LSB/g
        g_to_m_s2 = 9.80665
        ax_m = (ax / 16384.0) * g_to_m_s2
        ay_m = (ay / 16384.0) * g_to_m_s2
        az_m = (az / 16384.0) * g_to_m_s2

        # Gyro sensitivity: 131 LSB/(deg/s)
        dps_to_rad_s = 3.141592653589793 / 180.0
        gx_r = (gx / 131.0) * dps_to_rad_s
        gy_r = (gy / 131.0) * dps_to_rad_s
        gz_r = (gz / 131.0) * dps_to_rad_s

        # Temperature in C: temp_raw/340 + 36.53
        temp_c = (temp_raw / 340.0) + 36.53

        return (ax_m, ay_m, az_m), (gx_r, gy_r, gz_r), float(temp_c)


# ----------------------------
# Configuration
# ----------------------------

UDS_PATH = "/run/autoformbot/afb_i2c.sock"

OLED_WIDTH = 128
OLED_HEIGHT = 32

#
# Update rates (Hz)
SENSOR_HZ_VL53 = 10.0  # Match VL53L1X timing_budget=100ms
SENSOR_HZ_INA = 10.0
SENSOR_HZ_MPU = 100.0
OLED_HZ = 2.0

# CSV logging
# Logs are stored under /home/<USER>/afb_home/i2c_sensor_log_YYYY-MM-DD.csv by default.
# USER can be overridden via env var AFB_USER (recommended for systemd).
LOG_HZ = 10.0
LOG_DIR_NAME = "afb_home"

# Daily rolling:
#   /home/<USER>/afb_home/i2c_sensor_log_YYYY-MM-DD.csv
# A best-effort symlink is maintained:
#   /home/<USER>/afb_home/i2c_sensor_log.csv  -> today's file
LOG_BASE_NAME = "i2c_sensor_log"
LOG_EXT = ".csv"
LOG_FLUSH_SEC = 1.0

# Battery percent estimation from INA219 bus voltage (2S Li-ion default)
# - Use a LUT (piecewise linear interpolation) for a more realistic SoC curve.
# - Apply EMA smoothing to reduce jitter from load-induced voltage ripple.
#
# You MUST tune this LUT for your battery, wiring, and load.
# Values are pack voltage (V) -> percent (%).
BAT_LUT_2S = [
    (6.40, 0),
    (6.60, 5),
    (6.80, 10),
    (7.00, 20),
    (7.20, 35),
    (7.40, 50),
    (7.60, 65),
    (7.80, 80),
    (8.00, 92),
    (8.20, 100),
]

# EMA filter alpha: 0..1 (higher = less smoothing, more responsive)
BAT_VOLT_EWA_ALPHA = 0.25


# ----------------------------
# Helpers
# ----------------------------


def _run_cmd(cmd: list[str], timeout_s: float = 1.0) -> Tuple[int, str]:
    """Run a command and return (returncode, stdout_str)."""
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout_s)
        return 0, out.decode("utf-8", errors="replace").strip()
    except subprocess.CalledProcessError as e:
        return int(e.returncode), ""
    except Exception:
        return 1, ""


def get_ssid() -> str:
    """Best-effort SSID read for STA mode."""
    # iwgetid is commonly available on Raspberry Pi OS
    rc, out = _run_cmd(["iwgetid", "-r"], timeout_s=0.8)
    if rc == 0 and out:
        return out

    # Fallback to nmcli if installed
    rc, out = _run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"], timeout_s=1.0)
    if rc == 0 and out:
        # Lines look like: yes:<ssid>
        for line in out.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1].strip()

    return ""


def get_ap_ssid() -> str:
    """Best-effort AP SSID read for hostapd / NetworkManager hotspot.

    Tries, in order:
    1) hostapd_cli status (fast, if available)
    2) /etc/hostapd/hostapd.conf (common on Raspberry Pi OS)
    3) nmcli active connections (when AP is managed by NetworkManager)
    """
    # 1) hostapd_cli
    rc, out = _run_cmd(["hostapd_cli", "-i", "wlan0", "status"], timeout_s=0.8)
    if rc == 0 and out:
        for line in out.splitlines():
            if line.startswith("ssid="):
                ssid = line.split("=", 1)[1].strip()
                if ssid:
                    return ssid

    # 2) hostapd.conf
    conf_candidates = ["/etc/hostapd/hostapd.conf", "/etc/hostapd.conf"]
    for conf in conf_candidates:
        try:
            with open(conf, "r", encoding="utf-8", errors="ignore") as f:
                for line in f:
                    s = line.strip()
                    if not s or s.startswith("#"):
                        continue
                    if s.startswith("ssid="):
                        ssid = s.split("=", 1)[1].strip()
                        if ssid:
                            return ssid
        except Exception:
            pass

    # 3) nmcli active hotspot
    rc, out = _run_cmd(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show", "--active"], timeout_s=1.0)
    if rc == 0 and out:
        # Lines look like: <name>:wifi
        for line in out.splitlines():
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1].strip() == "wifi":
                name = parts[0].strip()
                if name:
                    return name

    return ""


def get_ip_addr(ifname: str) -> str:
    """Get IPv4 address for an interface via `ip` (no extra deps)."""
    rc, out = _run_cmd(["ip", "-4", "addr", "show", ifname], timeout_s=0.8)
    if rc != 0 or not out:
        return ""

    # Parse 'inet X.X.X.X/..'
    for line in out.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            ip_with_mask = line.split()[1]
            return ip_with_mask.split("/")[0]
    return ""


def detect_mode_and_ip() -> Tuple[str, str, str]:
    """Return (mode, ssid, ip).

    Heuristic:
    - If an SSID exists: STA
    - Else if hostapd is active: AP
    - Else: UNKNOWN

    IP is chosen in order: wlan0, eth0.
    """
    ssid = get_ssid()

    if ssid:
        mode = "STA"
    else:
        rc, out = _run_cmd(["systemctl", "is-active", "hostapd"], timeout_s=0.6)
        is_ap = (rc == 0 and out.strip() == "active")
        mode = "AP" if is_ap else "UNKNOWN"
        if is_ap:
            ap_ssid = get_ap_ssid()
            if ap_ssid:
                ssid = ap_ssid

    ip = get_ip_addr("eth0")
    if not ip:
        ip = get_ip_addr("wlan0")

    return mode, ssid, ip


def estimate_battery_percent(bus_voltage_v: Optional[float]) -> Optional[int]:
    """Estimate battery percent from pack voltage using LUT interpolation.

    - Voltages above the highest LUT voltage are clamped to 100%.
    - Voltages below the lowest LUT voltage are clamped to 0%.

    The LUT is defined by BAT_LUT_2S and assumed to be sorted by voltage.
    """
    if bus_voltage_v is None:
        return None

    v = float(bus_voltage_v)
    lut = BAT_LUT_2S

    if not lut:
        return None

    # Clamp to ends
    if v <= lut[0][0]:
        return int(lut[0][1])
    if v >= lut[-1][0]:
        return int(lut[-1][1])

    # Find segment and interpolate
    for (v0, p0), (v1, p1) in zip(lut[:-1], lut[1:]):
        if v0 <= v <= v1:
            if v1 == v0:
                return int(p1)
            t = (v - v0) / (v1 - v0)
            pct = p0 + t * (p1 - p0)
            return int(round(max(0.0, min(100.0, pct))))

    # Fallback (should not happen)
    return int(lut[-1][1])


# ----------------------------
# Shared state
# ----------------------------


@dataclass
class SensorCache:
    ts: float = 0.0
    distance_mm: Optional[float] = None
    imu_accel_m_s2: Optional[Tuple[float, float, float]] = None
    imu_gyro_rad_s: Optional[Tuple[float, float, float]] = None
    imu_temp_c: Optional[float] = None
    bus_voltage_v: Optional[float] = None
    bus_voltage_v_raw: Optional[float] = None
    bus_voltage_v_filt: Optional[float] = None
    current_mA: Optional[float] = None
    power_mW: Optional[float] = None
    battery_percent: Optional[int] = None
    mode: str = ""
    ssid: str = ""
    ip: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "ts": self.ts,
            "distance_mm": self.distance_mm,
            "ina219": {
                "bus_voltage_v": self.bus_voltage_v,
                "bus_voltage_v_raw": self.bus_voltage_v_raw,
                "bus_voltage_v_filt": self.bus_voltage_v_filt,
                "current_mA": self.current_mA,
                "power_mW": self.power_mW,
            },
            "battery_percent": self.battery_percent,
            "net": {
                "mode": self.mode,
                "ssid": self.ssid,
                "ip": self.ip,
            },
        }

    def to_ipc_dict(self) -> Dict[str, Any]:
        """Return a minimal payload for IPC consumers (driving/control loops)."""
        return {
            "ts": self.ts,
            "distance_mm": self.distance_mm,
            "imu": {
                "accel_m_s2": self.imu_accel_m_s2,
                "gyro_rad_s": self.imu_gyro_rad_s,
                "temp_c": self.imu_temp_c,
            },
        }


# ----------------------------
# Main I2C manager
# ----------------------------


class I2CManager:
    def __init__(self) -> None:
        self.stop_event = threading.Event()
        self.lock = threading.Lock()
        self.cache = SensorCache()

        # I2C bus
        self.i2c = busio.I2C(board.SCL, board.SDA)

        # Devices
        # Optional INA219 (battery monitor)
        self.ina = None
        try:
            self.ina = INA219(self.i2c)
        except Exception:
            self.ina = None

        # Optional distance sensor (VL53L0X / VL53L1X)
        # Priority: try VL53L0X first, then fall back to VL53L1X.
        self.tof = None
        self.tof_kind: str = ""  # "l0x" | "l1x" | ""

        # Try VL53L0X
        if adafruit_vl53l0x is not None:
            try:
                self.tof = adafruit_vl53l0x.VL53L0X(self.i2c)
                # Typical timing budgets: ~20ms (faster) to 200ms (smoother)
                # Keep it modest to match the 10Hz loop.
                try:
                    self.tof.measurement_timing_budget = 20000  # us
                except Exception:
                    pass
                self.tof_kind = "l0x"
            except Exception:
                self.tof = None
                self.tof_kind = ""

        # Fall back to VL53L1X
        if self.tof is None:
            try:
                self.tof = adafruit_vl53l1x.VL53L1X(self.i2c)
                self.tof.distance_mode = 1  # short
                self.tof.timing_budget = 100  # ms
                self.tof.start_ranging()
                self.tof_kind = "l1x"
            except Exception:
                self.tof = None
                self.tof_kind = ""

        # Optional IMU (MPU6050 / MPU6500-class)
        # Use the common register-map reader only (education-friendly, robust to clone parts).
        self.mpu = None
        try:
            self.mpu = _MPU6xxxCompat(self.i2c, address=0x68)
        except Exception:
            self.mpu = None

        self.oled = adafruit_ssd1306.SSD1306_I2C(OLED_WIDTH, OLED_HEIGHT, self.i2c)
        self.oled.fill(0)
        self.oled.show()

        # OLED drawing objects
        self.font = ImageFont.load_default()

        # UDS server socket
        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

        # Ensure runtime directory exists and is writable, then clean old socket
        uds_dir = os.path.dirname(UDS_PATH)
        try:
            os.makedirs(uds_dir, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Failed to create UDS directory: {uds_dir}: {e}")

        if not os.access(uds_dir, os.W_OK | os.X_OK):
            raise PermissionError(
                f"UDS directory is not writable: {uds_dir}. "
                "If running under systemd, set RuntimeDirectory=autoformbot (or run as root)."
            )

        try:
            if os.path.exists(UDS_PATH):
                os.unlink(UDS_PATH)
        except Exception:
            pass

        self.sock.bind(UDS_PATH)

        # Make it readable/writable by non-root users (education-friendly)
        # Note: For production, prefer a dedicated group + 0660.
        try:
            os.chmod(UDS_PATH, 0o666)
        except Exception:
            pass

        # EMA state for battery voltage smoothing
        self._bus_v_ema: Optional[float] = None

        # Keep last valid distance to avoid jitter/None when a frame isn't ready
        self._last_distance_mm: Optional[int] = None

        # CSV logger (10Hz)
        self._log_file = None
        self._log_writer = None
        self._log_lock = threading.Lock()
        self._log_buf: list[list[Any]] = []
        self._log_last_flush = time.time()
        self._log_date: Optional[str] = None

        # Determine target user/home. Prefer explicit env override for reproducibility.
        log_user = os.environ.get("AFB_USER") or os.environ.get("SUDO_USER") or os.environ.get("USER") or getpass.getuser()
        home_dir = os.path.expanduser(f"~{log_user}")
        if not home_dir or home_dir == "~":
            home_dir = os.path.expanduser("~")

        self._log_dir = os.path.join(home_dir, LOG_DIR_NAME)

        try:
            os.makedirs(self._log_dir, exist_ok=True)
        except Exception as e:
            raise RuntimeError(f"Failed to create log directory: {self._log_dir}: {e}")

        # Open today's file
        self._open_log_for_time(time.time())

    def close(self) -> None:
        # Clear OLED on shutdown
        try:
            self.oled.fill(0)
            self.oled.show()
        except Exception:
            pass

        if self.tof is not None and self.tof_kind == "l1x":
            try:
                self.tof.stop_ranging()
            except Exception:
                pass

        # Close CSV logger
        try:
            if self._log_writer is not None and self._log_file is not None and self._log_buf:
                for r in self._log_buf:
                    self._log_writer.writerow(r)
                self._log_buf.clear()
                self._log_file.flush()
            if self._log_file is not None:
                self._log_file.flush()
                self._log_file.close()
        except Exception:
            pass

        # Close UDS socket and remove socket file
        try:
            self.sock.close()
        except Exception:
            pass

        try:
            if os.path.exists(UDS_PATH):
                os.unlink(UDS_PATH)
        except Exception:
            pass

    def _log_header(self) -> list[str]:
        return [
            "timestamp_iso",
            "ts_unix",
            "distance_mm",
            "imu_ax_m_s2",
            "imu_ay_m_s2",
            "imu_az_m_s2",
            "imu_gx_rad_s",
            "imu_gy_rad_s",
            "imu_gz_rad_s",
            "imu_temp_c",
        ]

    def _open_log_for_time(self, t_unix: float) -> None:
        """Open (or rotate to) the daily CSV log file for the given unix time."""
        date_str = time.strftime("%Y-%m-%d", time.localtime(t_unix))
        if self._log_date == date_str and self._log_file is not None and self._log_writer is not None:
            return

        # Close existing file
        try:
            if self._log_file is not None:
                self._log_file.flush()
                self._log_file.close()
        except Exception:
            pass

        self._log_file = None
        self._log_writer = None

        # Build path like: i2c_sensor_log_YYYY-MM-DD.csv
        dated_name = f"{LOG_BASE_NAME}_{date_str}{LOG_EXT}"
        self._log_path = os.path.join(self._log_dir, dated_name)

        # Open CSV in append mode; write header if it's a new file
        try:
            is_new = not os.path.exists(self._log_path) or os.path.getsize(self._log_path) == 0
            self._log_file = open(self._log_path, "a", encoding="utf-8", newline="")
            self._log_writer = csv.writer(self._log_file)
            if is_new:
                self._log_writer.writerow(self._log_header())
                self._log_file.flush()
        except Exception as e:
            raise RuntimeError(f"Failed to open CSV log file: {self._log_path}: {e}")

        self._log_date = date_str

        # Best-effort: keep a stable symlink to today's file
        # /home/<USER>/afb_home/i2c_sensor_log.csv -> i2c_sensor_log_YYYY-MM-DD.csv
        try:
            link_path = os.path.join(self._log_dir, f"{LOG_BASE_NAME}{LOG_EXT}")
            tmp_link = link_path + ".tmp"
            try:
                if os.path.islink(tmp_link) or os.path.exists(tmp_link):
                    os.unlink(tmp_link)
            except Exception:
                pass
            os.symlink(self._log_path, tmp_link)
            os.replace(tmp_link, link_path)
        except Exception:
            # Symlink may fail on some systems/permissions; ignore.
            pass
    def _loop_csv_logger(self) -> None:
        """Log distance + IMU readings to CSV at a fixed rate.

        This logs the latest cached values (single-owner I2C model) rather than
        reading sensors directly here.
        """
        period = 1.0 / max(LOG_HZ, 1.0)
        while not self.stop_event.is_set():
            t0 = time.time()

            with self.lock:
                dist = self.cache.distance_mm
                accel = self.cache.imu_accel_m_s2
                gyro = self.cache.imu_gyro_rad_s
                temp_c = self.cache.imu_temp_c

            # Convert timestamp to ISO string in local time
            iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)) + f".{int((t0 % 1.0) * 1000):03d}"

            # Rotate daily (local time)
            try:
                self._open_log_for_time(t0)
            except Exception:
                # If rotation/open fails, keep running without crashing
                pass

            # Use string markers when a value is not available:
            # - "NC": sensor Not Connected / not detected
            # - "NL": No Latest reading available yet
            # NOTE: This makes the CSV columns mixed-type (numbers + strings).

            # Distance
            if self.tof is None:
                dist_out: Any = "NC"
            else:
                dist_out = "NL" if dist is None else int(dist)

            # IMU
            if self.mpu is None:
                ax = ay = az = "NC"
                gx = gy = gz = "NC"
                temp_out: Any = "NC"
            else:
                if accel is None:
                    ax = ay = az = "NL"
                else:
                    ax, ay, az = accel

                if gyro is None:
                    gx = gy = gz = "NL"
                else:
                    gx, gy, gz = gyro

                temp_out = "NL" if temp_c is None else float(temp_c)

            try:
                if self._log_writer is not None and self._log_file is not None:
                    row = [iso, f"{t0:.6f}", dist_out, ax, ay, az, gx, gy, gz, temp_out]
                    with self._log_lock:
                        self._log_buf.append(row)
                        if (t0 - self._log_last_flush) >= float(LOG_FLUSH_SEC):
                            for r in self._log_buf:
                                self._log_writer.writerow(r)
                            self._log_buf.clear()
                            self._log_file.flush()
                            self._log_last_flush = t0
            except Exception:
                # Never crash the process due to logging I/O
                pass

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    # ------------------------
    # Worker loops
    # ------------------------

    def _loop_vl53(self) -> None:
        period = 1.0 / max(SENSOR_HZ_VL53, 1.0)
        while not self.stop_event.is_set():
            t0 = time.time()

            dist = None

            if self.tof is not None:
                try:
                    if self.tof_kind == "l0x":
                        # VL53L0X: `range` is already in mm
                        d_mm = int(self.tof.range)
                        dist = d_mm
                        self._last_distance_mm = dist

                    elif self.tof_kind == "l1x":
                        # VL53L1X: distance is reported in cm
                        if getattr(self.tof, "data_ready", True):
                            d_cm = self.tof.distance
                            try:
                                self.tof.clear_interrupt()
                            except Exception:
                                pass
                            if d_cm is not None:
                                dist = int(d_cm) * 10
                                self._last_distance_mm = dist
                            else:
                                dist = None
                        else:
                            dist = self._last_distance_mm

                    else:
                        dist = self._last_distance_mm
                except Exception:
                    dist = self._last_distance_mm

            with self.lock:
                self.cache.distance_mm = dist
                self.cache.ts = time.time()

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _loop_mpu6050(self) -> None:
        """Read MPU6050 at a higher rate and cache the latest values."""
        period = 1.0 / max(SENSOR_HZ_MPU, 1.0)
        while not self.stop_event.is_set():
            t0 = time.time()

            accel = gyro = None
            temp_c = None

            if self.mpu is not None:
                try:
                    accel_t, gyro_t, t_c = self.mpu.read()  # type: ignore[attr-defined]
                    ax, ay, az = accel_t
                    gx, gy, gz = gyro_t
                    accel = (float(ax), float(ay), float(az))
                    gyro = (float(gx), float(gy), float(gz))
                    temp_c = float(t_c)
                except Exception:
                    accel = gyro = None
                    temp_c = None

            with self.lock:
                self.cache.imu_accel_m_s2 = accel
                self.cache.imu_gyro_rad_s = gyro
                self.cache.imu_temp_c = temp_c
                # Do not overwrite ts too aggressively if IMU is absent
                if self.mpu is not None:
                    self.cache.ts = time.time()

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _loop_ina219(self) -> None:
        period = 1.0 / max(SENSOR_HZ_INA, 1.0)
        while not self.stop_event.is_set():
            t0 = time.time()

            bus_v_raw = cur_mA = p_mW = None
            bus_v_ema = None
            batt_pct = None

            if self.ina is not None:
                try:
                    bus_v_raw = float(self.ina.bus_voltage)
                    cur_mA = float(self.ina.current)
                    p_mW = float(self.ina.power)

                    if self._bus_v_ema is None:
                        self._bus_v_ema = bus_v_raw
                    else:
                        a = float(BAT_VOLT_EWA_ALPHA)
                        a = max(0.0, min(1.0, a))
                        self._bus_v_ema = a * bus_v_raw + (1.0 - a) * self._bus_v_ema

                    bus_v_ema = self._bus_v_ema
                    batt_pct = estimate_battery_percent(bus_v_ema)
                except Exception:
                    bus_v_raw = cur_mA = p_mW = None
                    bus_v_ema = None
                    batt_pct = None
            else:
                bus_v_raw = cur_mA = p_mW = None
                bus_v_ema = None
                batt_pct = None

            with self.lock:
                # Keep bus_voltage_v as the filtered voltage for backward compatibility
                self.cache.bus_voltage_v = bus_v_ema
                self.cache.bus_voltage_v_raw = bus_v_raw
                self.cache.bus_voltage_v_filt = bus_v_ema
                self.cache.current_mA = cur_mA
                self.cache.power_mW = p_mW
                self.cache.battery_percent = batt_pct
                self.cache.ts = time.time()

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _loop_status(self) -> None:
        # Network + battery are slow-changing; update at OLED rate
        period = 1.0 / max(OLED_HZ, 1.0)
        while not self.stop_event.is_set():
            t0 = time.time()

            mode, ssid, ip = detect_mode_and_ip()

            with self.lock:
                self.cache.mode = mode
                self.cache.ssid = ssid
                self.cache.ip = ip
                self.cache.ts = time.time()

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _loop_oled(self) -> None:
        period = 1.0 / max(OLED_HZ, 1.0)
        while not self.stop_event.is_set():
            t0 = time.time()

            with self.lock:
                mode = self.cache.mode
                ssid = self.cache.ssid
                ip = self.cache.ip
                batt = self.cache.battery_percent

            # Build 3 lines for 128x32 (default font ~8px)
            # Line1: MODE + battery
            batt_str = "--" if batt is None else f"{batt:3d}%"
            line1 = f"{mode:<7} BAT:{batt_str}"

            # Line2: SSID (trim)
            ssid_show = ssid if ssid else "(no ssid)"
            if len(ssid_show) > 16:
                ssid_show = ssid_show[:16]
            line2 = f"SSID:{ssid_show}"

            # Line3: IP only (distance removed)
            ip_show = ip if ip else "0.0.0.0"
            line3 = f"IP:{ip_show}"
            if len(line3) > 21:
                line3 = line3[:21]

            try:
                img = Image.new("1", (OLED_WIDTH, OLED_HEIGHT))
                draw = ImageDraw.Draw(img)
                draw.text((0, 0), line1, font=self.font, fill=255)
                draw.text((0, 11), line2, font=self.font, fill=255)
                draw.text((0, 22), line3, font=self.font, fill=255)
                self.oled.image(img)
                self.oled.show()
            except Exception:
                # Do not crash on OLED write errors
                pass

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _loop_uds_server(self) -> None:
        # Non-blocking with timeout so we can exit quickly
        self.sock.settimeout(0.5)

        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception:
                continue

            # Default response
            with self.lock:
                payload = self.cache.to_ipc_dict()

            # Parse request (optional)
            try:
                req = json.loads(data.decode("utf-8", errors="replace")) if data else {}
                cmd = req.get("cmd", "get")
                if cmd != "get":
                    payload["error"] = f"unknown cmd: {cmd}"
            except Exception:
                payload["error"] = "bad request"

            try:
                resp = json.dumps(payload, separators=(",", ":")).encode("utf-8")
                self.sock.sendto(resp, addr)
            except Exception:
                pass

    def run(self) -> None:
        threads = [
            threading.Thread(target=self._loop_vl53, name="vl53", daemon=True),
            threading.Thread(target=self._loop_mpu6050, name="mpu6050", daemon=True),
            threading.Thread(target=self._loop_ina219, name="ina219", daemon=True),
            threading.Thread(target=self._loop_status, name="status", daemon=True),
            threading.Thread(target=self._loop_oled, name="oled", daemon=True),
            threading.Thread(target=self._loop_csv_logger, name="csvlog", daemon=True),
            threading.Thread(target=self._loop_uds_server, name="uds", daemon=True),
        ]

        for th in threads:
            th.start()

        # Main wait loop
        while not self.stop_event.is_set():
            time.sleep(0.2)


# ----------------------------
# Entrypoint
# ----------------------------


def main() -> None:
    mgr = I2CManager()

    def _handle_signal(_signum: int, _frame: Any) -> None:
        mgr.stop_event.set()

    signal.signal(signal.SIGINT, _handle_signal)
    signal.signal(signal.SIGTERM, _handle_signal)

    try:
        mgr.run()
    finally:
        mgr.close()


if __name__ == "__main__":
    main()
