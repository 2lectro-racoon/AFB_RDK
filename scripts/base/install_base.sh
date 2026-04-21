#!/bin/bash

set -e

LOG_TAG="[install_base]"
SUNRISE_LIST="/etc/apt/sources.list.d/sunrise.list"
SUNRISE_KEY="/usr/share/keyrings/sunrise.gpg"
ROS2_LIST="/etc/apt/sources.list.d/ros2.list"

update_sunrise_repo() {
    if [ -f "$SUNRISE_LIST" ]; then
        echo "$LOG_TAG sunrise apt 소스를 공식 문서 기준으로 점검/수정 중..."

        sudo cp "$SUNRISE_LIST" "$SUNRISE_LIST.bak.$(date +%Y%m%d_%H%M%S)"
        sudo sed -i 's|archive\.sunrisepi\.tech|archive.d-robotics.cc|g' "$SUNRISE_LIST"
        sudo sed -i 's|sunrise\.horizon\.cc|archive.d-robotics.cc|g' "$SUNRISE_LIST"

        echo "$LOG_TAG sunrise GPG 키 갱신 중..."
        sudo wget -O "$SUNRISE_KEY" http://archive.d-robotics.cc/keys/sunrise.gpg
    else
        echo "$LOG_TAG $SUNRISE_LIST 파일이 없어 sunrise 소스 수정은 건너뜁니다."
    fi
}

warn_ros2_repo() {
    if [ -f "$ROS2_LIST" ]; then
        echo "$LOG_TAG 경고: $ROS2_LIST 가 존재합니다."
        echo "$LOG_TAG 현재 apt update 실패 원인이 ROS2 저장소일 수 있습니다."
        echo "$LOG_TAG ros2.list 내용 확인 후 필요 시 임시 비활성화하세요:"
        echo "  sudo mv $ROS2_LIST ${ROS2_LIST}.disabled"
    fi
}

update_sunrise_repo
warn_ros2_repo

echo "$LOG_TAG apt 패키지 목록 갱신 중..."
sudo apt update

echo "$LOG_TAG 최소 패키지 설치 중..."
sudo apt install -y \
    git \
    python3-pip \
    python3-venv \
    rsync \
    direnv \
    net-tools \
    i2c-tools

echo "$LOG_TAG 설치 완료"