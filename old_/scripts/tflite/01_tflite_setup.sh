#!/bin/bash

echo "📦 Installing tflite and Python virtual environment..."

# 1. Create and activate virtual environment
if [ -d ".afbvenv" ]; then
    echo "🔁 Virtual environment '.afbvenv' already exists. Activating..."
else
    echo "🆕 Creating virtual environment '.afbvenv'..."
    python -m venv ~/.afbvenv
fi
source ~/.afbvenv/bin/activate
# 2. Install TensorFlow 2.20.0
pip install --upgrade pip
# TensorFlow 2.20.0 (Python 3.13 / aarch64 supported)
pip install tensorflow==2.20.0

# --- Critical fixes ---
# flatbuffers: avoid legacy 201810xxxx version that breaks on Python 3.13 (uses removed 'imp' module)
pip uninstall -y flatbuffers
pip install --no-cache-dir "flatbuffers<1000,>=23.5.26"

# Verify TensorFlow and flatbuffers
python - << 'EOF'
import importlib.metadata as m
import tensorflow as tf
print("TensorFlow:", tf.__version__)
print("flatbuffers:", m.version("flatbuffers"))
EOF

echo "✅ TensorFlow install complete!"
echo "🔄 Virtual environment '.afbvenv' is ready."

deactivate
echo "👋 Virtual environment deactivated."