# 🚀 Quick Start cu Docker

## 🐳 Testare Locală (5 minute)

### Windows:
```powershell
# 1. Pornește Docker Desktop

# 2. Deschide PowerShell în directorul proiectului
cd D:\github\CasehugAuto

# 3. Rulează scriptul de test
.\docker-test.ps1
```

### Linux/Mac:
```bash
# 1. Asigură-te că Docker rulează
docker --version

# 2. Dă permisiuni scriptului
chmod +x docker-test.sh

# 3. Rulează scriptul de test
./docker-test.sh
```

---

## 📝 Manual (dacă scriptul nu funcționează)

### 1. Configurare
```bash
# Copiază și editează config
cp config.example.json config.json
nano config.json  # sau notepad config.json pe Windows
```

Completează:
- `telegram_bot_token` (de la @BotFather)
- `telegram_chat_id` (de la @userinfobot)

### 2. Build
```bash
docker-compose build
```

### 3. Test Telegram
```bash
docker run --rm -v ${PWD}/config.json:/app/config.json casehugauto_casehugbot python test_telegram.py
```

### 4. Run Bot
```bash
# Foreground (vezi logs)
docker-compose up

# Background (detached)
docker-compose up -d
```

---

## 📊 Comandi Utile

```bash
# Vezi logs live
docker-compose logs -f

# Status container
docker-compose ps

# Oprește bot
docker-compose down

# Repornește bot
docker-compose restart

# Debug: shell în container
docker exec -it casehugauto /bin/bash

# Copiază fișiere debug
docker cp casehugauto:/app/debug_output ./debug_local
```

---

## 🐛 Probleme?

### Docker nu pornește
- **Windows/Mac:** Pornește Docker Desktop
- **Linux:** `sudo systemctl start docker`

### Build fail
```bash
# Rebuild complet
docker-compose down
docker-compose build --no-cache
```

### Nu găsește config.json
```bash
# Verifică că există
ls config.json

# Trebuie să fie în directorul curent
pwd
```

---

## ✅ După testare locală reușită

Dacă totul funcționează, ești gata pentru server! 🎉

Vezi [DOCKER_GUIDE.md](DOCKER_GUIDE.md) pentru:
- Deployment pe server
- Automatizare zilnică
- Troubleshooting avansat

---

## 📚 Documentație Completă

- **[README.md](README.md)** - Overview complet
- **[DOCKER_GUIDE.md](DOCKER_GUIDE.md)** - Ghid Docker detaliat
- **[QUICKSTART.md](QUICKSTART.md)** - Pornire rapidă (fără Docker)
- **[TELEGRAM_SETUP.md](TELEGRAM_SETUP.md)** - Configurare Telegram
- **[DEBUG_GUIDE.md](DEBUG_GUIDE.md)** - Cum să corectezi selectoarele
- **[TROUBLESHOOTING.md](TROUBLESHOOTING.md)** - Rezolvare probleme
