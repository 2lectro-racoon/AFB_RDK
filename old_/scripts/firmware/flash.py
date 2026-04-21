#!/usr/bin/env python3
import subprocess
import sys
from pathlib import Path

# ========= 사용자 설정 =========
OPENOCD = "openocd"

# 스크립트 위치 기준 경로
SCRIPT_DIR = Path(__file__).resolve().parent                 # .../AutoFormBotCode/scripts/firmware
SCRIPTS_DIR = SCRIPT_DIR.parent                              # .../AutoFormBotCode/scripts
REPO_ROOT = SCRIPTS_DIR.parent                               # .../AutoFormBotCode
DEFAULT_FW_DIR = REPO_ROOT / "firmware"                      # .../AutoFormBotCode/firmware

# Pi4/Pi5 전용 interface cfg (repo에 넣어두는 파일)
RPI4_IF_CFG = SCRIPT_DIR / "rpi4_swd.cfg"
RPI5_IF_CFG = SCRIPT_DIR / "rpi5_swd.cfg"

# fallback (OpenOCD 내장 cfg)
DEFAULT_IF_CFG_PI4 = "interface/raspberrypi-swd.cfg"         # Pi4/legacy용
DEFAULT_IF_CFG_PI5 = "interface/raspberrypi5-gpiod.cfg"      # Pi5용

TARGET_CFG = "target/stm32f1x.cfg"
FLASH_ADDR = "0x08000000"
# ===============================


def run(cmd: list[str]) -> None:
    print("\n[RUN]")
    print(" ".join(cmd))
    print("-" * 60)

    p = subprocess.run(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    print(p.stdout)

    if p.returncode != 0:
        print("[ERROR] OpenOCD failed")
        sys.exit(1)


def is_pi5() -> bool:
    """Raspberry Pi 5 여부 판별 (가장 확실한 방법: device-tree model)."""
    try:
        model = Path("/proc/device-tree/model").read_text(errors="ignore")
        return "Raspberry Pi 5" in model
    except Exception:
        return False


def resolve_firmware_path(arg: str | None) -> Path:
    """펌웨어 경로 해석.

    - 인자를 주면: 절대경로/상대경로 모두 허용
    - 인자를 안 주면: ~/AutoFormBotCode/firmware/firmware.bin 기본
    - 인자가 파일명만이면: DEFAULT_FW_DIR 아래에서 찾음
    """
    if not arg:
        return DEFAULT_FW_DIR / "firmware.bin"

    p = Path(arg).expanduser()

    # 절대경로/상대경로로 실제 파일이 있으면 그대로
    if p.exists():
        return p

    # 파일명만 준 경우: 기본 firmware 폴더에서 탐색
    return DEFAULT_FW_DIR / p.name


def pick_interface_cfg() -> tuple[str, str]:
    """Pi4/Pi5 자동 감지 후 OpenOCD interface cfg 선택.

    우선순위:
      - Pi5: scripts/firmware/rpi5_swd.cfg (있으면)
             -> 없으면 interface/raspberrypi5-gpiod.cfg
      - Pi4: scripts/firmware/rpi4_swd.cfg (있으면)
             -> 없으면 interface/raspberrypi-swd.cfg

    반환: (if_cfg_path, detected_label)
    """
    if is_pi5():
        if RPI5_IF_CFG.exists():
            return str(RPI5_IF_CFG), "Raspberry Pi 5"
        return DEFAULT_IF_CFG_PI5, "Raspberry Pi 5"

    # Pi4/legacy
    if RPI4_IF_CFG.exists():
        return str(RPI4_IF_CFG), "Raspberry Pi 4/legacy"
    return DEFAULT_IF_CFG_PI4, "Raspberry Pi 4/legacy"


def main() -> None:
    # 사용법: 인자 생략 시 기본 펌웨어 경로 사용
    if len(sys.argv) > 2:
        print("Usage:")
        print("  python3 flash.py [firmware.bin]")
        print(f"  (default: {DEFAULT_FW_DIR}/firmware.bin)")
        sys.exit(1)

    fw_arg = sys.argv[1] if len(sys.argv) == 2 else None
    bin_path = resolve_firmware_path(fw_arg)

    if not bin_path.exists():
        print(f"[ERROR] File not found: {bin_path}")
        print("[HINT] Put firmware at:")
        print(f"       {DEFAULT_FW_DIR}/firmware.bin")
        sys.exit(1)

    if_cfg, pi_label = pick_interface_cfg()

    print("[INFO] Script dir :", SCRIPT_DIR)
    print("[INFO] Repo root  :", REPO_ROOT)
    print("[INFO] Detected   :", pi_label)
    print("[INFO] Using interface config:", if_cfg)
    print("[INFO] Firmware:", bin_path)
    print("[INFO] Note: This script uses 'sysresetreq + reset halt' (core reset) to halt the CPU, avoiding NRST(mmap) conflicts.")

    # 업로드 로직(유지): flash write + verify
    cmd = [
        OPENOCD,
        "-f", if_cfg,
        "-c", "transport select swd",
        "-f", TARGET_CFG,

        # Init first
        "-c", "init",

        # 방법 2) NRST 물리라인을 건드리지 않고(CORE reset), halt 상태 확보
        "-c", "cortex_m reset_config sysresetreq",
        "-c", "reset halt",

        # Program + verify
        "-c", f"flash write_image erase {bin_path} {FLASH_ADDR}",
        "-c", f"verify_image {bin_path} {FLASH_ADDR}",

        # (선택) 바로 실행시키고 싶으면 아래 한 줄을 주석 해제
        # "-c", "reset run",

        "-c", "exit",
    ]

    run(cmd)

    print("[OK] Flash completed successfully")
    print("[INFO] If your board needs a reset to start the new firmware, toggle NRST via your GPIO reset script.")


if __name__ == "__main__":
    main()