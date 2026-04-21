#!/bin/bash

echo "📦 Installing OpenCV (opencv-contrib-python 4.13.0.90) and Python virtual environment..."

# 0. Install OpenCV system dependencies
echo "🛠 Installing OpenCV system dependencies..."
sudo apt update
sudo apt install -y \
    libopenblas-dev \
    libblas-dev \
    liblapack-dev \
    libjpeg-dev \
    libpng-dev \
    libtiff-dev \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev \
    libxvidcore-dev \
    libx264-dev \
    libgtk-3-dev \
    libcanberra-gtk*

# 1. Create and activate virtual environment
if [ -d ".afbvenv" ]; then
    echo "🔁 Virtual environment '.afbvenv' already exists. Activating..."
else
    echo "🆕 Creating virtual environment '.afbvenv'..."
    python3 -m venv ~/.afbvenv
fi
source ~/.afbvenv/bin/activate

# 2. Install opencv-contrib-python 4.13.0.90 (NumPy 2.x compatible)
pip install --upgrade pip
pip install "numpy==2.4.1"
pip install "opencv-contrib-python==4.13.0.90"

# Verify OpenCV and NumPy
python - << 'EOF'
import numpy as np
import cv2
print("NumPy:", np.__version__)
print("OpenCV:", cv2.__version__)
EOF

echo "✅ opencv install complete!"
echo "🔄 Virtual environment '.afbvenv' is ready."

deactivate
echo "👋 Virtual environment deactivated."