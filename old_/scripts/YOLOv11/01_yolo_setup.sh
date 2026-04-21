#!/bin/bash

echo "📦 Installing Ultralytics YOLOv11 and Python virtual environment..."

# 1. Create and activate virtual environment
if [ -d ".afbvenv" ]; then
    echo "🔁 Virtual environment '.afbvenv' already exists. Activating..."
else
    echo "🆕 Creating virtual environment '.afbvenv'..."
    python3 -m venv ~/.afbvenv
fi
source ~/.afbvenv/bin/activate
# 2. Install ultralytics Yolov11
pip install --upgrade pip

pip install --pre torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/nightly/cpu

# # Detect Raspberry Pi model and install torch first
# MODEL=$(grep "Model" /proc/cpuinfo 2>/dev/null)

# echo "🔍 Detected device: $MODEL"

# if [[ $MODEL == *"Raspberry Pi 4"* ]]; then
#     echo "🟡 Raspberry Pi 4 detected → installing PyTorch nightly (better CPU compatibility)"
#     pip install --pre torch torchvision torchaudio \
#         --index-url https://download.pytorch.org/whl/nightly/cpu

# elif [[ $MODEL == *"Raspberry Pi 5"* ]]; then
#     echo "🟢 Raspberry Pi 5 detected → installing stable PyTorch"
#     pip install torch torchvision torchaudio

# else
#     echo "⚠️ Unknown device → installing default PyTorch"
#     pip install torch torchvision torchaudio
# fi

# Install other dependencies
pip install polars
pip install opencv-python --no-deps
pip install matplotlib pandas pillow psutil py-cpuinfo pyyaml scipy seaborn tqdm ultralytics-thop

# Install Ultralytics last
pip install ultralytics --no-deps

echo "✅ Ultralytics YOLOv11 install complete!"
echo "🔄 Virtual environment '.afbvenv' is ready."

deactivate
echo "👋 Virtual environment deactivated."