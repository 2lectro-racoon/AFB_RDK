#!/bin/bash
set -e

# 첫 줄은 권한 문제 해결용으로 유지
sudo usermod -aG i2c afb

echo "🧩 Setting up I2C environment and services..."

# sudo로 실행 시 원래 사용자 우선 사용
USER_NAME=${SUDO_USER:-$(whoami)}
USER_HOME=$(eval echo ~${USER_NAME})
VENV_PATH="$USER_HOME/.afbvenv"
WORK_DIR="$USER_HOME/AFB_RDK"
PROJECT_ROOT="$USER_HOME/AFB_RDK"
I2C_DIR="$PROJECT_ROOT/scripts/i2c"
I2C_MANAGER_PATH="$I2C_DIR/i2c_manager.py"
OLED_CLEAR_PATH="$I2C_DIR/oled_clear.py"
OLED_DISPLAY_PATH="$I2C_DIR/oled_display.py"
UDS_PATH="/run/autoformbot/afb_i2c.sock"

I2C_SERVICE_FILE="/etc/systemd/system/i2c_manager.service"
OLED_CLEAR_SERVICE_FILE="/etc/systemd/system/oled_clear.service"

ensure_file_exists() {
    local file_path="$1"
    local label="$2"

    if [ ! -f "$file_path" ]; then
        echo "❌ $label 파일이 없습니다: $file_path"
        exit 1
    fi
}

# 필수 Python 파일 확인
ensure_file_exists "$I2C_MANAGER_PATH" "i2c_manager.py"
ensure_file_exists "$OLED_CLEAR_PATH" "oled_clear.py"

# oled_display.py 는 수동 실행 안내용이라 있으면 안내, 없어도 진행
if [ -f "$OLED_DISPLAY_PATH" ]; then
    HAS_OLED_DISPLAY=1
else
    HAS_OLED_DISPLAY=0
fi

# 가상환경 생성/확인
if [ ! -d "$VENV_PATH" ]; then
    echo "🔧 Creating Python virtual environment at $VENV_PATH"
    python3 -m venv "$VENV_PATH"
    if [ ! -f "$VENV_PATH/bin/python3" ]; then
        echo "❌ Failed to create virtual environment. Exiting."
        exit 1
    fi
else
    echo "📂 Virtual environment already exists. Skipping creation."
fi

# 가상환경 활성화
source "$VENV_PATH/bin/activate"

# lgpio/native extension용 빌드 도구 설치
sudo apt-get update
sudo apt-get install -y swig build-essential python3-dev

if apt-cache show liblgpio-dev >/dev/null 2>&1; then
    sudo apt-get install -y liblgpio-dev
else
    echo "⚠️  liblgpio-dev not found in apt repos; continuing."
fi

# Python 패키지 설치
echo "📦 Installing I2C Python packages..."
pip install --upgrade pip
pip install \
  adafruit-blinka \
  adafruit-circuitpython-ssd1306 \
  adafruit-circuitpython-ina219 \
  adafruit-circuitpython-vl53l0x \
  adafruit-circuitpython-vl53l1x \
#   adafruit-circuitpython-mpu6050 \
  pillow \
  netifaces \
  rpi-lgpio

# i2c_manager 서비스 파일 생성
PYTHON_PATH="$VENV_PATH/bin/python3"

sudo tee "$I2C_SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=AutoFormBot I2C Manager (OLED + sensors + UDS)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=$WORK_DIR

# Force Adafruit Blinka to use lgpio backend when needed
# Environment=BLINKA_FORCECHIP=BCM2XXX
# Environment=BLINKA_FORCEGPIO=lgpio

Environment=PYTHONUNBUFFERED=1
Environment=AFB_USER=$USER_NAME

SupplementaryGroups=i2c gpio video

RuntimeDirectory=autoformbot
RuntimeDirectoryMode=0775

ExecStartPre=/bin/rm -f $UDS_PATH
ExecStart=$PYTHON_PATH $I2C_MANAGER_PATH
ExecStopPost=$PYTHON_PATH $OLED_CLEAR_PATH

StandardOutput=journal
StandardError=journal

Restart=always
RestartSec=1
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

# oled_clear 서비스 파일 생성
sudo tee "$OLED_CLEAR_SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Clear OLED screen before shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target
Requires=i2c_manager.service
After=i2c_manager.service

[Service]
Type=oneshot
ExecStart=$PYTHON_PATH $OLED_CLEAR_PATH
RemainAfterExit=yes
User=$USER_NAME
Group=$USER_NAME

[Install]
WantedBy=halt.target reboot.target shutdown.target
EOF

# systemd 반영 및 서비스 등록
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable i2c_manager.service
sudo systemctl enable oled_clear.service

echo "✅ I2C setup complete."
echo
echo "Useful commands:"
echo "  sudo systemctl status i2c_manager.service"
echo "  sudo journalctl -u i2c_manager.service -f"
echo "  sudo systemctl restart i2c_manager.service"

if [ "$HAS_OLED_DISPLAY" -eq 1 ]; then
    echo
echo "⚡ To run OLED script manually:"
echo "  source \"$VENV_PATH/bin/activate\" && python \"$OLED_DISPLAY_PATH\""
fi

echo
echo "⚠️  i2c 그룹 권한 반영을 위해 한 번 재로그인 또는 재부팅이 필요할 수 있습니다."