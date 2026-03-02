#!/bin/bash

echo "🌐 Pornesc Windscribe VPN..."

# Start Windscribe service
windscribe start

# Așteaptă ca serviciul să pornească
sleep 3

# Login cu credentials (folosind variabile environment)
echo "🔐 Login Windscribe cu user: $WINDSCRIBE_USERNAME..."
echo -e "$WINDSCRIBE_USERNAME\n$WINDSCRIBE_PASSWORD" | windscribe login

# Verifică dacă login a reușit
if windscribe account > /dev/null 2>&1; then
    echo "✅ Login reușit!"
else
    echo "❌ Login eșuat! Verifică credentials."
    exit 1
fi

# Conectare la locație (France sau USA)
echo "🇫🇷 Conectez la France..."
windscribe connect FR

# Așteaptă conectare
sleep 5

# Verifică conexiunea
echo "✅ Verificare IP și locație:"
curl -s https://api.ipify.org
echo ""
windscribe status

# Pornește Xvfb
echo "🖥️  Pornesc Xvfb (Virtual Display)..."
Xvfb :99 -screen 0 1920x1080x24 &
export DISPLAY=:99
sleep 2
echo "✅ Xvfb pornit pe DISPLAY=:99"

# Pornește bot-ul
echo "🤖 Pornesc CasehugBot..."
python main.py
