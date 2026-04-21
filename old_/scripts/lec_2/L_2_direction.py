import afb2
import time

afb2.gpio.reset()  # GPIO 초기화

try:
    while True:
        angle = int(input("조향 각도 입력 (30~150): "))
        afb2.car.servo(angle)
        time.sleep(0.5)

except KeyboardInterrupt:
    print("사용자 종료")



