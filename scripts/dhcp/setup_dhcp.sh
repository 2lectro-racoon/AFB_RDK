#!/bin/bash

echo "[1] ifupdown 설정 비활성화..."

# interfaces 파일 백업
sudo cp /etc/network/interfaces /etc/network/interfaces.bak 2>/dev/null

# eth0 관련 설정 주석 처리
sudo sed -i 's/^auto eth0/#auto eth0/g' /etc/network/interfaces 2>/dev/null
sudo sed -i 's/^iface eth0/#iface eth0/g' /etc/network/interfaces 2>/dev/null
# eth0 블록 안에서만 address/netmask/gateway 주석 처리
sudo sed -i '/iface eth0/,/auto/{s/^\s*address/#address/g}' /etc/network/interfaces 2>/dev/null
sudo sed -i '/iface eth0/,/auto/{s/^\s*netmask/#netmask/g}' /etc/network/interfaces 2>/dev/null
sudo sed -i '/iface eth0/,/auto/{s/^\s*gateway/#gateway/g}' /etc/network/interfaces 2>/dev/null

echo "[2] NetworkManager 설정 변경..."

# NetworkManager.conf 수정
sudo sed -i 's/managed=false/managed=true/g' /etc/NetworkManager/NetworkManager.conf

echo "[3] NetworkManager 재시작..."

sudo systemctl restart NetworkManager

sleep 3

echo "[4] DHCP 설정 적용..."

sudo nmcli con mod eth0 ipv4.method auto
sudo nmcli con up eth0

echo "[5] 현재 네트워크 상태:"
nmcli device
ip a | grep eth0

echo ""
echo "✅ 완료! 이제 재부팅하면 DHCP 유지됨"
echo "👉 sudo reboot"