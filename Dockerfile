# Folosim Python 3.11 cu Debian slim
FROM python:3.11-slim-bookworm

# Setăm variabilele de mediu
ENV PYTHONUNBUFFERED=1 \
    DEBIAN_FRONTEND=noninteractive \
    CHROME_BIN=/usr/bin/chromium \
    CHROMEDRIVER_BIN=/usr/bin/chromedriver

# Instalăm dependențele sistem pentru Chrome și Selenium
RUN apt-get update && apt-get install -y \
    chromium \
    chromium-driver \
    wget \
    curl \
    unzip \
    xvfb \
    libglib2.0-0 \
    libnss3 \
    libgconf-2-4 \
    libfontconfig1 \
    libxrender1 \
    libxi6 \
    libxtst6 \
    libxss1 \
    libappindicator3-1 \
    libasound2 \
    libatk-bridge2.0-0 \
    libgtk-3-0 \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Creăm directorul aplicației
WORKDIR /app

# Copiem fișierul de dependențe
COPY requirements.txt .

# Instalăm dependențele Python
RUN pip install --no-cache-dir -r requirements.txt

# Copiem restul aplicației
COPY main.py .
COPY test_telegram.py .

# Creăm directoarele necesare
RUN mkdir -p /app/profiles /app/debug_output

# Setăm permisiuni
RUN chmod -R 755 /app

# Configurăm Chromium pentru a rula în container
ENV CHROME_FLAGS="--no-sandbox --disable-dev-shm-usage --disable-gpu --headless=new"

# Volum pentru configurație și profile
VOLUME ["/app/profiles", "/app/config", "/app/debug_output"]

# Comanda implicită
CMD ["python", "-u", "main.py"]
