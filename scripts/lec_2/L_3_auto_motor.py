import afb2
import time

afb2.gpio.reset()

try:
    while True:
        print("앞으로 전진")
        afb2.car.motor(70)   # 왼쪽 모터
        time.sleep(2)

        print("정지")
        afb2.car.motor(0)
        time.sleep(1)

        print("뒤로 후진")
        afb2.car.motor(-70)
        time.sleep(2)

        print("정지")
        afb2.car.motor(0)
        time.sleep(1)

except KeyboardInterrupt:
    print("사용자 종료")

finally:
    afb2.car.motor(0)