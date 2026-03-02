# Folosim Python 3.11 cu Debian slim
FROM python:3.11-slim-bookworm

# Setăm variabilele de mediu
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive

# Instalăm dependențele sistem pentru Chrome și Nodriver
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    gnupg \
    xvfb \
    libnss3 \
    libnspr4 \
    libdbus-1-3 \
    libatk1.0-0 \
    libatk-bridge2.0-0 \
    libcups2 \
    libdrm2 \
    libxkbcommon0 \
    libxcomposite1 \
    libxdamage1 \
    libxfixes3 \
    libxrandr2 \
    libgbm1 \
    libpango-1.0-0 \
    libcairo2 \
    libasound2 \
    libatspi2.0-0 \
    libwayland-client0 \
    fonts-liberation \
    libappindicator3-1 \
    xdg-utils \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Instalăm Google Chrome (pentru Nodriver)
RUN wget -q -O - https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - \
    && echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" >> /etc/apt/sources.list.d/google-chrome.list \
    && apt-get update \
    && apt-get install -y google-chrome-stable \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Creăm directorul aplicației
WORKDIR /app

# Copiem fișierul de dependențe
COPY requirements.txt .

# Instalăm dependențele Python (include nodriver)
RUN pip install --no-cache-dir -r requirements.txt

# Copiem restul aplicației
COPY main.py .
COPY test_telegram.py .
COPY start.sh .

# Creăm directoarele necesare
RUN mkdir -p /app/profiles /app/debug_output

# Setăm permisiuni
RUN chmod -R 755 /app && chmod +x /app/start.sh

# Configurăm Chrome pentru a rula în container (Nodriver va folosi aceste setări)
ENV CHROME_BIN=/usr/bin/google-chrome \
    DISPLAY=:99

# Volum pentru configurație și profile
VOLUME ["/app/profiles", "/app/config", "/app/debug_output"]

# Comanda implicită - rulează prin start.sh cu Xvfb
CMD ["/app/start.sh"]
