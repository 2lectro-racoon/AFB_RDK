

#!/bin/bash

set -e

LOG_TAG="[install_base]"

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