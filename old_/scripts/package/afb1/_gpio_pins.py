# gpio_pins.py

# frozen namespace: disallows modification of predefined values
from types import SimpleNamespace

class FrozenNamespace(SimpleNamespace):
    def __setattr__(self, key, value):
        raise TypeError(f"Cannot modify constant GPIO pin: {key}")

PINS = FrozenNamespace(
    # Servo
    SERVO_PIN = 18,           # GPIO19: Servo control signal (Rev1.3)
    # SERVO_PIN = 19,           # GPIO19: Servo control signal (Rev1.2)

    # LEDs
    LED_RIGHT = 24,            # GPIO7: Right LED (Rev1.3)
    LED_LEFT  = 17,            # GPIO8: Left LED (Rev1.3)
    # LED_RIGHT = 7,            # GPIO7: Right LED (Rev1.2)
    # LED_LEFT  = 8,            # GPIO8: Left LED (Rev1.2)

    # Motor Driver (TB6612FNG)
    STBY    = 26,             # GPIO26: TB6612FNG standby pin

    M1_IN1  = 16,             # GPIO16: Motor 1 input 1
    M1_IN2  = 20,             # GPIO20: Motor 1 input 2
    M1_PWM  = 12,             # GPIO12: Motor 1 PWM

    M2_IN1  = 6,              # GPIO6: Motor 2 input 1
    M2_IN2  = 5,              # GPIO5: Motor 2 input 2
    M2_PWM  = 13,             # GPIO13: Motor 2 PWM

    # Battery Level LEDs
    # BAT_100 = 23,             # GPIO23: Battery 100%
    BAT_100  = 24,            # GPIO24: Battery 100%
    BAT_50  = 25,             # GPIO25: Battery 50%
    BAT_10  = 27              # GPIO27: Battery 10%
)