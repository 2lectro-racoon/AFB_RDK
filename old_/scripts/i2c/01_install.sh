#!/bin/bash
set -e

USER_HOME=$(eval echo ~${SUDO_USER:-$USER})
VENV_PATH="$USER_HOME/.afbvenv"
OLED_SCRIPT_PATH="$USER_HOME/AutoFormBotCode/scripts/i2c/oled_display.py"

# ✅ Check if virtual environment already exists
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

# ⭐ Activate the virtual environment
source "$VENV_PATH/bin/activate"

# 🔧 Build tools needed for rpi-lgpio/lgpio (native extension)
# lgpio builds a native extension and requires swig.
sudo apt-get update

# Base build tools (always available)
sudo apt-get install -y swig build-essential python3-dev

# Optional system dev package for lgpio (may not exist on some Raspberry Pi OS/Debian repos)
if apt-cache show liblgpio-dev >/dev/null 2>&1; then
  sudo apt-get install -y liblgpio-dev
else
  echo "⚠️  liblgpio-dev not found in apt repos; continuing."
fi

# 📦 Install OLED dependencies
pip install --upgrade pip
pip install \
  adafruit-blinka \
  adafruit-circuitpython-ssd1306 \
  adafruit-circuitpython-ina219 \
  adafruit-circuitpython-vl53l0x \
  adafruit-circuitpython-vl53l1x \
  adafruit-circuitpython-mpu6050 \
  pillow \
  netifaces \
  rpi-lgpio

# 🎉 Done
echo "✅ Virtual environment setup complete."
echo "⚡ To run OLED script manually:"
echo "    source \"$VENV_PATH/bin/activate\" && python \"$OLED_SCRIPT_PATH\""
