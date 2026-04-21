#!/usr/bin/env python3
"""I2C Manager (single owner of /dev/i2c-*).

- Reads:
  - INA219 (bus voltage / current / power)
  - VL53L1X / VL53L0X (distance) [currently disabled in smbus2 migration]
  - MPU6xxx (MPU6050/MPU6500-class) [currently disabled in smbus2 migration]
- Displays on OLED:
  - Wi-Fi mode (STA/AP), SSID, IP
  - Battery percent (INA219 voltage-based)
- IPC:
  - Unix Domain Socket (datagram) server: /run/autoformbot/afb_i2c.sock
  - Request: JSON bytes (e.g. {"cmd":"get"})
  - Response: JSON dict with latest cached readings

Notes:
- Keep this as the ONLY process that touches I2C devices.
- Other processes must read sensor values via IPC (UDS) from this manager.
- RDK X5 is not supported by Adafruit Blinka `board`, so this version uses smbus2 directly.
- Confirmed external I2C bus in this project: /dev/i2c-5
"""

from __future__ import annotations

import csv
import getpass
import json
import os
import signal
import socket
import subprocess
import threading
import time
from dataclasses import dataclass
from typing import Any, Dict, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont
from smbus2 import SMBus, i2c_msg


# ----------------------------
# Configuration
# ----------------------------

I2C_BUS_NUM = 5
UDS_PATH = "/run/autoformbot/afb_i2c.sock"

OLED_WIDTH = 128
OLED_HEIGHT = 32
OLED_ADDR = 0x3C
INA219_ADDR = 0x40

SENSOR_HZ_VL53 = 10.0
SENSOR_HZ_INA = 10.0
SENSOR_HZ_MPU = 100.0
OLED_HZ = 2.0

LOG_HZ = 10.0
LOG_DIR_NAME = "afb_home"
LOG_BASE_NAME = "i2c_sensor_log"
LOG_EXT = ".csv"
LOG_FLUSH_SEC = 1.0

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
BAT_VOLT_EWA_ALPHA = 0.25


# ----------------------------
# Minimal device helpers (smbus2)
# ----------------------------

class SSD1306I2C32:
    """Minimal SSD1306 128x32 I2C driver using smbus2."""

    def __init__(
        self,
        bus: SMBus,
        address: int = OLED_ADDR,
        width: int = OLED_WIDTH,
        height: int = OLED_HEIGHT,
    ) -> None:
        self.bus = bus
        self.address = address
        self.width = width
        self.height = height
        self.pages = height // 8
        self.buffer = bytearray(width * self.pages)
        self._init_display()

    def _write_cmd(self, cmd: int) -> None:
        self.bus.write_byte_data(self.address, 0x00, cmd & 0xFF)

    def _write_data(self, data: bytes) -> None:
        chunk_size = 16
        for i in range(0, len(data), chunk_size):
            chunk = data[i:i + chunk_size]
            msg = i2c_msg.write(self.address, bytes([0x40]) + bytes(chunk))
            self.bus.i2c_rdwr(msg)

    def _init_display(self) -> None:
        init_seq = [
            0xAE,
            0xD5, 0x80,
            0xA8, 0x1F,
            0xD3, 0x00,
            0x40,
            0x8D, 0x14,
            0x20, 0x00,
            0xA1,
            0xC8,
            0xDA, 0x02,
            0x81, 0x8F,
            0xD9, 0xF1,
            0xDB, 0x40,
            0xA4,
            0xA6,
            0x2E,
            0xAF,
        ]
        for cmd in init_seq:
            self._write_cmd(cmd)
        self.fill(0)
        self.show()

    def fill(self, color: int) -> None:
        value = 0xFF if color else 0x00
        for i in range(len(self.buffer)):
            self.buffer[i] = value

    def image(self, img: Image.Image) -> None:
        img = img.convert("1")
        if img.size != (self.width, self.height):
            raise ValueError(f"Expected image size {(self.width, self.height)}, got {img.size}")

        pixels = img.load()
        buf = bytearray(self.width * self.pages)
        for y in range(self.height):
            for x in range(self.width):
                if pixels[x, y]:
                    buf[x + (y // 8) * self.width] |= 1 << (y % 8)
        self.buffer = buf

    def show(self) -> None:
        for page in range(self.pages):
            self._write_cmd(0xB0 + page)
            self._write_cmd(0x00)
            self._write_cmd(0x10)
            start = page * self.width
            end = start + self.width
            self._write_data(self.buffer[start:end])


class INA219Compat:
    """Minimal INA219 reader using smbus2."""

    REG_CONFIG = 0x00
    REG_BUS_VOLTAGE = 0x02
    REG_POWER = 0x03
    REG_CURRENT = 0x04
    REG_CALIBRATION = 0x05

    def __init__(self, bus: SMBus, address: int = INA219_ADDR) -> None:
        self.bus = bus
        self.address = address
        self.current_lsb_mA = 0.1
        self.power_lsb_mW = 2.0
        self._configure()

    @staticmethod
    def _to_signed(v: int) -> int:
        return v - 65536 if v & 0x8000 else v

    def _read_u16_be(self, reg: int) -> int:
        raw = self.bus.read_word_data(self.address, reg)
        return ((raw & 0xFF) << 8) | ((raw >> 8) & 0xFF)

    def _write_u16_be(self, reg: int, value: int) -> None:
        swapped = ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
        self.bus.write_word_data(self.address, reg, swapped)

    def _configure(self) -> None:
        self._write_u16_be(self.REG_CALIBRATION, 4096)
        self._write_u16_be(self.REG_CONFIG, 0x399F)
        time.sleep(0.01)

    @property
    def bus_voltage(self) -> float:
        raw = self._read_u16_be(self.REG_BUS_VOLTAGE)
        return ((raw >> 3) * 0.004)

    @property
    def current(self) -> float:
        raw = self._to_signed(self._read_u16_be(self.REG_CURRENT))
        return raw * self.current_lsb_mA

    @property
    def power(self) -> float:
        raw = self._read_u16_be(self.REG_POWER)
        return raw * self.power_lsb_mW


# ----------------------------
# Helpers
# ----------------------------

def _run_cmd(cmd: list[str], timeout_s: float = 1.0) -> Tuple[int, str]:
    try:
        out = subprocess.check_output(cmd, stderr=subprocess.DEVNULL, timeout=timeout_s)
        return 0, out.decode("utf-8", errors="replace").strip()
    except subprocess.CalledProcessError as e:
        return int(e.returncode), ""
    except Exception:
        return 1, ""


def get_ssid() -> str:
    rc, out = _run_cmd(["iwgetid", "-r"], timeout_s=0.8)
    if rc == 0 and out:
        return out

    rc, out = _run_cmd(["nmcli", "-t", "-f", "ACTIVE,SSID", "dev", "wifi"], timeout_s=1.0)
    if rc == 0 and out:
        for line in out.splitlines():
            if line.startswith("yes:"):
                return line.split(":", 1)[1].strip()

    return ""


def get_ap_ssid() -> str:
    rc, out = _run_cmd(["hostapd_cli", "-i", "wlan0", "status"], timeout_s=0.8)
    if rc == 0 and out:
        for line in out.splitlines():
            if line.startswith("ssid="):
                ssid = line.split("=", 1)[1].strip()
                if ssid:
                    return ssid

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

    rc, out = _run_cmd(["nmcli", "-t", "-f", "NAME,TYPE", "con", "show", "--active"], timeout_s=1.0)
    if rc == 0 and out:
        for line in out.splitlines():
            parts = line.split(":", 1)
            if len(parts) == 2 and parts[1].strip() == "wifi":
                name = parts[0].strip()
                if name:
                    return name

    return ""


def get_ip_addr(ifname: str) -> str:
    rc, out = _run_cmd(["ip", "-4", "addr", "show", ifname], timeout_s=0.8)
    if rc != 0 or not out:
        return ""

    for line in out.splitlines():
        line = line.strip()
        if line.startswith("inet "):
            ip_with_mask = line.split()[1]
            return ip_with_mask.split("/")[0]
    return ""


def detect_mode_and_ip() -> Tuple[str, str, str]:
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
    if bus_voltage_v is None:
        return None

    v = float(bus_voltage_v)
    lut = BAT_LUT_2S

    if v <= lut[0][0]:
        return int(lut[0][1])
    if v >= lut[-1][0]:
        return int(lut[-1][1])

    for (v0, p0), (v1, p1) in zip(lut[:-1], lut[1:]):
        if v0 <= v <= v1:
            if v1 == v0:
                return int(p1)
            t = (v - v0) / (v1 - v0)
            pct = p0 + t * (p1 - p0)
            return int(round(max(0.0, min(100.0, pct))))

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

        self.bus = SMBus(I2C_BUS_NUM)

        self.ina: Optional[INA219Compat] = None
        try:
            self.ina = INA219Compat(self.bus)
        except Exception:
            self.ina = None

        # disabled during smbus2 migration
        self.tof = None
        self.tof_kind: str = ""
        self.mpu = None

        self.oled = SSD1306I2C32(self.bus)
        self.oled.fill(0)
        self.oled.show()
        self.font = ImageFont.load_default()

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)

        uds_dir = os.path.dirname(UDS_PATH)
        os.makedirs(uds_dir, exist_ok=True)

        if not os.access(uds_dir, os.W_OK | os.X_OK):
            raise PermissionError(f"UDS directory is not writable: {uds_dir}")

        try:
            if os.path.exists(UDS_PATH):
                os.unlink(UDS_PATH)
        except Exception:
            pass

        self.sock.bind(UDS_PATH)

        try:
            os.chmod(UDS_PATH, 0o666)
        except Exception:
            pass

        self._bus_v_ema: Optional[float] = None
        self._last_distance_mm: Optional[int] = None

        self._log_file = None
        self._log_writer = None
        self._log_lock = threading.Lock()
        self._log_buf: list[list[Any]] = []
        self._log_last_flush = time.time()
        self._log_date: Optional[str] = None

        log_user = os.environ.get("AFB_USER") or os.environ.get("SUDO_USER") or os.environ.get("USER") or getpass.getuser()
        home_dir = os.path.expanduser(f"~{log_user}")
        if not home_dir or home_dir == "~":
            home_dir = os.path.expanduser("~")

        self._log_dir = os.path.join(home_dir, LOG_DIR_NAME)
        os.makedirs(self._log_dir, exist_ok=True)
        self._open_log_for_time(time.time())

    def close(self) -> None:
        try:
            self.oled.fill(0)
            self.oled.show()
        except Exception:
            pass

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

        try:
            self.sock.close()
        except Exception:
            pass

        try:
            if os.path.exists(UDS_PATH):
                os.unlink(UDS_PATH)
        except Exception:
            pass

        try:
            self.bus.close()
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
        date_str = time.strftime("%Y-%m-%d", time.localtime(t_unix))
        if self._log_date == date_str and self._log_file is not None and self._log_writer is not None:
            return

        try:
            if self._log_file is not None:
                self._log_file.flush()
                self._log_file.close()
        except Exception:
            pass

        self._log_file = None
        self._log_writer = None

        dated_name = f"{LOG_BASE_NAME}_{date_str}{LOG_EXT}"
        self._log_path = os.path.join(self._log_dir, dated_name)

        is_new = not os.path.exists(self._log_path) or os.path.getsize(self._log_path) == 0
        self._log_file = open(self._log_path, "a", encoding="utf-8", newline="")
        self._log_writer = csv.writer(self._log_file)
        if is_new:
            self._log_writer.writerow(self._log_header())
            self._log_file.flush()

        self._log_date = date_str

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
            pass

    def _loop_csv_logger(self) -> None:
        period = 1.0 / max(LOG_HZ, 1.0)
        while not self.stop_event.is_set():
            t0 = time.time()

            with self.lock:
                dist = self.cache.distance_mm
                accel = self.cache.imu_accel_m_s2
                gyro = self.cache.imu_gyro_rad_s
                temp_c = self.cache.imu_temp_c

            iso = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime(t0)) + f".{int((t0 % 1.0) * 1000):03d}"

            try:
                self._open_log_for_time(t0)
            except Exception:
                pass

            dist_out: Any = "NC" if self.tof is None else ("NL" if dist is None else int(dist))

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
                pass

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _loop_vl53(self) -> None:
        period = 1.0 / max(SENSOR_HZ_VL53, 1.0)
        while not self.stop_event.is_set():
            with self.lock:
                self.cache.distance_mm = self._last_distance_mm
                self.cache.ts = time.time()
            time.sleep(period)

    def _loop_mpu6050(self) -> None:
        period = 1.0 / max(SENSOR_HZ_MPU, 1.0)
        while not self.stop_event.is_set():
            with self.lock:
                self.cache.imu_accel_m_s2 = None
                self.cache.imu_gyro_rad_s = None
                self.cache.imu_temp_c = None
            time.sleep(period)

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
                        a = max(0.0, min(1.0, float(BAT_VOLT_EWA_ALPHA)))
                        self._bus_v_ema = a * bus_v_raw + (1.0 - a) * self._bus_v_ema

                    bus_v_ema = self._bus_v_ema
                    batt_pct = estimate_battery_percent(bus_v_ema)
                except Exception:
                    bus_v_raw = cur_mA = p_mW = None
                    bus_v_ema = None
                    batt_pct = None

            with self.lock:
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

            batt_str = "--" if batt is None else f"{batt:3d}%"
            line1 = f"{mode:<7} BAT:{batt_str}"

            ssid_show = ssid if ssid else "(no ssid)"
            if len(ssid_show) > 16:
                ssid_show = ssid_show[:16]
            line2 = f"SSID:{ssid_show}"

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
                pass

            dt = time.time() - t0
            time.sleep(max(0.0, period - dt))

    def _loop_uds_server(self) -> None:
        self.sock.settimeout(0.5)

        while not self.stop_event.is_set():
            try:
                data, addr = self.sock.recvfrom(4096)
            except socket.timeout:
                continue
            except Exception:
                continue

            with self.lock:
                payload = self.cache.to_ipc_dict()

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