#!/bin/bash

echo "📦 Setting up picamera2 and Python virtual environment..."

# 1. Create and activate virtual environment
if [ -d ".afbvenv" ]; then
    echo "🔁 Virtual environment '.afbvenv' already exists. Activating..."
else
    echo "🆕 Creating virtual environment '.afbvenv'..."
    python3.11 -m venv ~/.afbvenv
fi
source ~/.afbvenv/bin/activate

# 2. Upgrade pip and install picamera2
pip install --upgrade pip

# Ensure system dependencies are available for picamera2
sudo apt update
sudo apt install -y python3-picamera2 libcamera-apps libatlas-base-dev

echo "✅ picamera2 setup complete!"
echo "🔄 Virtual environment '.afbvenv' is ready with picamera2 and OpenCV installed."

deactivate
echo "👋 Virtual environment deactivated."
