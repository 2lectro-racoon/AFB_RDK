#!/bin/bash

echo "🧼 Setting up OLED clear service..."

USER_NAME=$(whoami)
SERVICE_FILE="/etc/systemd/system/oled_clear.service"
PYTHON_PATH="/home/$USER_NAME/.afbvenv/bin/python3"
SCRIPT_PATH="/home/$USER_NAME/AutoFormBotCode/scripts/i2c/oled_clear.py"

# Create the systemd service file
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Clear OLED screen before shutdown
DefaultDependencies=no
Before=shutdown.target reboot.target halt.target
Requires=oled_display.service
After=oled_display.service

[Service]
Type=oneshot
ExecStart=$PYTHON_PATH $SCRIPT_PATH
RemainAfterExit=yes
User=$USER_NAME

[Install]
WantedBy=halt.target reboot.target shutdown.target
EOF

# Reload systemd and enable the service
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable oled_clear.service

echo "✅ OLED clear service registered and enabled!"