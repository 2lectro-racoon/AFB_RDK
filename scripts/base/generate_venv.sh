

#!/bin/bash

set -e

LOG_TAG="[generate_venv]"
VENV_PATH="$HOME/.afbvenv"
WORK_DIR="$HOME/afb_home"
ENVRC_PATH="$WORK_DIR/.envrc"
BASHRC_PATH="$HOME/.bashrc"
DIRENV_HOOK='eval "$(direnv hook bash)"'

ensure_direnv_hook() {
    if grep -Fq "$DIRENV_HOOK" "$BASHRC_PATH" 2>/dev/null; then
        echo "$LOG_TAG .bashrc 에 direnv hook 이 이미 설정되어 있습니다."
    else
        echo "$LOG_TAG .bashrc 에 direnv hook 을 추가합니다."
        printf '\n# direnv\n%s\n' "$DIRENV_HOOK" >> "$BASHRC_PATH"
    fi
}

echo "$LOG_TAG 작업 폴더 생성 중..."
mkdir -p "$WORK_DIR"

echo "$LOG_TAG 가상환경 생성/확인 중..."
if [ -d "$VENV_PATH" ]; then
    echo "$LOG_TAG 가상환경이 이미 존재합니다: $VENV_PATH"
else
    python3 -m venv "$VENV_PATH"
    echo "$LOG_TAG 가상환경 생성 완료: $VENV_PATH"
fi

ensure_direnv_hook

echo "$LOG_TAG .envrc 작성 중..."
cat > "$ENVRC_PATH" <<EOF
export VIRTUAL_ENV="$VENV_PATH"
PATH_add "\$VIRTUAL_ENV/bin"
EOF

echo "$LOG_TAG direnv 허용 적용 중..."
cd "$WORK_DIR"
direnv allow

echo
cat <<EOF
$LOG_TAG 완료
- 가상환경: $VENV_PATH
- 작업 폴더: $WORK_DIR
- .envrc: $ENVRC_PATH

다음부터는 아래처럼 사용하면 됩니다.
  cd ~/afb_home

처음 한 번은 현재 셸에 bashrc 를 다시 반영하세요.
  source ~/.bashrc
EOF