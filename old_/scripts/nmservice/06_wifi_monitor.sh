#!/bin/bash
echo "📡 Monitoring Wi-Fi status..."
INTERFACE=$(iw dev | awk '$1=="Interface"{print $2}')

# SSID for AP fallback (passed from systemd service as $1 and/or env SSID)
AP_SSID="${1:-${SSID:-AFB}}"

# Resolve absolute path to the mode switch script (avoid /home/$USER which becomes /home/root under systemd)
SWITCH_SCRIPT="/home/afb2/AutoFormBotCode/scripts/nmservice/04_auto_wifi_or_ap.sh"

# If the repo path is different, fall back to current user's home (best-effort)
if [ ! -x "$SWITCH_SCRIPT" ]; then
  SWITCH_SCRIPT="/home/$(whoami)/AutoFormBotCode/scripts/nmservice/04_auto_wifi_or_ap.sh"
fi

# Final fallback: try PATH lookup (if installed elsewhere)
if [ ! -x "$SWITCH_SCRIPT" ]; then
  SWITCH_SCRIPT="04_auto_wifi_or_ap.sh"
fi

while true; do
  STATE=$(nmcli -t -f GENERAL.STATE device show $INTERFACE | cut -d: -f2 | cut -d' ' -f1)

  MODE=$(iw dev $INTERFACE info | grep type | awk '{print $2}')
  IP=$(ip -4 addr show $INTERFACE | grep -oP '(?<=inet\s)\d+(\.\d+){3}' | head -n1)

  if [[ "$STATE" -lt 70 && -z "$IP" && "$MODE" != "AP" ]]; then
    echo "⚠️ Wi-Fi disconnected (no IP). Switching mode..."
    $SWITCH_SCRIPT "$AP_SSID"
    # Avoid tight loops if switching fails
    sleep 3
  fi

  sleep 10
done