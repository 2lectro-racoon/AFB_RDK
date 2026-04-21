#!/bin/bash

echo "📡 Checking AP Mode Status..."

echo -e "\n[1] hostapd status:"
systemctl is-active --quiet hostapd && echo "✅ hostapd is running" || echo "❌ hostapd is NOT running"

echo -e "\n[2] dnsmasq status:"
systemctl is-active --quiet dnsmasq && echo "✅ dnsmasq is running" || echo "❌ dnsmasq is NOT running"

echo -e "\n[3] wlan0 IP address:"
ip addr show wlan0 | grep "inet "

echo -e "\n[4] wlan0 interface mode:"
iw dev wlan0 info | grep type

echo -e "\n[5] SSID visibility setting (hostapd.conf):"
grep -i -E "ssid=|ignore_broadcast_ssid=" /etc/hostapd/hostapd.conf

echo -e "\n[6] wlan0 management by NetworkManager:"
nmcli dev status | grep wlan0

echo -e "\n[7] Check current channel and country:"
iw dev wlan0 info | grep channel
iw reg get | grep country