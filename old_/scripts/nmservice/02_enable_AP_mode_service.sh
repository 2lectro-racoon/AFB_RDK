#!/bin/bash

set -e

SSID="$1"

if [ -z "$SSID" ]; then
    echo "Usage: $0 <SSID>"
    exit 1
fi

SERVICE_NAME="ap_mode.service"
SERVICE_PATH="/etc/systemd/system/$SERVICE_NAME"
SCRIPT_PATH="$(realpath "$(dirname "$0")")/01_setup_ap_mode.sh"

echo "🔧 Enabling $SERVICE_NAME..."
echo "SSID: $SSID"

sudo tee "$SERVICE_PATH" > /dev/null <<EOF
[Unit]
Description=AutoFormBot AP Mode Service
After=network-online.target NetworkManager.service
Wants=network-online.target

[Service]
Type=oneshot
ExecStart=/usr/bin/env bash "$SCRIPT_PATH" "$SSID"
RemainAfterExit=yes

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable "$SERVICE_NAME"
sudo systemctl start "$SERVICE_NAME"

echo "✅ $SERVICE_NAME has been enabled and started."
