from flask import Flask, render_template, request, Response
import afb2
import time
import cv2
import os

save_dir = 'captures'

if not os.path.exists(save_dir):
    os.makedirs(save_dir)

app = Flask(__name__)

afb2.gpio.reset()
afb2.camera.init(640, 480, 30)

servo_angle = 90
latest_frame = None


def generate():
    global latest_frame

    while True:
        frame = afb2.camera.get_image()

        frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        latest_frame = frame_rgb.copy()

        _, jpeg = cv2.imencode('.jpg', frame_rgb)

        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n'
               + jpeg.tobytes()
               + b'\r\n')

        time.sleep(0.03)


@app.route('/capture', methods=["POST"])
def capture():
    global latest_frame

    if latest_frame is not None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = f"captures/frame_{timestamp}.jpg"

        cv2.imwrite(path, latest_frame)

        print(f"CAPTURE: {path}")

    return '', 204


@app.route('/')
def index():
    return render_template("index.html")


@app.route('/key', methods=["POST"])
def key():

    global servo_angle
    key = request.form.get("key")

    print("KEY:", key)

    if key == "ArrowUp":
        afb2.car.motor(100)

    elif key == "ArrowDown":
        afb2.car.motor(-100)

    elif key == "ArrowLeft":

        if servo_angle != 40:
            afb2.car.servo(40)
            servo_angle = 40

    elif key == "ArrowRight":

        if servo_angle != 140:
            afb2.car.servo(140)
            servo_angle = 140

    # 모터만 정지
    elif key == "stop":
        afb2.car.motor(0)

    # 서보만 센터
    elif key == "servo_center":

        if servo_angle != 90:
            afb2.car.servo(90)
            servo_angle = 90

    return '', 204


@app.route('/video_feed')
def video_feed():

    return Response(
        generate(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)