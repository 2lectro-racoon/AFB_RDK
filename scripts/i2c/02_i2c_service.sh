#!/bin/bash
set -e

echo "🧩 Setting up I2C Manager service..."

# If this script is run with sudo, prefer the invoking user
USER_NAME=${SUDO_USER:-$(whoami)}
SERVICE_FILE="/etc/systemd/system/i2c_manager.service"
PYTHON_PATH="/home/$USER_NAME/.afbvenv/bin/python3"
SCRIPT_PATH="/home/$USER_NAME/AutoFormBotCode/scripts/i2c/i2c_manager.py"
OLED_CLEAR_PATH="/home/$USER_NAME/AutoFormBotCode/scripts/i2c/oled_clear.py"
UDS_PATH="/run/autoformbot/afb_i2c.sock"

# Create the systemd service file
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=AutoFormBot I2C Manager (OLED + sensors + UDS)
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=$USER_NAME
Group=$USER_NAME
WorkingDirectory=/home/$USER_NAME

# Force Adafruit Blinka to use lgpio backend (works on both Raspberry Pi 4 and 5)
# Environment=BLINKA_FORCECHIP=BCM2XXX
# Environment=BLINKA_FORCEGPIO=lgpio

Environment=PYTHONUNBUFFERED=1

# Ensure i2c_manager logs under /home/<USER>/afb_home even if env differs
Environment=AFB_USER=$USER_NAME

# Ensure the service user can access I2C / GPIO devices (depends on distro setup)
SupplementaryGroups=i2c gpio video

# Create /run/autoformbot at runtime (owned by root but writable as needed)
RuntimeDirectory=autoformbot
RuntimeDirectoryMode=0775

# Remove stale socket before start
ExecStartPre=/bin/rm -f $UDS_PATH

ExecStart=$PYTHON_PATH $SCRIPT_PATH

# Explicitly clear OLED on stop/shutdown
ExecStopPost=$PYTHON_PATH $OLED_CLEAR_PATH

StandardOutput=journal
StandardError=journal

Restart=always
RestartSec=1
TimeoutStopSec=10

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable/start the service
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable i2c_manager.service

# NOTE: Do not start the service during install. Dependencies (pip packages) may not be ready yet.
# Start it after the full install is complete (or after reboot).
# sudo systemctl restart i2c_manager.service

echo "✅ i2c_manager service registered! (start after install/reboot)"

echo "\nUseful commands:"
echo "  sudo systemctl status i2c_manager.service"
echo "  sudo journalctl -u i2c_manager.service -f"
