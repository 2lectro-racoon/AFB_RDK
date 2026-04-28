

#!/bin/bash
set -e

LOG_TAG="[opencv_install]"
VENV_PATH="$HOME/.afbvenv"

if [ ! -d "$VENV_PATH" ]; then
    echo "$LOG_TAG venv not found: $VENV_PATH"
    exit 1
fi

echo "$LOG_TAG activating venv..."
source "$VENV_PATH/bin/activate"

echo "$LOG_TAG installing dependencies..."
pip install --upgrade pip
pip install numpy==1.24.4

echo "$LOG_TAG installing OpenCV 4.10.0..."
pip install opencv-python==4.10.0.84

echo "$LOG_TAG verifying installation..."
python3 - <<'PY'
import cv2
print("OpenCV version:", cv2.__version__)
PY

echo "$LOG_TAG done."