import spidev
import time

# ===========================
# SPI 설정
# ===========================
spi = spidev.SpiDev()
spi.open(0, 0)  # (bus=0, device=0 → CE0 사용)
spi.max_speed_hz = 500000
spi.mode = 0    # SPI_MODE0

print("=== Raspberry Pi (HW-CS) STM32 SPI TEST TOOL ===")

# ===========================
# 패킷 생성 + 전송 함수
# ===========================
def send_packet(cmd, data_bytes):
    length = len(data_bytes)
    packet = [0xAA, cmd, length, 0, 0, 0]

    checksum = cmd ^ length

    # DATA0
    if length > 0:
        packet[3] = data_bytes[0]
        checksum ^= data_bytes[0]

    # DATA1
    if length > 1:
        packet[4] = data_bytes[1]
        checksum ^= data_bytes[1]

    packet[5] = checksum

    print("TX:", " ".join(f"{b:02X}" for b in packet))

    # 하드웨어 CS를 사용하므로 수동 제어 필요 없음
    rx = spi.xfer2(packet)

    print("RX:", " ".join(f"{b:02X}" for b in rx))
    return rx

# ===========================
# HEX 문자열 → BYTE
# ===========================
def hex_to_byte(s):
    return int(s.strip(), 16)

def set_leg_angles(leg, a1, a2, a3):
    """
    leg: 0,1,2...
    a1,a2,a3: 0~180
    """
    base_ch = leg * 3
    angles = [a1, a2, a3]

    for i, ang in enumerate(angles):
        ch = base_ch + i
        send_packet(0x02, [ch & 0xFF, ang & 0xFF])
        time.sleep(0.005)  # 너무 빠르면 STM32쪽 처리 못할 수도 있어서 약간 텀

def parse_leg_line(line: str):
    parts = line.strip().split()
    if len(parts) != 4:
        raise ValueError("format: <leg> <a1> <a2> <a3> (ex: 0 135 120 180)")

    leg = int(parts[0])
    a1 = int(parts[1])
    a2 = int(parts[2])
    a3 = int(parts[3])

    # 간단 범위 체크
    for a in (a1, a2, a3):
        if not (0 <= a <= 180):
            raise ValueError("angles must be 0~180")

    return leg, a1, a2, a3

# ===========================
# MAIN
# ===========================
while True:
    try:
        cmd_str = input("\nEnter CMD hex (e.g. 0F, 00, 01, 02, 03): ")
        cmd = hex_to_byte(cmd_str)

        # ----------------------------------------------------
        # CMD = 0x0F : PING
        # ----------------------------------------------------
        if cmd == 0x0F:
            send_packet(0x0F, [])
            continue

        # ----------------------------------------------------
        # CMD = 0x00 : MODE SET
        # ----------------------------------------------------
        if cmd == 0x00:
            mode = hex_to_byte(input("Enter mode (00=CAR, 01=QUAD): "))
            send_packet(0x00, [mode])
            continue

        # ----------------------------------------------------
        # CMD = 0x01 : MOTOR SPEED
        # ----------------------------------------------------
        if cmd == 0x01:
            speed = int(input("Enter speed (-255~255): "))
            data = [speed & 0xFF, (speed >> 8) & 0xFF]
            send_packet(0x01, data)
            continue

        # ----------------------------------------------------
        # CMD = 0x02 : SERVO SET
        # ----------------------------------------------------
        if cmd == 0x02:
            ch = hex_to_byte(input("Enter channel (0~0B hex): "))
            angle = int(input("Enter angle (0~180): "))
            send_packet(0x02, [ch, angle])
            continue

        # ----------------------------------------------------
        # CMD = 0x03 : STATUS REQUEST
        # ----------------------------------------------------
        if cmd == 0x03:
            send_packet(0x03, [])
            continue

        # ----------------------------------------------------
        # CMD = 0x04 : LEG SET (입력: "0 135 120 180")
        # ----------------------------------------------------
        if cmd == 0x04:
            line = input("Enter: <leg> <a1> <a2> <a3> (ex: 0 135 120 180): ")
            leg, a1, a2, a3 = parse_leg_line(line)
            set_leg_angles(leg, a1, a2, a3)
            continue

        print("Unknown command!")

    except KeyboardInterrupt:
        print("\nExit.")
        break

spi.close()