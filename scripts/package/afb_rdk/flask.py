TARGET_SIZE = (640, 480)  # (width, height)
JPEG_QUALITY = 70         # Lower quality reduces CPU + bandwidth
FRAME_INTERVAL = 1 / 30   # Target stream FPS
import threading
from flask import Flask, Response, request, jsonify
import cv2
import time
import afb2

app = Flask(__name__)


# --- Angles endpoints ---
@app.route('/angles.json')
def angles_api_json():
    """Return last-sent servo angles as JSON for debugging/UI."""
    try:
        angles = afb2.quad.getAngle()  # expected: list of length 12
    except Exception:
        angles = [None] * 12

    # Always return exactly 12 values to keep the UI stable.
    if not isinstance(angles, list):
        angles = list(angles)
    if len(angles) < 12:
        angles = angles + [None] * (12 - len(angles))
    elif len(angles) > 12:
        angles = angles[:12]

    return jsonify({"angles": angles})



@app.route('/angles')
def angles_view():
    """Render last-sent servo angles as an HTML grid."""
    # Read angles from the same JSON logic.
    try:
        angles = afb2.quad.getAngle()
    except Exception:
        angles = [None] * 12

    if not isinstance(angles, list):
        angles = list(angles)
    if len(angles) < 12:
        angles = angles + [None] * (12 - len(angles))
    elif len(angles) > 12:
        angles = angles[:12]

    html = '''
    <!doctype html>
    <html>
    <head>
        <meta charset="utf-8" />
        <title>AFB Servo Angles</title>
        <style>
            body {
                margin: 20px;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            }
            .angles {
                width: 100%;
                max-width: 980px;
                margin: 0 auto;
                padding: 12px;
                border: 1px solid #ccc;
                background: #fff;
            }
            .angles-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            .angles-table td {
                border: 1px solid #ddd;
                text-align: center;
                padding: 10px;
            }
            .angles-ch {
                font-weight: 700;
            }
            .angles-val {
                font-size: 22px;
                line-height: 1.2;
            }
            .hint {
                margin-top: 10px;
                color: #666;
            }
        </style>
        <script>
            const ORDER = [11, 10, 9, 0, 1, 2, 8, 7, 6, 3, 4, 5];

            async function fetchAngles() {
                try {
                    const res = await fetch('/angles.json', { cache: 'no-store' });
                    const data = await res.json();
                    const angles = (data && data.angles) ? data.angles : [];

                    for (let i = 0; i < ORDER.length; i++) {
                        const ch = ORDER[i];
                        const el = document.getElementById('angle-' + ch);
                        if (!el) continue;
                        const v = angles[ch];
                        el.textContent = (v === null || v === undefined) ? 'NL' : String(v);
                    }
                } catch (e) {
                    // Ignore fetch errors
                }
            }

            document.addEventListener('DOMContentLoaded', () => {
                fetchAngles();
                setInterval(fetchAngles, 200);
            });
        </script>
    </head>
    <body>
        <div class="angles">
            <h2>Servo Angles (last sent)</h2>
            <table class="angles-table">
                <tr>
                    <td class="angles-ch">CH11</td>
                    <td class="angles-ch">CH10</td>
                    <td class="angles-ch">CH9</td>
                    <td class="angles-ch">CH0</td>
                    <td class="angles-ch">CH1</td>
                    <td class="angles-ch">CH2</td>
                </tr>
                <tr>
                    <td class="angles-val"><span id="angle-11">NL</span></td>
                    <td class="angles-val"><span id="angle-10">NL</span></td>
                    <td class="angles-val"><span id="angle-9">NL</span></td>
                    <td class="angles-val"><span id="angle-0">NL</span></td>
                    <td class="angles-val"><span id="angle-1">NL</span></td>
                    <td class="angles-val"><span id="angle-2">NL</span></td>
                </tr>
                <tr>
                    <td class="angles-ch">CH8</td>
                    <td class="angles-ch">CH7</td>
                    <td class="angles-ch">CH6</td>
                    <td class="angles-ch">CH3</td>
                    <td class="angles-ch">CH4</td>
                    <td class="angles-ch">CH5</td>
                </tr>
                <tr>
                    <td class="angles-val"><span id="angle-8">NL</span></td>
                    <td class="angles-val"><span id="angle-7">NL</span></td>
                    <td class="angles-val"><span id="angle-6">NL</span></td>
                    <td class="angles-val"><span id="angle-3">NL</span></td>
                    <td class="angles-val"><span id="angle-4">NL</span></td>
                    <td class="angles-val"><span id="angle-5">NL</span></td>
                </tr>
            </table>
            <div class="hint">Updates every 200ms via <code>/angles.json</code></div>
        </div>
    </body>
    </html>
    '''

    # Render initial values once (the JS will refresh after load).
    def _fmt(v):
        return 'NL' if (v is None) else str(v)

    html = html.replace('<span id="angle-11">NL</span>', f'<span id="angle-11">{_fmt(angles[11])}</span>')
    html = html.replace('<span id="angle-10">NL</span>', f'<span id="angle-10">{_fmt(angles[10])}</span>')
    html = html.replace('<span id="angle-9">NL</span>', f'<span id="angle-9">{_fmt(angles[9])}</span>')
    html = html.replace('<span id="angle-0">NL</span>', f'<span id="angle-0">{_fmt(angles[0])}</span>')
    html = html.replace('<span id="angle-1">NL</span>', f'<span id="angle-1">{_fmt(angles[1])}</span>')
    html = html.replace('<span id="angle-2">NL</span>', f'<span id="angle-2">{_fmt(angles[2])}</span>')
    html = html.replace('<span id="angle-8">NL</span>', f'<span id="angle-8">{_fmt(angles[8])}</span>')
    html = html.replace('<span id="angle-7">NL</span>', f'<span id="angle-7">{_fmt(angles[7])}</span>')
    html = html.replace('<span id="angle-6">NL</span>', f'<span id="angle-6">{_fmt(angles[6])}</span>')
    html = html.replace('<span id="angle-3">NL</span>', f'<span id="angle-3">{_fmt(angles[3])}</span>')
    html = html.replace('<span id="angle-4">NL</span>', f'<span id="angle-4">{_fmt(angles[4])}</span>')
    html = html.replace('<span id="angle-5">NL</span>', f'<span id="angle-5">{_fmt(angles[5])}</span>')

    return html

# --- Sensors endpoint ---
@app.route('/sensors.json')
def sensors_api_json():
    """Return sensor readings as JSON for debugging/UI.

    Expected sensor API:
    - afb2.sensor.distance() -> int mm
    - afb2.sensor.mpu() -> list/tuple of 6 floats (or values), missing values may be None
    """
    distance_mm = None
    mpu = [None] * 6

    # Distance
    try:
        d = afb2.sensor.distance()
        if d is not None:
            distance_mm = int(d)
    except Exception:
        distance_mm = None

    # MPU (6-axis)
    try:
        vals = afb2.sensor.mpu()
        if vals is not None:
            vals = list(vals)
            if len(vals) < 6:
                vals = vals + [None] * (6 - len(vals))
            elif len(vals) > 6:
                vals = vals[:6]
            mpu = vals
    except Exception:
        mpu = [None] * 6

    return jsonify({"distance_mm": distance_mm, "mpu": mpu})

#
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

def startServer() -> None:
    """Start the Flask server if it is not already running.

    This allows using the web UI (e.g. /stream, /angles) without calling imshow().
    """
    global server_started
    if not server_started:
        threading.Thread(target=flask_thread, daemon=True).start()
        server_started = True

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
            frame = afb2.camera.get_image()
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
            .angles {
                width: 100%;
                max-width: 980px;
                margin: 20px auto;
                padding: 12px;
                border: 1px solid #ccc;
                background: #fff;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            }
            .angles-table {
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }
            .angles-table td {
                border: 1px solid #ddd;
                text-align: center;
                padding: 8px;
            }
            .angles-ch {
                font-weight: 700;
            }
            .angles-val {
                font-size: 18px;
                line-height: 1.2;
            }
            .sensors {
                width: 100%;
                max-width: 980px;
                margin: 20px auto;
                padding: 12px;
                border: 1px solid #ccc;
                background: #fff;
                font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, "Liberation Mono", "Courier New", monospace;
            }
            .sensors-grid {
                display: grid;
                grid-template-columns: repeat(3, 1fr);
                gap: 8px;
                margin-top: 10px;
            }
            .sensor-cell {
                border: 1px solid #ddd;
                padding: 10px;
                text-align: center;
            }
            .sensor-label {
                font-weight: 700;
            }
            .sensor-value {
                margin-top: 6px;
                font-size: 18px;
                line-height: 1.2;
            }
            .sensor-wide {
                grid-column: 1 / -1;
            }
        </style>
        <script>
            const ORDER = [11, 10, 9, 0, 1, 2, 8, 7, 6, 3, 4, 5];

            async function fetchAngles() {
                try {
                    const res = await fetch('/angles.json', { cache: 'no-store' });
                    const data = await res.json();
                    const angles = (data && data.angles) ? data.angles : [];

                    for (let i = 0; i < ORDER.length; i++) {
                        const ch = ORDER[i];
                        const el = document.getElementById('angle-' + ch);
                        if (!el) continue;
                        const v = angles[ch];
                        el.textContent = (v === null || v === undefined) ? 'NL' : String(v);
                    }
                } catch (e) {
                    // Ignore fetch errors (server might be starting)
                }
            }

            async function fetchSensors() {
                try {
                    const res = await fetch('/sensors.json', { cache: 'no-store' });
                    const data = await res.json();

                    const d = (data && data.distance_mm !== undefined) ? data.distance_mm : null;
                    const distEl = document.getElementById('distance-mm');
                    if (distEl) {
                        distEl.textContent = (d === null || d === undefined) ? 'NL' : String(d);
                    }

                    const mpu = (data && data.mpu) ? data.mpu : [];
                    for (let i = 0; i < 6; i++) {
                        const el = document.getElementById('mpu-' + i);
                        if (!el) continue;
                        const v = mpu[i];
                        el.textContent = (v === null || v === undefined) ? 'NL' : String(v);
                    }
                } catch (e) {
                    // Ignore fetch errors
                }
            }

            document.addEventListener('DOMContentLoaded', () => {
                fetchAngles();
                fetchSensors();
                setInterval(fetchAngles, 200);
                setInterval(fetchSensors, 200);
            });
        </script>
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

        <div class="angles">
            <h3>Servo Angles (last sent)</h3>
            <table class="angles-table">
                <tr>
                    <td class="angles-ch">CH11</td>
                    <td class="angles-ch">CH10</td>
                    <td class="angles-ch">CH9</td>
                    <td class="angles-ch">CH0</td>
                    <td class="angles-ch">CH1</td>
                    <td class="angles-ch">CH2</td>
                </tr>
                <tr>
                    <td class="angles-val"><span id="angle-11">NL</span></td>
                    <td class="angles-val"><span id="angle-10">NL</span></td>
                    <td class="angles-val"><span id="angle-9">NL</span></td>
                    <td class="angles-val"><span id="angle-0">NL</span></td>
                    <td class="angles-val"><span id="angle-1">NL</span></td>
                    <td class="angles-val"><span id="angle-2">NL</span></td>
                </tr>
                <tr>
                    <td class="angles-ch">CH8</td>
                    <td class="angles-ch">CH7</td>
                    <td class="angles-ch">CH6</td>
                    <td class="angles-ch">CH3</td>
                    <td class="angles-ch">CH4</td>
                    <td class="angles-ch">CH5</td>
                </tr>
                <tr>
                    <td class="angles-val"><span id="angle-8">NL</span></td>
                    <td class="angles-val"><span id="angle-7">NL</span></td>
                    <td class="angles-val"><span id="angle-6">NL</span></td>
                    <td class="angles-val"><span id="angle-3">NL</span></td>
                    <td class="angles-val"><span id="angle-4">NL</span></td>
                    <td class="angles-val"><span id="angle-5">NL</span></td>
                </tr>
            </table>
            <p style="margin-top:10px; color:#666;">Updates every 200ms via <code>/angles.json</code></p>
        </div>

        <div class="sensors">
            <h3>Sensors</h3>
            <div class="sensors-grid">
                <div class="sensor-cell">
                    <div class="sensor-label">MPU Ax</div>
                    <div class="sensor-value"><span id="mpu-0">NL</span></div>
                </div>
                <div class="sensor-cell">
                    <div class="sensor-label">MPU Ay</div>
                    <div class="sensor-value"><span id="mpu-1">NL</span></div>
                </div>
                <div class="sensor-cell">
                    <div class="sensor-label">MPU Az</div>
                    <div class="sensor-value"><span id="mpu-2">NL</span></div>
                </div>
                <div class="sensor-cell">
                    <div class="sensor-label">MPU Gx</div>
                    <div class="sensor-value"><span id="mpu-3">NL</span></div>
                </div>
                <div class="sensor-cell">
                    <div class="sensor-label">MPU Gy</div>
                    <div class="sensor-value"><span id="mpu-4">NL</span></div>
                </div>
                <div class="sensor-cell">
                    <div class="sensor-label">MPU Gz</div>
                    <div class="sensor-value"><span id="mpu-5">NL</span></div>
                </div>
                <div class="sensor-cell sensor-wide">
                    <div class="sensor-label">Distance (mm)</div>
                    <div class="sensor-value"><span id="distance-mm">NL</span></div>
                </div>
            </div>
            <p style="margin-top:10px; color:#666;">Updates every 200ms via <code>/sensors.json</code></p>
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
        afb2.car.motor(100)
        # afb.gpio.motor(100, 1, 1)
    elif key == "ArrowDown":
        afb2.car.motor(-100)
        # afb.gpio.motor(100, -1, 1)
    elif key == "ArrowLeft":
        if servo_angle != 40:
            afb2.car.servo(40)
            # afb.gpio.servo(40)
            servo_angle = 40
    elif key == "ArrowRight":
        if servo_angle != 140:
            afb2.car.servo(140)
            # afb.gpio.servo(140)
            servo_angle = 140
    elif key == "stop":
        # afb.gpio.motor(0, 1, 1)
        afb2.car.motor(0)
        if servo_angle != 90:
            afb2.car.servo(90)
            # afb.gpio.servo(90)
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

    startServer()

def capture():
    """Backward-compatible helper to start the Flask server."""
    startServer()