#!/bin/bash

echo "📶 Setting up AutoFormBot Wi-Fi Monitor service..."

SSID="$1"

USER_NAME=$(whoami)
SCRIPT_SRC="/home/$USER_NAME/AutoFormBotCode/scripts/nmservice/06_wifi_monitor.sh"
SCRIPT_DEST="/usr/local/bin/autoformbot_wifi_monitor.sh"
SERVICE_FILE="/etc/systemd/system/autoformbot_wifi_monitor.service"

echo $SSID

# Copy script to /usr/local/bin and make it executable
sudo cp "$SCRIPT_SRC" "$SCRIPT_DEST"
sudo chmod +x "$SCRIPT_DEST"

# Create the systemd service file
sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=AutoFormBot Wi-Fi Monitor
After=network.target

[Service]
Type=simple
ExecStart=/usr/bin/env SSID=${SSID} bash "$SCRIPT_DEST" "${SSID}"
Restart=always
User=$USER_NAME

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd and enable/start the service
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable autoformbot_wifi_monitor.service
sudo systemctl start autoformbot_wifi_monitor.service

echo "✅ AutoFormBot Wi-Fi Monitor service registered and started!"