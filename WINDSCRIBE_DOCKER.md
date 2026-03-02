# 🌐 Windscribe în Docker - 2 Metode

## ⚡ Metoda 1: SOCKS5 Proxy (RECOMANDAT - CEA MAI SIMPLĂ)

### Pas 1: Obține credentials SOCKS5
1. Mergi la: https://windscribe.com/myaccount
2. Click pe **"Config Generators"**
3. Secțiunea **"SOCKS5 Proxy"**
4. Vei vedea:
   ```
   Hostname: proxy-nl.windscribe.com (sau alt server)
   Port: 1080
   Username: your_windscribe_username
   Password: your_windscribe_password
   ```

### Pas 2: Configurează în config.json
```json
{
  "proxy": {
    "enabled": true,
    "host": "proxy-nl.windscribe.com",
    "port": 1080,
    "username": "your_windscribe_username",
    "password": "your_windscribe_password"
  }
}
```

### Pas 3: Rulează bot-ul
```bash
docker-compose up --build -d
```

**Avantaje:**
- ✅ CEL MAI SIMPLU
- ✅ Funcționează 100%
- ✅ Nu necesită privilegii speciale
- ✅ Setup în 2 minute

**Dezavantaje:**
- ⚠️ Trebuie să ai plan Windscribe plătit ($3-9/lună)

---

## 🔧 Metoda 2: Windscribe CLI în Docker (AVANSATĂ)

### Pas 1: Configurează credentials

Editează `.env.windscribe`:
```bash
WINDSCRIBE_USERNAME=your_windscribe_username
WINDSCRIBE_PASSWORD=your_windscribe_password
```

### Pas 2: Build cu Windscribe

```bash
# Build image cu Windscribe CLI
docker-compose -f docker-compose.windscribe.yml up --build -d
```

### Pas 3: Verifică conexiunea

```bash
# Vezi logs
docker-compose -f docker-compose.windscribe.yml logs -f

# Ar trebui să vezi:
# 🌐 Pornesc Windscribe VPN...
# 🔐 Login Windscribe...
# 🇫🇷 Conectez la France...
# ✅ Verificare IP: 185.xxx.xxx.xxx
```

**Avantaje:**
- ✅ VPN complet în container
- ✅ Funcționează cu orice plan Windscribe
- ✅ Control total asupra locației

**Dezavantaje:**
- ⚠️ Mai complicat
- ⚠️ Necesită `privileged: true` (mai puțin sigur)
- ⚠️ Build mai lent (~2-3 min)

---

## 🚀 QUICK START (Metoda 1 - SOCKS5)

### 1. Obține SOCKS5 credentials de la Windscribe

### 2. Editează config.json:
```json
{
  "proxy": {
    "enabled": true,
    "host": "proxy-nl.windscribe.com",
    "port": 1080,
    "username": "YOUR_USERNAME",
    "password": "YOUR_PASSWORD"
  }
}
```

### 3. Rulează:
```bash
docker-compose up --build -d
docker-compose logs -f
```

### 4. Verifică:
Ar trebui să vezi:
```
✅ Pagină creată cu stealth pentru Cont 1
🌐 Folosesc proxy: proxy-nl.windscribe.com:1080
🍪 Găsit fișier cookies: cookies_cont1.json
✅ Cookie-uri încărcate: 12/12
📦 Deschid discord pentru Cont 1...
```

**Dacă NU apare Cloudflare challenge → SUCCESS! ✅**

---

## 📊 Comparație metode

| Aspect | SOCKS5 Proxy | Windscribe CLI |
|--------|--------------|----------------|
| **Dificultate** | ⭐ Foarte simplu | ⭐⭐⭐ Avansat |
| **Timp setup** | 2 minute | 10 minute |
| **Securitate** | ✅ Sigur | ⚠️ privileged mode |
| **Viteză build** | ✅ 1 minut | ⚠️ 3-5 minute |
| **Plan necesar** | Pro ($3-9/lună) | Orice plan |
| **Funcționează?** | ✅ 100% | ✅ 100% |

---

## ❓ Care metodă să aleg?

### Dacă ai plan Windscribe plătit ($3/lună):
→ **Folosește SOCKS5 Proxy** (Metoda 1)
- Cel mai simplu
- Cel mai rapid
- Cel mai sigur

### Dacă vrei VPN complet în container:
→ **Folosește Windscribe CLI** (Metoda 2)
- Mai mult control
- Schimbi locația ușor
- Funcționează cu orice plan

---

## 🔍 Testare

### Verifică că VPN funcționează:

**Cu SOCKS5:**
```bash
docker-compose logs | grep "proxy"
# Ar trebui: 🌐 Folosesc proxy: proxy-nl.windscribe.com:1080
```

**Cu Windscribe CLI:**
```bash
docker exec -it casehugauto_windscribe windscribe status
# Ar trebui: CONNECTED to FR
```

### Verifică că Cloudflare este bypass:
```bash
docker-compose logs | grep "Cloudflare"
```

**Succes:**
```
✅ Cloudflare challenge trecut!
```

**Eșec:**
```
❌ Cloudflare challenge nu a fost trecut în 30s
```

---

## 🆘 Troubleshooting

### SOCKS5 nu funcționează:
1. Verifică credentials în config.json
2. Testează manual: `curl -x socks5://username:password@proxy-nl.windscribe.com:1080 https://api.ipify.org`
3. Încearcă alt server: `proxy-us.windscribe.com` sau `proxy-fr.windscribe.com`

### Windscribe CLI nu se conectează:
1. Verifică username/password în `.env.windscribe`
2. Vezi logs: `docker-compose -f docker-compose.windscribe.yml logs`
3. Intră manual în container: `docker exec -it casehugauto_windscribe bash`
4. Testează: `windscribe status`

---

## 📞 Next Steps

1. **Alege metoda ta:**
   - SOCKS5 (simplu) sau CLI (avansat)?

2. **Configurează credentials:**
   - config.json (SOCKS5) sau .env.windscribe (CLI)

3. **Rulează:**
   ```bash
   docker-compose up --build -d
   ```

4. **Verifică logs:**
   ```bash
   docker-compose logs -f
   ```

**Întrebare:** Care metodă preferi? SOCKS5 sau CLI?
