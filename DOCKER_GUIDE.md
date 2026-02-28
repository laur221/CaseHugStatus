# 🐳 Docker Setup - Ghid Complet

Acest ghid te ajută să rulezi CasehugBot în Docker pentru testare locală și deployment pe server.

---

## 📋 Cerințe

- **Docker Desktop** (Windows/Mac) sau **Docker Engine** (Linux)
- **Docker Compose** (inclus în Docker Desktop)
- **config.json** configurat corect

---

## 🚀 Quick Start

### 1. Verifică Docker

```bash
docker --version
docker-compose --version
```

Dacă nu ai Docker instalat:
- **Windows/Mac**: [Docker Desktop](https://www.docker.com/products/docker-desktop)
- **Linux**: `curl -fsSL https://get.docker.com | sh`

### 2. Configurează config.json

Asigură-te că `config.json` există și e completat:

```bash
# Windows
copy config.example.json config.json

# Linux/Mac
cp config.example.json config.json
```

Editează `config.json` cu tokenul Telegram și conturile tale.

### 3. Construiește imaginea Docker

```bash
docker-compose build
```

Acest pas:
- Descarcă Python 3.11
- Instalează Chromium și ChromeDriver
- Instalează dependențele Python
- Pregătește mediul

**⏱️ Durată:** 2-5 minute (prima dată)

### 4. Rulează containerul

```bash
docker-compose up
```

Pentru a rula în background (detached):

```bash
docker-compose up -d
```

---

## 📊 Monitorizare

### Vezi logurile live

```bash
docker-compose logs -f
```

### Vezi status container

```bash
docker-compose ps
```

### Oprește containerul

```bash
docker-compose down
```

---

## 🐛 Debugging în Docker

### 1. Accesează Shell-ul containerului

```bash
docker exec -it casehugauto /bin/bash
```

În container poți:
```bash
# Vezi fișierele
ls -la

# Vezi profiles
ls -la profiles/

# Vezi debug output
ls -la debug_output/

# Rulează manual
python main.py
```

### 2. Copiază fișiere debug din container

```bash
# Copiază toate fișierele debug
docker cp casehugauto:/app/debug_output ./debug_output_local

# Copiază un fișier specific
docker cp casehugauto:/app/debug_output/debug_Cont1_homepage.html ./
```

### 3. Verifică profile salvate

```bash
# Liste profile
docker exec casehugauto ls -la /app/profiles

# Vezi conținutul unui profil
docker exec casehugauto du -sh /app/profiles/*
```

---

## 📁 Structura Volumes

Docker montează următoarele directoare:

```
./profiles       → /app/profiles       (Profile Chrome cu login Steam salvat)
./config.json    → /app/config.json    (Configurație - read-only)
./debug_output   → /app/debug_output   (Fișiere HTML și PNG pentru debug)
```

### Ce înseamnă asta?

- **Profiles:** Login-urile Steam sunt salvate pe disk-ul tău local, nu în container
- **Config:** Poți edita `config.json` pe local și repornești containerul
- **Debug:** Fișierele debug sunt accesibile direct pe disk-ul local

---

## ⚙️ Configurare Avansată

### Modifică resurse alocate

Editează `docker-compose.yml`:

```yaml
deploy:
  resources:
    limits:
      cpus: '2.0'      # Max 2 CPU cores
      memory: 2G        # Max 2GB RAM
    reservations:
      cpus: '1.0'      # Min 1 CPU core
      memory: 1G        # Min 1GB RAM
```

### Schimbă timezone

În `docker-compose.yml`:

```yaml
environment:
  - TZ=Europe/Bucharest  # Schimbă cu timezone-ul tău
```

Lista timezone-uri: `timedatectl list-timezones`

### Adaugă variabile de mediu

```yaml
environment:
  - TZ=Europe/Bucharest
  - LOG_LEVEL=DEBUG
  - PYTHONUNBUFFERED=1
```

---

## 🔄 Actualizare și Rebuild

### Când modifici codul

```bash
# Oprește containerul
docker-compose down

# Rebuild imaginea
docker-compose build --no-cache

# Pornește din nou
docker-compose up -d
```

### Când modifici doar config.json

Nu e nevoie de rebuild! Editează `config.json` și repornește:

```bash
docker-compose restart
```

---

## 📅 Automatizare Zilnică

### Folosind Cron (Linux)

Creează script `run_daily.sh`:

```bash
#!/bin/bash
cd /path/to/CasehugAuto
docker-compose up
```

Adaugă în crontab:

```bash
crontab -e
```

Adaugă:
```
0 10 * * * /path/to/CasehugAuto/run_daily.sh >> /var/log/casehugbot.log 2>&1
```

### Folosind Task Scheduler (Windows)

1. Creează `run_daily.bat`:
```batch
@echo off
cd D:\github\CasehugAuto
docker-compose up
```

2. Task Scheduler → Create Basic Task → Daily → 10:00 AM → Start a program → `run_daily.bat`

---

## 🌐 Deployment pe Server

### 1. Copiază fișierele pe server

```bash
# Cu scp
scp -r CasehugAuto/ user@server:/home/user/

# Sau cu rsync
rsync -avz CasehugAuto/ user@server:/home/user/CasehugAuto/
```

### 2. Instalează Docker pe server

```bash
# Ubuntu/Debian
curl -fsSL https://get.docker.com | sh
sudo usermod -aG docker $USER
newgrp docker

# Instalează docker-compose
sudo apt-get install docker-compose-plugin
```

### 3. Configurează și rulează

```bash
cd /home/user/CasehugAuto

# Editează config.json
nano config.json

# Build și run
docker-compose build
docker-compose up -d

# Vezi logs
docker-compose logs -f
```

### 4. Setează restart automat

Docker Compose deja are `restart: unless-stopped` configurat.

Containerul va:
- Porni automat la boot-ul serverului
- Reporni automat dacă crashes
- Nu reporni dacă l-ai oprit manual

---

## 🐛 Troubleshooting Docker

### ❌ Eroare: "Cannot connect to Docker daemon"

**Windows/Mac:**
- Pornește Docker Desktop
- Wait for "Docker is running"

**Linux:**
```bash
sudo systemctl start docker
sudo systemctl enable docker
```

### ❌ Eroare: "Port already in use"

Dacă un alt container folosește același port (improbabil pentru acest bot):

```bash
# Vezi ce containere rulează
docker ps -a

# Oprește containere vechi
docker stop $(docker ps -aq)
docker rm $(docker ps -aq)
```

### ❌ Eroare: "No space left on device"

Docker consumă mult spațiu. Curăță:

```bash
# Șterge containere oprite
docker container prune -f

# Șterge imagini nefolosite
docker image prune -a -f

# Șterge volume orfane
docker volume prune -f

# Șterge tot (ATENȚIE!)
docker system prune -a -f --volumes
```

### ❌ Eroare: "selenium.common.exceptions"

1. Rebuild imaginea:
```bash
docker-compose build --no-cache
```

2. Verifică că Chromium e instalat în container:
```bash
docker exec casehugauto chromium --version
```

### ❌ Browserul nu găsește elemente

1. Extrage fișierele debug:
```bash
docker cp casehugauto:/app/debug_output ./debug_local
```

2. Analizează HTML-urile după [DEBUG_GUIDE.md](DEBUG_GUIDE.md)

---

## 📊 Comparație: Local vs Docker

| Aspect | Local (fără Docker) | Cu Docker |
|--------|---------------------|-----------|
| **Setup inițial** | Instaleză Python, Chrome, deps | `docker-compose up` |
| **Portabilitate** | Dependențe sistem | Izolat, funcționează peste tot |
| **Updates** | Manual update deps | Rebuild imagine |
| **Debugging** | Mai ușor de debugat | Screenshots și HTML-uri |
| **Resurse** | Mai puține | +500MB pentru imagine |
| **Production** | Risc configurație | Consistent, reproducibil |

---

## ✅ Checklist Pre-Deploy pe Server

Înainte de a pune pe server, verifică local în Docker:

- [ ] `docker-compose build` - reușit
- [ ] `docker-compose up` - pornește fără erori
- [ ] Telegram trimite test message
- [ ] Profiles se salvează în `./profiles/`
- [ ] Debug files în `./debug_output/`
- [ ] Logurile arată OK în `docker-compose logs`
- [ ] Restart funcționează: `docker-compose restart`
- [ ] Containerul supraviețuiește reboot: `docker-compose down && docker-compose up -d`

Dacă toate sunt ✅, ești gata pentru server! 🚀

---

## 🎯 Comenzi Rapide - Cheat Sheet

```bash
# Build
docker-compose build

# Run (foreground)
docker-compose up

# Run (background)
docker-compose up -d

# Stop
docker-compose down

# Restart
docker-compose restart

# Logs (live)
docker-compose logs -f

# Status
docker-compose ps

# Shell în container
docker exec -it casehugauto /bin/bash

# Copiază debug files
docker cp casehugauto:/app/debug_output ./debug_local

# Rebuild complet
docker-compose down && docker-compose build --no-cache && docker-compose up -d

# Curățenie totală
docker system prune -a -f
```

---

## 📚 Resurse Utile

- [Docker Documentation](https://docs.docker.com/)
- [Docker Compose Documentation](https://docs.docker.com/compose/)
- [Dockerfile Best Practices](https://docs.docker.com/develop/dev-best-practices/)

---

**Mult succes cu Docker! 🐳**

Pentru probleme, verifică:
1. `docker-compose logs -f` - logurile live
2. `./debug_output/` - fișiere HTML și screenshots
3. [TROUBLESHOOTING.md](TROUBLESHOOTING.md) - probleme comune
