import afb2
import cv2
import numpy as np
from tensorflow.keras.models import load_model

# 모델 로드
model = load_model('CNN.h5')
class_names = ['go', 'left', 'right']

# 시스템 초기화
afb2.gpio.reset()
afb2.camera.init(640, 480, 15)

prev_class = None
i = 0

try:

    while True:

        # 기본 전진
        afb2.car.motor(60)

        frame = afb2.camera.get_image()

        frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)

        height = frame_bgr.shape[0]
        roi = frame_bgr[int(height * 0.5):, :]

        input_img = cv2.resize(roi, (64, 64))
        input_img = input_img.astype(np.float32) / 255.0
        input_img = np.expand_dims(input_img, axis=0)

        prediction = model.predict(input_img, verbose=0)

        pred_class = class_names[np.argmax(prediction)]
        confidence = np.max(prediction)

        print(f"[{i}] {pred_class.upper()} ({confidence:.2f})")
        i += 1

        # 표시용 텍스트
        label = f"{pred_class.upper()} ({confidence:.2f})"

        cv2.putText(
            frame_bgr,
            label,
            (10, 30),
            cv2.FONT_HERSHEY_SIMPLEX,
            1,
            (0, 255, 0),
            2
        )

        cv2.rectangle(
            frame_bgr,
            (0, int(height * 0.5)),
            (640, 480),
            (255, 0, 0),
            2
        )

        # 웹 스트리밍
        afb2.flask.imshow("AFB Camera", frame_bgr, 0)

        # 조향 변경
        if pred_class != prev_class:

            if pred_class == 'left':
                afb2.car.servo(30)

            elif pred_class == 'right':
                afb2.car.servo(150)

            elif pred_class == 'go':
                afb2.car.servo(80)

            prev_class = pred_class

        if cv2.waitKey(1) & 0xFF == ord('q'):
            break

finally:

    afb2.car.motor(0)
    afb2.camera.release_camera()
    cv2.destroyAllWindows()