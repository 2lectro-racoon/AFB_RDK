#!/bin/bash

set -e

if [ "$#" -ne 1 ]; then
    echo "사용법: $0 <새이름>"
    echo "예시: $0 afb003"
    exit 1
fi

NEW_NAME="$1"

# 영문 소문자, 숫자, -, _ 만 허용
if [[ ! "$NEW_NAME" =~ ^[a-z_][a-z0-9_-]*$ ]]; then
    echo "오류: 이름은 영문 소문자, 숫자, -, _ 만 사용할 수 있습니다."
    exit 1
fi

if [ "$EUID" -ne 0 ]; then
    echo "이 스크립트는 sudo로 실행해야 합니다."
    echo "예시: sudo $0 $NEW_NAME"
    exit 1
fi

CURRENT_USER="${SUDO_USER:-$(logname 2>/dev/null || true)}"
if [ -z "$CURRENT_USER" ] || [ "$CURRENT_USER" = "root" ]; then
    CURRENT_USER="$(awk -F: '$3 >= 1000 && $1 != "nobody" {print $1; exit}' /etc/passwd)"
fi

CURRENT_HOSTNAME="$(hostnamectl --static 2>/dev/null || hostname)"
TARGET_USER="afb"
TARGET_HOSTNAME="$NEW_NAME"
TARGET_PASSWORD="code1234"

if [ -z "$CURRENT_USER" ]; then
    echo "오류: 현재 일반 사용자 계정을 찾을 수 없습니다."
    exit 1
fi

echo "현재 사용자: $CURRENT_USER"
echo "현재 호스트네임: $CURRENT_HOSTNAME"
echo "변경할 사용자: $TARGET_USER"
echo "변경할 호스트네임: $TARGET_HOSTNAME"
echo

# 1) hostname 변경
if [ "$CURRENT_HOSTNAME" != "$TARGET_HOSTNAME" ]; then
    echo "[1/5] 호스트네임 변경 중..."
    hostnamectl set-hostname "$TARGET_HOSTNAME"

    cp /etc/hosts /etc/hosts.bak.$(date +%Y%m%d_%H%M%S)

    if grep -q '^127\.0\.1\.1' /etc/hosts; then
        sed -i "s/^127\.0\.1\.1.*/127.0.1.1\t$TARGET_HOSTNAME/" /etc/hosts
    else
        printf '\n127.0.1.1\t%s\n' "$TARGET_HOSTNAME" >> /etc/hosts
    fi
else
    echo "[1/5] 호스트네임은 이미 $TARGET_HOSTNAME 입니다."
fi

# 2) 사용자 생성 또는 재사용
if id "$TARGET_USER" >/dev/null 2>&1; then
    echo "[2/5] 사용자 $TARGET_USER 는 이미 존재합니다."
    echo "[2/5] 사용자 $TARGET_USER 비밀번호를 기본값으로 갱신합니다."
    echo "$TARGET_USER:$TARGET_PASSWORD" | chpasswd
    usermod -aG sudo "$TARGET_USER"
else
    echo "[2/5] 사용자 $TARGET_USER 생성 중..."
    useradd -m -s /bin/bash "$TARGET_USER"
    echo "$TARGET_USER:$TARGET_PASSWORD" | chpasswd
    usermod -aG sudo "$TARGET_USER"
    echo "사용자 $TARGET_USER 가 생성되었습니다."
fi

# 3) 기존 홈 디렉토리 내용 복사
if [ "$CURRENT_USER" != "$TARGET_USER" ]; then
    SRC_HOME="/home/$CURRENT_USER"
    DST_HOME="/home/$TARGET_USER"

    if [ -d "$SRC_HOME" ] && [ -d "$DST_HOME" ]; then
        echo "[3/5] /home/$CURRENT_USER 내용을 /home/$TARGET_USER 로 복사 중..."
        mkdir -p "$DST_HOME"
        rsync -a \
            --exclude='.cache' \
            --exclude='.local/share/Trash' \
            --exclude='.gvfs' \
            "$SRC_HOME"/ "$DST_HOME"/
        chown -R "$TARGET_USER:$TARGET_USER" "$DST_HOME"
    else
        echo "[3/5] 홈 디렉토리 복사를 건너뜁니다."
    fi
else
    echo "[3/5] 현재 사용자와 대상 사용자가 같아서 홈 복사는 건너뜁니다."
fi

# 4) SSH authorized_keys 복구 확인
if [ -f "/home/$CURRENT_USER/.ssh/authorized_keys" ] && [ "$CURRENT_USER" != "$TARGET_USER" ]; then
    echo "[4/5] SSH 키 권한 정리 중..."
    mkdir -p "/home/$TARGET_USER/.ssh"
    cp "/home/$CURRENT_USER/.ssh/authorized_keys" "/home/$TARGET_USER/.ssh/authorized_keys"
    chown -R "$TARGET_USER:$TARGET_USER" "/home/$TARGET_USER/.ssh"
    chmod 700 "/home/$TARGET_USER/.ssh"
    chmod 600 "/home/$TARGET_USER/.ssh/authorized_keys"
else
    echo "[4/5] SSH 키 복사는 건너뜁니다."
fi

# 5) 안내
cat <<EOF
[5/5] 완료

변경 결과
- 새 호스트네임: $TARGET_HOSTNAME
- 새 사용자: $TARGET_USER

다음 작업을 권장합니다.
1. 기본 사용자 정보
   사용자명: $TARGET_USER
   비밀번호: $TARGET_PASSWORD

2. SSH 재접속 테스트
   ssh $TARGET_USER@<현재 IP>

3. 정상 접속 확인 후, 기존 사용자 삭제 여부 결정
   sudo deluser --remove-home $CURRENT_USER

4. 호스트네임 완전 반영을 위해 재부팅
   sudo reboot
EOF