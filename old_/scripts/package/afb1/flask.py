TARGET_SIZE = (640, 480)  # (width, height)
JPEG_QUALITY = 70         # Lower quality reduces CPU + bandwidth
FRAME_INTERVAL = 1 / 30   # Target stream FPS
import threading
from flask import Flask, Response, request
import cv2
import time
import afb1

app = Flask(__name__)
 # Each slot keeps the latest *already encoded* JPEG to avoid per-client re-encode.
streams = [
    {"frame": None, "jpeg": None, "name": None, "ts": 0.0} for _ in range(4)
]  # index 0–3
server_started = False

latest_frame = None
servo_angle = 90

def flask_thread():
    # Enable threaded serving so multiple browser clients don't block each other.
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)

@app.route('/video_feed/<int:slot>')
def video_feed(slot):
    # Guard invalid slot indexes.
    if slot < 0 or slot >= len(streams):
        return ("Invalid slot", 404)

    def generate():
        try:
            last_ts = 0.0
            while True:
                item = streams[slot]
                jpeg = item.get("jpeg")
                ts = item.get("ts", 0.0)

                # Wait until we have a frame.
                if jpeg is None:
                    time.sleep(0.01)
                    continue

                # If nothing changed, sleep a bit to reduce busy looping.
                if ts == last_ts:
                    time.sleep(0.005)
                    continue

                last_ts = ts
                yield (
                    b'--frame\r\n'
                    b'Content-Type: image/jpeg\r\n'
                    b'Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n'
                    b'Pragma: no-cache\r\n'
                    b'Expires: 0\r\n\r\n' + jpeg + b'\r\n'
                )

                # Optional pacing (helps some browsers avoid buffering bursts).
                time.sleep(FRAME_INTERVAL)
        except GeneratorExit:
            print(f"[INFO] Client disconnected from slot {slot}")

    resp = Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    # Some proxies (e.g., nginx) buffer by default; this header tells them not to.
    resp.headers['X-Accel-Buffering'] = 'no'
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/video_feed')
def single_video_feed():
    def generate():
        global latest_frame
        last_time = 0.0
        while True:
            frame = afb1.camera.get_image()
            latest_frame = frame.copy()

            # Encode once per loop, avoid extra colorspace roundtrips.
            # Keep the stream in BGR -> JPEG (browsers can decode JPEG regardless).
            ok, jpeg = cv2.imencode(
                '.jpg',
                cv2.resize(frame, TARGET_SIZE),
                [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
            )
            if not ok:
                time.sleep(0.01)
                continue

            yield (
                b'--frame\r\n'
                b'Content-Type: image/jpeg\r\n'
                b'Cache-Control: no-store, no-cache, must-revalidate, max-age=0\r\n'
                b'Pragma: no-cache\r\n'
                b'Expires: 0\r\n\r\n' + jpeg.tobytes() + b'\r\n'
            )

            # Pace to target FPS.
            now = time.time()
            dt = now - last_time
            last_time = now
            sleep_s = max(0.0, FRAME_INTERVAL - dt)
            time.sleep(sleep_s)

    resp = Response(generate(), mimetype='multipart/x-mixed-replace; boundary=frame')
    resp.headers['X-Accel-Buffering'] = 'no'
    resp.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
    resp.headers['Pragma'] = 'no-cache'
    resp.headers['Expires'] = '0'
    return resp

@app.route('/stream')
def stream_viewer():
    html = '''
    <!doctype html>
    <html>
    <head>
        <title>AFB Stream Viewer</title>
        <style>
            .container {
                display: flex;
                flex-wrap: wrap;
                justify-content: center;
                gap: 20px;
            }
            .stream {
                text-align: center;
                flex: 1 1 300px;
            }
            img {
                width: 100%;
                max-width: 480px;
                height: auto;
                border: 1px solid #ccc;
            }
        </style>
    </head>
    <body>
        <h1>AFB Stream Viewer</h1>
        <div class="container">
    '''
    for idx in range(4):
        label = streams[idx]["name"] if streams[idx]["name"] else f"Slot {idx}"
        html += f'''
            <div class="stream">
                <h3>{label}</h3>
                <img src="/video_feed/{idx}">
            </div>
        '''
    html += '''
        </div>
    </body>
    </html>
    '''
    return html

@app.route('/capture', methods=['GET', 'POST'])
def capture_page():
    if request.method == 'POST':
        # handle capture action, e.g. save image or other
        pass
    return '''
    <!DOCTYPE html>
    <html lang="ko">
    <head>
      <meta charset="UTF-8">
      <title>AFB 자동차 키보드 제어</title>
      <script>
        document.addEventListener("keydown", function(event) {
          fetch("/key", {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: "key=" + event.key
          });
        });

        document.addEventListener("keyup", function(event) {
          fetch("/key", {
            method: "POST",
            headers: {"Content-Type": "application/x-www-form-urlencoded"},
            body: "key=stop"
          });
        });

        document.addEventListener("keydown", function(event) {
          if (event.key === "a") {
            fetch("/imwrite", { method: "POST" });
          }
        });
      </script>
    </head>
    <body>
      <h2>AFB 자동차 키보드 제어</h2>
      <p><strong>페이지 클릭 후 방향키(↑ ↓ ← →)로 제어하세요.</strong></p>
      <hr>
      <h3>🚗 실시간 카메라 영상</h3>
      <img src="/video_feed" width="640" height="480">
    </body>
    </html>
    '''

@app.route('/key', methods=['POST'])
def key_control():
    global servo_angle
    key = request.form.get('key')
    if key == "ArrowUp":
        afb1.gpio.motor(100, 1, 1)
    elif key == "ArrowDown":
        afb1.gpio.motor(100, -1, 1)
    elif key == "ArrowLeft":
        if servo_angle != 40:
            afb1.gpio.servo(40)
            servo_angle = 40
    elif key == "ArrowRight":
        if servo_angle != 140:
            afb1.gpio.servo(140)
            servo_angle = 140
    elif key == "stop":
        afb1.gpio.motor(0, 1, 1)
        if servo_angle != 90:
            afb1.gpio.servo(90)
            servo_angle = 90
    return ('', 204)

def imwrite():
    global latest_frame
    if latest_frame is not None:
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        path = f"captures/frame_{timestamp}.jpg"
        cv2.imwrite(path, cv2.cvtColor(latest_frame, cv2.COLOR_RGB2BGR))
        print(f"✅ 캡처됨: {path}")
    return '', 204

def imshow(name, frame, slot):
    global server_started

    frame = cv2.resize(frame, TARGET_SIZE)

    if 0 <= slot < 4:
        # Encode once here (producer side) so each client doesn't re-encode.
        ok, jpeg = cv2.imencode(
            '.jpg',
            frame,
            [int(cv2.IMWRITE_JPEG_QUALITY), JPEG_QUALITY],
        )
        if ok:
            streams[slot]["frame"] = frame
            streams[slot]["jpeg"] = jpeg.tobytes()
            streams[slot]["name"] = name
            streams[slot]["ts"] = time.time()

    if not server_started:
        threading.Thread(target=flask_thread, daemon=True).start()
        server_started = True

def capture():
    global server_started
    if not server_started:
        threading.Thread(target=flask_thread, daemon=True).start()
        server_started = True