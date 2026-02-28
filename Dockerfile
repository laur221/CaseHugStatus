# Folosim Python 3.11 cu Debian slim
FROM python:3.11-slim-bookworm

# Setăm variabilele de mediu
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    PLAYWRIGHT_BROWSERS_PATH=/ms-playwright

# Instalăm dependențele sistem pentru Playwright
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    xvfb \
    libglib2.0-0 \
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
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Creăm directorul aplicației
WORKDIR /app

# Copiem fișierul de dependențe
COPY requirements.txt .

# Instalăm dependențele Python
RUN pip install --no-cache-dir -r requirements.txt

# Instalăm Playwright browsers (Chromium)
RUN playwright install chromium
RUN playwright install-deps chromium

# Copiem restul aplicației
COPY main.py .
COPY test_telegram.py .
COPY start.sh .

# Creăm directoarele necesare
RUN mkdir -p /app/profiles /app/debug_output

# Setăm permisiuni
RUN chmod -R 755 /app && chmod +x /app/start.sh

# Configurăm Chromium pentru a rula în container
ENV CHROME_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --headless=new"

# Volum pentru configurație și profile
VOLUME ["/app/profiles", "/app/config", "/app/debug_output"]

# Comanda implicită - rulează prin start.sh cu Xvfb
CMD ["/app/start.sh"]
