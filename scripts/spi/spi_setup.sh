sudo usermod -aG gpio afb

if [ -d ".afbvenv" ]; then
    echo "🔁 Virtual environment '.afbvenv' already exists. Activating..."
else
    echo "🆕 Creating virtual environment '.afbvenv'..."
    python -m venv ~/.afbvenv
fi

pip3 install spidev lgpio

deactivate