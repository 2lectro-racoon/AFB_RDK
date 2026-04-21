#!/bin/bash

echo "📦 Installing Flask and Python virtual environment..."

# 1. Create and activate virtual environment
if [ -d ".afbvenv" ]; then
    echo "🔁 Virtual environment '.afbvenv' already exists. Activating..."
else
    echo "🆕 Creating virtual environment '.afbvenv'..."
    python3 -m venv ~/.afbvenv
fi
source ~/.afbvenv/bin/activate

# 2. Install Flask
pip install --upgrade pip
pip install flask

echo "✅ Flask installation complete!"
echo "🔄 Virtual environment '.afbvenv' is ready."

deactivate
echo "👋 Virtual environment deactivated."