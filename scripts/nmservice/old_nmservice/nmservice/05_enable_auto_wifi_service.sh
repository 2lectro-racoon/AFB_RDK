#!/bin/bash

set -e

SSID="$1"

SERVICE_NAME="auto_wifi_or_ap.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
SCRIPT_PATH="$(realpath "$(dirname "$0")")/04_auto_wifi_or_ap.sh"

echo "🔧 Enabling $SERVICE_NAME..."

echo $SSID

sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=Auto Wi-Fi or AP Mode Switcher
After=network.target
Wants=network.target

[Service]
ExecStart=/usr/bin/env SSID=${SSID} bash "$SCRIPT_PATH" "${SSID}"
Restart=on-failure
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "✅ $SERVICE_NAME has been enabled and started."
