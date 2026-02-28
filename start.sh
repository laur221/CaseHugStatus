#!/bin/bash

# Start Xvfb (Virtual Display) on display :99
echo "🖥️  Pornesc Xvfb (Virtual Display)..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
export DISPLAY=:99

# Așteaptă ca Xvfb să pornească
sleep 2

echo "✅ Xvfb pornit pe DISPLAY=:99"

# Rulează botul Python
echo "🤖 Pornesc CasehugBot..."
python main.py

# Cleanup la închidere
kill $XVFB_PID 2>/dev/null || true
