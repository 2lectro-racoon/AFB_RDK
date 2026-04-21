#!/bin/bash
set -e

HOSTNAME_VALUE="$(hostname)"
NUM_SUFFIX="$(echo "$HOSTNAME_VALUE" | grep -oE '[0-9]+$')"

if [[ -n "$NUM_SUFFIX" ]]; then
  SSID="AFB-${NUM_SUFFIX}"
else
  SSID="AFB"
fi
export SSID

LOG_FILE="install_log_$(date +%Y%m%d_%H%M%S).log"
exec > >(tee -a "$LOG_FILE") 2>&1

echo "AutoFormBot Auto Wi-Fi/AP mode switching script install..."

# Enable I2C and SPI (persist across reboots)
# Uses raspi-config non-interactive mode (Raspberry Pi OS)
if command -v raspi-config >/dev/null 2>&1; then
  echo "Enabling I2C and SPI via raspi-config..."
  sudo raspi-config nonint do_i2c 0 || true
  sudo raspi-config nonint do_spi 0 || true
else
  echo "WARNING: raspi-config not found. Skipping I2C/SPI enable step."
fi

# Ensure kernel modules are loaded (best-effort)
# This helps some minimal images where modules are not auto-loaded.
sudo tee /etc/modules-load.d/afb-i2c-spi.conf >/dev/null <<'EOF'
i2c-dev
spi-dev
EOF

# -------------------------------
# direnv: auto venv enable/disable in ~/afb_home
# -------------------------------
# direnv applies environment only inside a directory and automatically unloads it when leaving.
# This avoids global auto-activation and reduces student confusion.

echo "Setting up direnv auto-venv for ~/afb_home..."

# Install direnv (Raspberry Pi OS / Debian)
sudo apt-get update
sudo apt-get install -y direnv

sudo apt install -y python3-pip python3-flask dnsmasq hostapd

# Enable direnv hook for bash (idempotent)
BASHRC="$HOME/.bashrc"
if ! grep -q 'direnv hook bash' "$BASHRC"; then
  {
    echo ''
    echo '# direnv (AutoFormBot)'
    echo 'eval "$(direnv hook bash)"'
  } >> "$BASHRC"
fi

# Enable direnv hook for zsh if ~/.zshrc exists (optional)
ZSHRC="$HOME/.zshrc"
if [ -f "$ZSHRC" ] && ! grep -q 'direnv hook zsh' "$ZSHRC"; then
  {
    echo ''
    echo '# direnv (AutoFormBot)'
    echo 'eval "$(direnv hook zsh)"'
  } >> "$ZSHRC"
fi

# Create the afb_home directory and its .envrc
mkdir -p "$HOME/afb_home"
cat > "$HOME/afb_home/.envrc" <<'EOF'
# AutoFormBot: directory-scoped environment

# Use the unified venv without `source activate` so unloading works reliably.
export VIRTUAL_ENV="$HOME/.afbvenv"
PATH_add "$VIRTUAL_ENV/bin"

# Optional prompt marker (direnv will restore PS1 when leaving)
export PS1="(.afbvenv) ${PS1}"

# Project environment
export AUTOBOT_ROOT="$HOME/AutoFormBotCode"
export PYTHONPATH="$AUTOBOT_ROOT/scripts/gpio:$AUTOBOT_ROOT/scripts/opencv:$AUTOBOT_ROOT/scripts/tflite:$AUTOBOT_ROOT/scripts/YOLOv11:$AUTOBOT_ROOT/scripts/package:$PYTHONPATH"
EOF

# Trust the .envrc so it activates automatically
if command -v direnv >/dev/null 2>&1; then
  direnv allow "$HOME/afb_home" || true
fi

AUTOFORM_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

echo "Copying /scripts/lec to \$HOME..."
cp -r "$AUTOFORM_PATH/scripts/lec_1" "$HOME/afb_home/lec_1"
cp -r "$AUTOFORM_PATH/scripts/lec_2" "$HOME/afb_home/lec_2"
cp -r "$AUTOFORM_PATH/scripts/lec_quad" "$HOME/afb_home/lec_quad"
bash "$AUTOFORM_PATH/scripts/nmservice/02_enable_AP_mode_service.sh" "$SSID"
# bash "$AUTOFORM_PATH/scripts/nmservice/01_setup_web_server.sh"
# bash "$AUTOFORM_PATH/scripts/nmservice/05_enable_auto_wifi_service.sh" "$SSID"
# bash "$AUTOFORM_PATH/scripts/nmservice/07_enable_wifi_monitor.sh" "$SSID"
bash "$AUTOFORM_PATH/scripts/i2c/01_install.sh"
bash "$AUTOFORM_PATH/scripts/i2c/02_i2c_service.sh"
# bash "$AUTOFORM_PATH/scripts/i2c/03_oled_clear_service.sh"
bash "$AUTOFORM_PATH/scripts/opencv/01_opencv_setup.sh"
bash "$AUTOFORM_PATH/scripts/flask/01_flask_setup.sh"
bash "$AUTOFORM_PATH/scripts/YOLOv11/01_yolo_setup.sh"
bash "$AUTOFORM_PATH/scripts/tflite/01_tflite_setup.sh"
bash "$AUTOFORM_PATH/scripts/gpio/01_gpio_setup.sh"
bash "$AUTOFORM_PATH/scripts/afb/01_picamera2_setup.sh"

# bash "$AUTOFORM_PATH/scripts/gpio/01_servo_stop.sh"

echo 'avoid_warnings=1' | sudo tee -a /boot/firmware/config.txt
echo "AutoFormBot Setting Done..."

sudo reboot