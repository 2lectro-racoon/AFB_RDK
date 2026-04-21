#!/bin/bash
# 03_setup_sta_mode.sh - Setup script for STA (client) mode
# Notes:
# - In AP mode we mark wlan0 as unmanaged for NetworkManager via 99-unmanaged-wlan0.conf.
# - Removing that file often requires restarting NetworkManager to take effect.

set -e

echo "📶 Setting up Station (Client) Mode..."

INTERFACE="wlan0"
UNMANAGED_CONF="/etc/NetworkManager/conf.d/99-unmanaged-wlan0.conf"
AP_IP_CIDR="192.168.4.1/24"

# Stop AP-related services if running
echo "🛑 Stopping AP services..."
sudo systemctl stop hostapd 2>/dev/null || true
sudo systemctl stop dnsmasq 2>/dev/null || true

# Remove leftover AP IP if present (do NOT flush all addresses blindly)
echo "🔄 Cleaning up AP IP on $INTERFACE..."
sudo ip addr del "$AP_IP_CIDR" dev "$INTERFACE" 2>/dev/null || true

# Ensure NetworkManager will manage wlan0 again
if [ -f "$UNMANAGED_CONF" ]; then
  echo "🧹 Removing unmanaged config for $INTERFACE..."
  sudo rm -f "$UNMANAGED_CONF"
else
  echo "ℹ️ No unmanaged config found for $INTERFACE."
fi

# Restart NetworkManager to reliably apply unmanaged config removal
echo "🔁 Restarting NetworkManager..."
sudo systemctl restart NetworkManager
sleep 1

# Ensure NM runtime flag is enabled
echo "🔧 Enabling NM management for $INTERFACE..."
sudo nmcli dev set "$INTERFACE" managed yes || true

# Ensure wlan0 is in managed mode at kernel level
current_mode=$(iw dev "$INTERFACE" info 2>/dev/null | awk '/type/ {print $2; exit}')
if [ "$current_mode" != "managed" ]; then
  echo "🔧 Converting $INTERFACE to managed mode..."
  sudo ip link set "$INTERFACE" down || true
  sudo iw dev "$INTERFACE" set type managed || true
  sudo ip link set "$INTERFACE" up || true
else
  echo "ℹ️ $INTERFACE is already in managed mode."
fi

# Make sure Wi-Fi radio is on
sudo nmcli radio wifi on || true

echo "✅ STA mode setup complete."
echo "ℹ️ To connect: sudo nmcli con up \"<SSID_PROFILE_NAME>\" ifname $INTERFACE"