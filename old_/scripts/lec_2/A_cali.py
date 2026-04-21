

from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any, Callable, Dict

import afb2


CALIB_PATH = Path(__file__).with_name("steering_center.json")
DEFAULT_CENTER = 90.0
DEFAULT_STEP = 1.0
DEFAULT_MIN = 0.0
DEFAULT_MAX = 180.0


class SteeringCalib:
    def __init__(
        self,
        center_deg: float = DEFAULT_CENTER,
        min_deg: float = DEFAULT_MIN,
        max_deg: float = DEFAULT_MAX,
    ) -> None:
        self.center_deg = float(center_deg)
        self.min_deg = float(min_deg)
        self.max_deg = float(max_deg)

    def clamp(self, angle: float) -> float:
        return max(self.min_deg, min(self.max_deg, float(angle)))

    def to_dict(self) -> Dict[str, float]:
        return {
            "center_deg": self.center_deg,
            "min_deg": self.min_deg,
            "max_deg": self.max_deg,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "SteeringCalib":
        return cls(
            center_deg=float(data.get("center_deg", DEFAULT_CENTER)),
            min_deg=float(data.get("min_deg", DEFAULT_MIN)),
            max_deg=float(data.get("max_deg", DEFAULT_MAX)),
        )


def load_calibration(path: Path) -> SteeringCalib:
    if not path.exists():
        return SteeringCalib()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return SteeringCalib()

    return SteeringCalib.from_dict(data)


def save_calibration(calib: SteeringCalib, path: Path) -> None:
    path.write_text(
        json.dumps(calib.to_dict(), indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def resolve_steering_sender() -> Callable[[float], None]:
    """Resolve the steering output function from the afb2 package.

    Update this function if your steering API name is different.
    """
    if hasattr(afb2, "car") and hasattr(afb2.car, "steering"):
        return afb2.car.steering

    if hasattr(afb2, "car") and hasattr(afb2.car, "servo"):
        return afb2.car.servo

    raise AttributeError(
        "Steering output function was not found. "
        "Expected afb2.car.steering(angle) or afb2.car.servo(angle)."
    )


def send_angle(angle: float, calib: SteeringCalib, sender: Callable[[float], None]) -> float:
    out = calib.clamp(angle)

    # Convert to int for SPI protocol (bitwise operations require int)
    out_int = int(round(out))

    sender(out_int)
    return out_int


def print_help() -> None:
    print("Commands:")
    print("  + / -            move current angle by step")
    print("  ++ / --          move current angle by 5 * step")
    print("  step <deg>       set step size")
    print("  set <deg>        send exact steering angle")
    print("  center           send saved center angle")
    print("  use              store current angle as center")
    print("  lim <lo> <hi>    set min/max angle")
    print("  p                print current state")
    print("  s                save")
    print("  q                save and quit")


def main() -> None:
    afb2.gpio.reset()
    time.sleep(8)
    calib = load_calibration(CALIB_PATH)
    sender = resolve_steering_sender()

    current = calib.center_deg
    step = DEFAULT_STEP

    print("=== Steering Center Calibration Tool ===")
    print(f"[loaded] {CALIB_PATH}")
    print_help()

    sent = send_angle(current, calib, sender)
    print(f"[sent] {sent:.2f} deg")

    while True:
        try:
            cmd = input("steer> ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\n[exit]")
            break

        if not cmd:
            continue

        if cmd in {"q", "quit", "exit"}:
            break

        if cmd in {"+", "plus"}:
            current += step
            sent = send_angle(current, calib, sender)
            current = sent
            print(f"[sent] {sent:.2f} deg")
            continue

        if cmd in {"-", "minus"}:
            current -= step
            sent = send_angle(current, calib, sender)
            current = sent
            print(f"[sent] {sent:.2f} deg")
            continue

        if cmd == "++":
            current += step * 5.0
            sent = send_angle(current, calib, sender)
            current = sent
            print(f"[sent] {sent:.2f} deg")
            continue

        if cmd == "--":
            current -= step * 5.0
            sent = send_angle(current, calib, sender)
            current = sent
            print(f"[sent] {sent:.2f} deg")
            continue

        if cmd in {"center", "c"}:
            current = calib.center_deg
            sent = send_angle(current, calib, sender)
            current = sent
            print(f"[center] {sent:.2f} deg")
            continue

        if cmd in {"use", "u"}:
            calib.center_deg = current
            print(f"[saved center in memory] {calib.center_deg:.2f} deg")
            continue

        if cmd in {"p", "print"}:
            print(
                f"current={current:.2f}, center={calib.center_deg:.2f}, "
                f"step={step:.2f}, lim=[{calib.min_deg:.2f}, {calib.max_deg:.2f}]"
            )
            continue

        if cmd in {"s", "save"}:
            save_calibration(calib, CALIB_PATH)
            print(f"[saved] {CALIB_PATH}")
            continue

        parts = cmd.split()

        if parts[0] == "step" and len(parts) == 2:
            try:
                value = float(parts[1])
                if value <= 0:
                    raise ValueError
                step = value
                print(f"[step] {step:.2f}")
            except ValueError:
                print("usage: step <positive number>")
            continue

        if parts[0] == "set" and len(parts) == 2:
            try:
                value = float(parts[1])
                sent = send_angle(value, calib, sender)
                current = sent
                print(f"[sent] {sent:.2f} deg")
            except ValueError:
                print("usage: set <deg>")
            continue

        if parts[0] == "lim" and len(parts) == 3:
            try:
                lo = float(parts[1])
                hi = float(parts[2])
                if hi < lo:
                    lo, hi = hi, lo
                calib.min_deg = lo
                calib.max_deg = hi
                current = calib.clamp(current)
                sent = send_angle(current, calib, sender)
                current = sent
                print(f"[lim] [{calib.min_deg:.2f}, {calib.max_deg:.2f}]")
            except ValueError:
                print("usage: lim <lo> <hi>")
            continue

        print("unknown command")
        print_help()

    save_calibration(calib, CALIB_PATH)
    print(f"[auto-saved] {CALIB_PATH}")


if __name__ == "__main__":
    main()