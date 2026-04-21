#!/bin/bash

# Fail fast on errors in pipelines, but keep undefined vars safe in this script
set -o pipefail

# --- helpers ---
log() { echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"; }

AP_IP_CIDR="192.168.4.1/24"

is_hostapd_active() {
  systemctl is-active --quiet hostapd
}

iface_type() {
  iw dev "$INTERFACE" info 2>/dev/null | awk '/\btype\b/{print $2; exit}'
}

ensure_managed_for_scan() {
  # Make sure NetworkManager manages wlan0 and the iface is in managed mode
  sudo rm -f /etc/NetworkManager/conf.d/99-unmanaged-wlan0.conf
  # NM often needs a restart to reliably pick up unmanaged-devices changes
  sudo systemctl restart NetworkManager || true
  sleep 1
  sudo ip link set "$INTERFACE" down || true
  sleep 0.5
  sudo iw dev "$INTERFACE" set type managed || true
  sleep 0.5
  sudo ip link set "$INTERFACE" up || true
  sudo nmcli dev set "$INTERFACE" managed yes || true
}

stop_ap_services_if_any() {
  sudo systemctl stop hostapd || true
  sudo systemctl stop dnsmasq || true
}

cleanup_ap_ip() {
  # Remove AP IP if it was left behind
  sudo ip addr del "$AP_IP_CIDR" dev "$INTERFACE" 2>/dev/null || true
}

wait_for_nm_connected() {
  # Returns 0 if connected (>=70) within timeout
  local tries=${1:-10}
  local i state
  for i in $(seq 1 "$tries"); do
    state=$(nmcli -t -f GENERAL.STATE device show "$INTERFACE" 2>/dev/null | sed 's/[^0-9]//g')
    if [[ -n "$state" && "$state" -ge 70 ]]; then
      return 0
    fi
    log "⏳ Waiting for NM connection... ($i/$tries)"
    sleep 2
  done
  return 1
}

wait_for_iface_present() {
  local tries=${1:-10}
  local i
  for i in $(seq 1 "$tries"); do
    if ip link show "$INTERFACE" &>/dev/null; then
      return 0
    fi
    sleep 1
  done
  return 1
}

wait_for_iface_up() {
  local tries=${1:-5}
  local i state
  for i in $(seq 1 "$tries"); do
    sudo ip link set "$INTERFACE" up || true
    sleep 1
    state=$(cat "/sys/class/net/$INTERFACE/operstate" 2>/dev/null || echo "")
    if [[ "$state" == "up" ]]; then
      return 0
    fi
  done
  return 1
}

echo "🔄 Auto Wi-Fi/AP mode switching script starting..."

AP_SSID="$1"
echo "[DEBUG] 04_auto_wifi_or_ap.sh received: '$1'"
echo "[DEBUG] Assigned SSID: '$AP_SSID'"

# Get AutoFormBot root path dynamically
AUTOFORM_PATH="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"

# Wi-Fi interface
INTERFACE="wlan0"
# AP_SSID="$AP_SSID"
AP_IP="192.168.4.1"
CHANNEL="6"

# Wait until wlan0 interface appears
log "⏳ Waiting for $INTERFACE to become available..."
if wait_for_iface_present 10; then
  log "✅ $INTERFACE is available."
else
  log "❌ $INTERFACE not found. Exiting."
  exit 1
fi


# Saved Wi-Fi connection profiles (names)
KNOWN_SSIDS=$(nmcli -t -f NAME,TYPE connection show | awk -F: '$2=="802-11-wireless" && $1!="" {print $1}')

enable_ap_mode() {
  echo "📶 Switching to AP mode..."
  bash "$AUTOFORM_PATH/scripts/nmservice/02_setup_ap_mode.sh" "$AP_SSID"
}

enable_sta_mode() {
  echo "📡 Switching to STA mode..."
  bash "$AUTOFORM_PATH/scripts/nmservice/03_setup_sta_mode.sh"
}

# Call enable_ap_mode or enable_sta_mode based on your decision logic
# enable_ap_mode
# enable_sta_mode

# If we are currently in AP mode (hostapd running or iface type is AP), we must not leave it half-configured.
# We'll stop AP services for scanning, then either connect STA or re-enable AP.
WAS_AP=0
CUR_TYPE=$(iface_type)
if is_hostapd_active || [[ "$CUR_TYPE" == "AP" || "$CUR_TYPE" == "__ap" ]]; then
  WAS_AP=1
  log "ℹ️ Detected AP mode (hostapd active or iface type AP). Temporarily stopping AP for scanning..."
  stop_ap_services_if_any
  # Remove leftover AP IP before scanning to avoid dual-IP confusion
  cleanup_ap_ip
fi

log "🔁 Ensuring $INTERFACE is in managed mode for scanning..."
ensure_managed_for_scan

# Bring interface up
log "⏳ Waiting for $INTERFACE to be UP..."
if wait_for_iface_up 5; then
  log "✅ $INTERFACE is UP."
else
  log "⚠️ $INTERFACE did not reach operstate=up (continuing anyway)."
fi

# Scan for known SSIDs
echo "🔍 Scanning for Wi-Fi networks..."
sudo nmcli radio wifi on
sleep 2
sudo nmcli dev wifi rescan || true
sleep 3

SSID_FOUND=""
# Build a newline-separated list of visible SSIDs
VISIBLE_SSIDS=$(sudo nmcli -t -f SSID dev wifi | sed '/^$/d' | sort -u)
while IFS= read -r SSID; do
  [[ -z "$SSID" ]] && continue
  if echo "$VISIBLE_SSIDS" | grep -Fxq "$SSID"; then
    SSID_FOUND="$SSID"
    break
  fi
done <<< "$KNOWN_SSIDS"

if [[ -n "$SSID_FOUND" ]]; then
  SSID_ACTIVE=$(nmcli -t -f active,ssid dev wifi | grep "^yes" | cut -d: -f2)
  if [[ "$SSID_ACTIVE" == "$SSID_FOUND" ]]; then
    log "✅ Already connected to '$SSID_FOUND'. Skipping reconnection."
    exit 0
  fi

  log "✅ Known SSID '$SSID_FOUND' found. Connecting to it..."
  enable_sta_mode
  # After switching to STA mode, ensure NM is really managing wlan0 before bringing the connection up
  sudo systemctl restart NetworkManager || true
  sleep 1
  sudo nmcli dev set "$INTERFACE" managed yes || true
  log "🔗 Bringing up connection on $INTERFACE for SSID '$SSID_FOUND'..."
  sleep 2
  # Make sure AP IP is not left behind when moving to STA
  cleanup_ap_ip
  sudo nmcli con up "$SSID_FOUND" ifname "$INTERFACE" || true
  # If NM autoconnect is enabled, con up may not block; wait for connected state

  if wait_for_nm_connected 10; then
    log "✅ Connection established to '$SSID_FOUND'."
  else
    log "❌ Connection to '$SSID_FOUND' failed. Falling back to AP mode..."
    enable_ap_mode
  fi
else
  log "🚫 No known SSID found. Starting AP mode..."
  enable_ap_mode

  # If we were in AP before scanning and still no STA was established, make sure AP is actually enabled.
  if [[ "$WAS_AP" -eq 1 && -z "$SSID_FOUND" ]]; then
    log "↩️ Restoring AP mode after scan (no known SSID found)."
    enable_ap_mode
  fi
fi
