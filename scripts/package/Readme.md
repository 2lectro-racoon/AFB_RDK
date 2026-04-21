# AutoFormBot afp package

## ✨ Overview

AuotFormBot에 구동에 필요한 커스텀 패키지 (ver 2.0.0)

---

## 패키지 구성

| 패키지명 | 설명 |
|--------|---------|
| `/afb/__init__.py` | AutoFormBot의 카메라, GPIO, 센서, 제어 기능을 하나의 `afb` 인터페이스로 통합하는 패키지 엔트리포인트 |
| `/afb/_spi_bus.py` | 라즈베리파이 ↔ STM32 컨트롤 보드 간 SPI 통신을 담당하는 저수준 버스 모듈 |
| `/afb/camera.py` | libcamera 기반 카메라 초기화 및 프레임 획득을 담당하는 모듈 |
| `/afb/car.py` | 차량(자율주행차) 모드에서의 조향 및 구동 제어 로직 모듈 |
| `/afb/flask.py` | Headless 환경에서 카메라 영상을 웹으로 확인하기 위한 Flask 기반 스트리밍 모듈 |
| `/afb/gpio.py` | GPIO를 이용한 컨트롤 보드 초기화 및 제어 모듈 |
| `/afb/quad.py` | 4족(거미형) 로봇 모드에서의 다리 및 관절 제어 로직 모듈 |
| `/afb/sensor.py` | 거리 센서 및 IMU(MPU) 등 I2C 센서 값을 읽어오는 공용 센서 인터페이스 모듈 |

---

## How To Use [For v2 (Rev >= 1.2)]

### 0. Activate AFB_venv

파이썬 가상환경 활성화 또는 전용 경로 접속  

```bash
cd ~/afb_home
```
or  

```bash
source ~/.afbvenv/bin/activate
```

파이썬 파일에서 패키지 임포트  

```python
import afb2
```

### 1. Camera

카메라 초기설정  

```python
afb2.camera.init(width, height, framerate) # 기본값 640, 480, 30
```

카메라 프레임 불러오기  

```python
frame = afb2.camera.get_image()
```

카메라 해제  

```python
afb2.camera.release_camera()
```

### 2. Flask

Headless 상황에서(SSH 접속 등) 최대 4채널의 영상 출력 지원 및 쿼드모드의 12채널 서보각도, 센서값 실시간 모니터링 지원  

아래의 함수 실행 후 웹에서 라즈베리파이 IP:5000/stream 으로 접속 후 새로고침하여 사용

```python
afb2.flask.imshow(title, frame, slot) # 영상 제목(문자열), 출력하고자 하는 영상 프레임, 위치(0, 1, 2, 3)
```
카메라 사용 없이 각도 및 센서 값을 보고 싶다면 아래의 코드 샤용  
```python
afb2.flask.startServer() # 카메라 활성화 없이 플라스크 실행할 때 사용
```

![Flask 화면](/images/flask.png)

### 3.A 컨트롤 보드 리셋 

꼭 SPI통신 안정화를 위해 컨트롤 보드 제어 전 리셋 시행  

```python
afb2.gpio.reset()
```

컨트롤 보드의 각 모드는 펌웨어로 구분, 출고 시 해당 펌웨어로 출고  

### 3.B 차량모드 제어

조향 제어

```python
afb2.car.servo(angle) # 기본값 90(중심) 30~150 권장
```

구동모터 제어

```python
afb2.car.motor(speed) # -255~255(기본값 0)
```
or  

```python
afb2.car.motor(speed, inverse) # -255~255(기본값 0), 1 or -1(기본값 1, 역방향 구동시 -1)
```

### 3.C 쿼드모드 제어

개별 관절(채널) 제어  

```python
#|---------------------------------|
#|          Front(Camera)          |
#|---------------------------------|
#| 11 |                       |  2 |
#|---- -----             ----- ----|
#|    | 10 |             |  1 |    |
#|    ----- -----   ----- ----     |
#|         |  9 |   |  0 |         |
#|          -----   -----          |
#|         |  6 |   |  3 |         |
#|    ----- -----   ----- ----     |
#|    |  7 |             |  4 |    |
#|---- -----             ----- ----|
#|  8 |                       |  5 |
#|---------------------------------|

afb2.quad.servo(ch, angle) # ch: 0~11채널, angle: 0~180 이나 채널 별로 간섭 여부 확인 필요
```

개별 다리 제어  

```python
#|---------------------------------------------------------|
#|                      Front(Camera)                      |
#|---------------------------------------------------------|
#| ch3-a2 |                                       | ch0-a2 |
#|-------- --------                       -------- --------|
#|        | ch3-a1 |                     | ch0-a1 |        |
#|         -------- --------     -------- --------         |
#|                 | ch3-a0 |   | ch0-a0 |                 |
#|                  --------     --------                  |
#|                 | ch2-a0 |   | ch1-a0 |                 |
#|         -------- --------     -------- --------         |
#|        | ch2-a1 |                     | ch1-a1 |        |
#|-------- --------                       -------- --------|
#| ch2-a2 |                                       | ch1-a2 |
#|---------------------------------------------------------|

afb2.quad.leg(ch, a0, a1, 2) # ch: 0~3, a0,1,2: 0~180 이나 채널 별로 간섭 여부 확인 필요
```
중립 자세  

```python
#|---------------------------------------|
#|              Front(Camera)            |
#|---------------------------------------|
#|  90 |                           |  90 |
#|----- -----                 ----- -----|
#|     | 120 |               |  60 |     |
#|      ----- -----     ----- -----      |
#            |  90 |   |  90 |           |
#|            -----     -----            |
#|           |  90 |   |  90 |           |
#|      ----- -----     ----- -----      |
#|     |  40 |               | 140 |     |
#|----- -----                 ----- -----|
#|  90 |                           |  90 |
#|---------------------------------------|

afb2.quad.stand()
```
기본 자세  

```python
#|---------------------------------------|
#|              Front(Camera)            |
#|---------------------------------------|
#|   0 |                           | 180 |
#|----- -----                 ----- -----|
#|     | 180 |               |   0 |     |
#|      ----- -----     ----- -----      |
#            | 135 |   |  40 |           |
#|            -----     -----            |
#|           |  40 |   | 135 |           |
#|      ----- -----     ----- -----      |
#|     |   0 |               | 180 |     |
#|----- -----                 ----- -----|
#| 180 |                           |   0 |
#|---------------------------------------|

afb2.quad.legReset()
```
### 3.D 센서 값 읽기

전면 거리센서  

```python
afb2.sensor.distance()

# >>> mm 단위로 전면 거리 값 출력(int형)
```

IMU 센서  

```python
afb2.sensor.mpu()

# >>> [accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z] raw 데이터 출력
```

IMU의 경우 자율주행차량에는 미장착 되어있음  

---

## How To Use [For v1 (Rev < 1.2)] NOY TESTED

### 0. Activate AFB_venv

파이썬 가상환경 활성화 또는 전용 경로 접속  

```bash
cd ~/afb_home
```
or  

```bash
source ~/.afbvenv/bin/activate
```

파이썬 파일에서 패키지 임포트  

```python
import afb1
```

### 1. Camera

카메라 초기설정  

```python
afb1.camera.init(width, height, framerate) # 기본값 640, 480, 30
```

카메라 프레임 불러오기  

```python
frame = afb1.camera.get_image()
```

카메라 해제  

```python
afb1.camera.release_camera()
```

### 2. Flask

Headless 상황에서(SSH 접속 등) 최대 4채널의 영상 출력 지원  

아래의 함수 실행 후 웹에서 라즈베리파이 IP:5000/stream으로 접속 후 새로고침하여 사용

```python
afb1.flask.imshow(title, frame, slot) # 영상 제목(문자열), 출력하고자 하는 영상 프레임, 위치(0, 1, 2, 3)
```

![Flask 화면](/images/flask.png)

### 3. Gpio

gpio 초기설정  

```python
afb1.gpio.init()
```

조향 제어

```python
afb1.gpio.servo(angle) # 기본값 90(중심) 30~150 권장
```

구동모터 제어

```python
afb1.gpio.motor(speed, inverse, motor_id) # -255~255(기본값 0), 1 or -1(기본값 1, 역방향 구동시 -1), 1 or 2(기본값 1채널)
```

TB6612FNG STBY핀 제어

```python
afb1.gpio.stby(state) # 0 or 1 (기본값 False)
```

전체 해제

```python
afb.gpio.stop_all()
```
---