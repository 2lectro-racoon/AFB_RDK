if [ -d ".afbvenv" ]; then
    echo "🔁 Virtual environment '.afbvenv' already exists. Activating..."
else
    echo "🆕 Creating virtual environment '.afbvenv'..."
    python -m venv ~/.afbvenv
fi

sudo apt install -y python3-lgpio
pip3 install spidev

deactivate