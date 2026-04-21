#!/bin/bash
set -e

echo "📦 Setting up lgpio, SPI (spidev), and Python virtual environment..."

# Always use a single shared venv under the user's HOME so services and shells match
VENV_DIR="$HOME/.afbvenv"
VENV_PYTHON="$VENV_DIR/bin/python3"

# -----------------------------
# 0) System packages
# -----------------------------

sudo apt update

# Build deps for pip-installing lgpio (SWIG + compiler + Python headers)
sudo apt install -y --no-install-recommends \
  swig \
  python3-dev \
  build-essential

# System-level SPI bindings (useful as a fallback)
sudo apt install -y --no-install-recommends python3-spidev

# Ensure SPI is enabled is handled elsewhere (raspi-config). We only install deps here.

# -----------------------------
# 1) Create and activate venv
# -----------------------------

if [ -d "$VENV_DIR" ]; then
  echo "🔁 Virtual environment '$VENV_DIR' already exists. Activating..."
else
  echo "🆕 Creating virtual environment '$VENV_DIR'..."
  python3 -m venv "$VENV_DIR"
fi

# shellcheck disable=SC1090
source "$VENV_DIR/bin/activate"

pip install --upgrade pip

# -----------------------------
# 2) lgpio (Blinka backend dependency)
# -----------------------------

# Some distros ship only the runtime library: liblgpio.so.1
# But building the Python wheel needs the linker name: liblgpio.so
# If liblgpio.so is missing but liblgpio.so.1 exists, create a symlink.
LIBDIR="/usr/lib/aarch64-linux-gnu"
if [ -f "$LIBDIR/liblgpio.so.1" ] && [ ! -e "$LIBDIR/liblgpio.so" ]; then
  echo "🔧 Creating symlink for lgpio: $LIBDIR/liblgpio.so -> liblgpio.so.1"
  sudo ln -sf "$LIBDIR/liblgpio.so.1" "$LIBDIR/liblgpio.so"
  sudo ldconfig
fi

# Install lgpio into the venv (needed by Adafruit Blinka on many RPi OS builds)
# Use --no-cache-dir to avoid stale build artifacts.
pip install --no-cache-dir lgpio

# -----------------------------
# 3) SPI (spidev)
# -----------------------------

pip install --no-cache-dir spidev

echo "✅ lgpio + spidev setup complete in $VENV_DIR!"

deactivate
echo "👋 Virtual environment deactivated."
