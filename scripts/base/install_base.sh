#!/bin/bash

set -e

LOG_TAG="[install_base]"
SUNRISE_LIST="/etc/apt/sources.list.d/sunrise.list"
ROS2_LIST="/etc/apt/sources.list.d/ros2.list"
APT_BACKUP_DIR="/etc/apt/backup_sources"
TIMESTAMP="$(date +%Y%m%d_%H%M%S)"

backup_apt_source() {
    local src_file="$1"

    if [ -f "$src_file" ]; then
        sudo mkdir -p "$APT_BACKUP_DIR"
        sudo cp "$src_file" "$APT_BACKUP_DIR/$(basename "$src_file").bak.$TIMESTAMP"
    fi
}

update_sunrise_repo() {
    if [ -f "$SUNRISE_LIST" ]; then
        echo "$LOG_TAG sunrise apt 소스를 공식 문서 기준으로 점검/수정 중..."

        backup_apt_source "$SUNRISE_LIST"
        sudo sed -i 's|archive\.sunrisepi\.tech|archive.d-robotics.cc|g' "$SUNRISE_LIST"
        sudo sed -i 's|sunrise\.horizon\.cc|archive.d-robotics.cc|g' "$SUNRISE_LIST"

        echo "$LOG_TAG sunrise GPG 키 갱신 중..."
        sudo wget -O "$SUNRISE_KEY" http://archive.d-robotics.cc/keys/sunrise.gpg
    else
        echo "$LOG_TAG $SUNRISE_LIST 파일이 없어 sunrise 소스 수정은 건너뜁니다."
    fi
}

fix_ros2_repo() {
    if [ -f "$ROS2_LIST" ]; then
        echo "$LOG_TAG ROS2 저장소를 공식 저장소로 교체 중..."

        backup_apt_source "$ROS2_LIST"

        # 기존 미러 제거 후 공식 ROS2 repo로 교체
        UBUNTU_CODENAME=$(lsb_release -cs 2>/dev/null || echo "jammy")
        ARCH=$(dpkg --print-architecture)

        echo "$LOG_TAG ROS2 GPG 키 갱신 중..."
        sudo curl -sSL https://raw.githubusercontent.com/ros/rosdistro/master/ros.key \
            -o /usr/share/keyrings/ros-archive-keyring.gpg

        echo "$LOG_TAG ROS2 공식 저장소 등록 중..."
        echo "deb [arch=$ARCH signed-by=/usr/share/keyrings/ros-archive-keyring.gpg] http://packages.ros.org/ros2/ubuntu $UBUNTU_CODENAME main" \
            | sudo tee "$ROS2_LIST" > /dev/null
    else
        echo "$LOG_TAG ROS2 저장소가 없어 건너뜁니다."
    fi
}

# 예전 버전 스크립트가 /etc/apt/sources.list.d 에 남긴 백업 파일 정리
if ls /etc/apt/sources.list.d/*.bak.* >/dev/null 2>&1; then
    sudo mkdir -p "$APT_BACKUP_DIR"
    sudo mv /etc/apt/sources.list.d/*.bak.* "$APT_BACKUP_DIR"/
fi

update_sunrise_repo
fix_ros2_repo

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