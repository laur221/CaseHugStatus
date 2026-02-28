#!/bin/bash
# Script pentru salvarea cookie-urilor DIRECT din Docker cu același browser
# Astfel Cloudflare nu va detecta diferențe de fingerprint

echo "🍪 Salvare Cookie-uri din Docker (pentru bypass Cloudflare perfect)"
echo "════════════════════════════════════════════════════════════════════"
echo ""
echo "IMPORTANT: Acest script rulează browser-ul ÎN DOCKER cu Xvfb"
echo "           Cookie-urile vor avea EXACT același fingerprint ca botul!"
echo ""
echo "Pornesc Xvfb..."
Xvfb :99 -screen 0 1920x1080x24 -ac +extension GLX +render -noreset &
XVFB_PID=$!
export DISPLAY=:99
sleep 2

echo "✅ Xvfb pornit"
echo ""
echo "Pornesc Python script pentru salvare cookie-uri..."
python3 /app/save_cookies_docker.py

# Cleanup
kill $XVFB_PID 2>/dev/null || true
