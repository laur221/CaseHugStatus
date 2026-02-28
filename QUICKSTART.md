# ⚡ Quick Start - Pornire Rapidă

Ghid rapid pentru a avea botul funcțional în 5 minute!

---

## 🚀 Pași Rapizi

### 1️⃣ Instalează Dependențele (30 secunde)

**Windows:**
```bash
setup.ps1
```

**Sau manual:**
```bash
pip install -r requirements.txt
```

---

### 2️⃣ Configurează Telegram (2 minute)

1. **Creează bot:**
   - Caută `@BotFather` pe Telegram
   - Trimite `/newbot`
   - Alege un nume și username
   - Copiază tokenul primit

2. **Obține Chat ID:**
   - Caută `@userinfobot` pe Telegram
   - Trimite un mesaj
   - Copiază ID-ul primit

3. **Editează config.json:**
   ```json
   {
     "telegram_bot_token": "PUNE-TOKENUL-AICI",
     "telegram_chat_id": "PUNE-CHAT-ID-AICI",
     ...
   }
   ```

---

### 3️⃣ Testează Telegram (10 secunde)

```bash
python test_telegram.py
```

Dacă vezi "✅ SUCCES!" înseamnă că e gata! 🎉

---

### 4️⃣ Rulează Botul (Prima dată - 5 minute)

```bash
python main.py
```

**CE SE ÎNTÂMPLĂ:**
1. Se deschid 4 browsere Chrome
2. Pentru fiecare browser: **LOGHEAZĂ-TE MANUAL PE STEAM** (ai 60 secunde)
3. După login, botul preia controlul
4. Deschide casele gratuite
5. Trimite raport pe Telegram

**⚠️ IMPORTANT:** După prima rulare, login-ul e salvat! Nu mai trebuie să te loghezi data viitoare.

---

### 5️⃣ Rulări Ulterioare (Automat!)

Acum poți rula oricând:

```bash
python main.py
```

Sau click dublu pe:
```
run.bat
```

Botul va:
- ✅ Deschide browserele (deja logate)
- ✅ Accesa casehug.com
- ✅ Deschide casele gratuite
- ✅ Trimite raport pe Telegram

---

## 📋 Checklist Ultra-Rapid

Înainte de prima rulare, verifică:

- [ ] Python instalat (`python --version`)
- [ ] Chrome instalat și actualizat
- [ ] Dependențe instalate (`pip install -r requirements.txt`)
- [ ] `config.json` creat și editat cu:
  - [ ] Token Telegram de la @BotFather
  - [ ] Chat ID de la @userinfobot
  - [ ] Numele celor 4 conturi
- [ ] Test Telegram reușit (`python test_telegram.py`)

---

## 🎯 CE FACI DUPĂ?

### Automatizare Zilnică

**Windows Task Scheduler:**
1. Win + R → `taskschd.msc`
2. Create Basic Task
3. Daily la ora 10:00
4. Action: `python.exe`
5. Arguments: `d:\github\CasehugAuto\main.py`

**Sau folosește un script:**
```powershell
# daily_run.ps1
cd "d:\github\CasehugAuto"
python main.py
```

---

## 🐛 Probleme?

### ❌ "config.json nu există"
```bash
copy config.example.json config.json
# Apoi editează config.json
```

### ❌ "ModuleNotFoundError"
```bash
pip install -r requirements.txt
```

### ❌ Browserul nu se deschide
- Actualizează Chrome
- Reinstalează: `pip install --upgrade selenium webdriver-manager`

### ❌ Nu primesc mesaje pe Telegram
- Rulează: `python test_telegram.py`
- Verifică token și chat ID în config.json
- Asigură-te că ai apăsat "Start" pe bot

---

## 📚 Pentru Mai Multe Detalii

- **README.md** - Documentație completă
- **TELEGRAM_SETUP.md** - Ghid detaliat Telegram
- **TROUBLESHOOTING.md** - Rezolvare probleme

---

## 💡 Tips & Tricks

### Tip 1: Rule odată pe zi
```bash
# Ajunge să rulezi o dată pe zi pentru casele gratuite
# Nu abuza, riști ban
```

### Tip 2: Verifică raportul Telegram
```
📱 Vei primi pe Telegram:
- Ce skin-uri ai primit
- Prețul fiecărui skin
- Balanța actualizată
- Pentru toate 4 conturile
```

### Tip 3: Configurare per cont
```json
// Unele conturi nu au Steam case
"available_cases": ["discord", "daily"]  // Fără "steam"

// Alte conturi au toate
"available_cases": ["discord", "steam", "daily"]
```

### Tip 4: Păstrează browserele deschise
```python
# În main.py, browserele rămân deschise
# Ca să le închizi automat, decomentează:
# driver.quit()  # linia 207
```

---

## 🎰 Exemplu Raport Telegram

După rulare, vei primi:

```
🎰 Casehug Daily Report
📅 28.02.2026 10:00:00
──────────────────────────────

👤 Cont Principal
💰 Balanță: $25.50

  📦 discord:
     🎁 AK-47 | Redline (FT)
     💵 $8.50

  📦 steam:
     🎁 AWP | Asiimov (BS)
     💵 $12.30

  📦 daily:
     🎁 Glock-18 | Water Elemental
     💵 $3.20

──────────────────────────────
... (celelalte 3 conturi)
```

---

## ✅ Gata!

Acum ai totul configurat! 🎉

Rulează `python main.py` și bucură-te de automatizare! 🚀

---

**Happy Autotrading! 🎰💰**
