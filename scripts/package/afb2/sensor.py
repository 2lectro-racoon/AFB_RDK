

"""afb.sensor

Real-time I2C sensor access via i2c_manager's Unix Domain Socket (UDS).

The i2c_manager (systemd service) is the single owner of /dev/i2c-* and publishes
latest cached readings over a Unix domain *datagram* socket.

Public API:
  - distance() -> Optional[int]
      Returns distance in millimeters as an int.
  - mpu() -> Optional[list[float]]
      Returns 6-axis IMU values as [ax, ay, az, gx, gy, gz] (floats).

Notes:
  - Returns None if the sensor is not connected, no reading is available yet,
    or UDS IPC fails.
  - This module has no dependency on I2C libraries.

"""

from __future__ import annotations

import json
import os
import socket
import time
from typing import Any, Dict, Optional


# Default UDS path used by i2c_manager.py
DEFAULT_UDS_PATH = "/run/autoformbot/afb_i2c.sock"
DEFAULT_TIMEOUT_SEC = 0.25


def _uds_rpc(
    payload: Dict[str, Any],
    uds_path: str = DEFAULT_UDS_PATH,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> Optional[Dict[str, Any]]:
    """Send a JSON payload to i2c_manager via UDS (datagram) and return JSON response."""

    if not os.path.exists(uds_path):
        return None

    try:
        data = json.dumps(payload, separators=(",", ":")).encode("utf-8")
    except Exception:
        return None

    # Datagram sockets require the client to bind to a local path so the server
    # can reply to that address.
    pid = os.getpid()
    nonce = int(time.time() * 1_000_000)
    client_path = f"/tmp/afb_i2c_cli_{pid}_{nonce}.sock"

    s = socket.socket(socket.AF_UNIX, socket.SOCK_DGRAM)
    try:
        s.settimeout(float(timeout_sec))

        # Best-effort cleanup for a stale file
        try:
            if os.path.exists(client_path):
                os.unlink(client_path)
        except Exception:
            pass

        s.bind(client_path)
        s.sendto(data, uds_path)

        resp, _addr = s.recvfrom(4096)
        raw = resp.decode("utf-8", errors="ignore").strip()
        if not raw:
            return None

        out = json.loads(raw)
        if isinstance(out, dict):
            return out
        return None
    except Exception:
        return None
    finally:
        try:
            s.close()
        except Exception:
            pass
        try:
            if os.path.exists(client_path):
                os.unlink(client_path)
        except Exception:
            pass


def _get_cache(
    uds_path: str = DEFAULT_UDS_PATH,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> Optional[Dict[str, Any]]:
    """Fetch latest cached sensor values from i2c_manager."""

    return _uds_rpc({"cmd": "get"}, uds_path=uds_path, timeout_sec=timeout_sec)

def _to_float_or_nl(x: Any) -> Any:
        if x is None:
            return "NL"
        try:
            if isinstance(x, bool):
                return "NL"
            return float(x)
        except Exception:
            return "NL"


def distance(
    uds_path: str = DEFAULT_UDS_PATH,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> Optional[int]:
    """Return distance in millimeters as int.

    Returns None if unavailable.
    """

    d = _get_cache(uds_path=uds_path, timeout_sec=timeout_sec)
    if not d:
        return None

    v = d.get("distance_mm")
    if v is None:
        return None

    # i2c_manager may store distance as float (e.g., cm->mm conversion) or int.
    if isinstance(v, bool):
        return None
    if isinstance(v, int):
        return v
    if isinstance(v, float):
        return int(round(v))

    # Unknown type
    return None


def mpu(
    uds_path: str = DEFAULT_UDS_PATH,
    timeout_sec: float = DEFAULT_TIMEOUT_SEC,
) -> Optional[list[float]]:
    """Return 6-axis IMU values as [ax, ay, az, gx, gy, gz].

    Returns None if unavailable.
    """

    d = _get_cache(uds_path=uds_path, timeout_sec=timeout_sec)
    if not d:
        return None

    imu = d.get("imu")
    if not isinstance(imu, dict):
        return None

    accel = imu.get("accel_m_s2")
    gyro = imu.get("gyro_rad_s")

    # if not (isinstance(accel, (list, tuple)) and len(accel) == 3):
    #     return None
    # if not (isinstance(gyro, (list, tuple)) and len(gyro) == 3):
    #     return None

    # try:
    #     ax, ay, az = float(accel[0]), float(accel[1]), float(accel[2])
    #     gx, gy, gz = float(gyro[0]), float(gyro[1]), float(gyro[2])
    #     return [ax, ay, az, gx, gy, gz]
    # except Exception:
    #     return None
    
        # Use "NL" marker for missing values (per-axis).

    # accel/gyro may be missing or malformed; fill with "NL" in that case.
    if not (isinstance(accel, (list, tuple)) and len(accel) == 3):
        ax = ay = az = "NL"
    else:
        ax = _to_float_or_nl(accel[0])
        ay = _to_float_or_nl(accel[1])
        az = _to_float_or_nl(accel[2])

    if not (isinstance(gyro, (list, tuple)) and len(gyro) == 3):
        gx = gy = gz = "NL"
    else:
        gx = _to_float_or_nl(gyro[0])
        gy = _to_float_or_nl(gyro[1])
        gz = _to_float_or_nl(gyro[2])

    return [ax, ay, az, gx, gy, gz]