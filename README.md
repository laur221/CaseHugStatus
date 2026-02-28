# 🎰 CasehugAuto - Bot Automatizare Casehug.com

Bot Python pentru automatizarea deschiderii caselor gratuite pe casehug.com cu 4 conturi Steam diferite și notificări pe Telegram.

## 📋 Caracteristici

- ✅ 4 browsere Chrome cu profile separate (salvează login-ul Steam permanent)
- ✅ Deschide automat casele gratuite (Discord, Steam, Daily)
- ✅ Trimite raport detaliat pe Telegram cu:
  - Skin-urile primite
  - Prețurile skinurilor
  - Balanța contului
- ✅ Configurabil pentru fiecare cont (unele conturi nu au Steam case disponibil)
- ✅ Nu trebuie să te loghezi de fiecare dată - salvează sesiunea
- ✅ **Docker support** - rulează în container izolat

## 🚀 Instalare

### Metoda 1: Cu Docker (Recomandat) 🐳

**Avantaje:**
- Setup rapid (un singur comandă)
- Funcționează identic pe Windows/Linux/Mac/Server
- Nu poluează sistemul cu dependențe
- Ușor de deploiat pe server

```bash
# 1. Clonează repo
git clone https://github.com/your-user/CasehugAuto
cd CasehugAuto

# 2. Configurează
copy config.example.json config.json
# Editează config.json cu datele tale

# 3. Build și run
docker-compose build
docker-compose up
```

📚 **Ghid complet:** [DOCKER_GUIDE.md](DOCKER_GUIDE.md)

---

### Metoda 2: Instalare Manuală

#### 1. Instalează Python
Descarcă Python 3.8+ de la [python.org](https://www.python.org/downloads/)

### 2. Instalează dependențele
```bash
pip install -r requirements.txt
```

### 3. Instalează Chrome și ChromeDriver
- Asigură-te că ai Google Chrome instalat
- ChromeDriver va fi descărcat automat de webdriver-manager

## ⚙️ Configurare

### 1. Configurează config.json

Editează `config.json` cu datele tale:

```json
{
  "telegram_bot_token": "123456:ABC-DEF1234ghIkl-zyx57W2v1u123ew11",
  "telegram_chat_id": "123456789",
  "accounts": [
    {
      "name": "Cont Principal",
      "profile_dir": "profile_1",
      "available_cases": ["discord", "steam", "daily"]
    },
    {
      "name": "Cont Secundar",
      "profile_dir": "profile_2",
      "available_cases": ["discord", "steam", "daily"]
    },
    {
      "name": "Cont 3 (fără Steam case)",
      "profile_dir": "profile_3",
      "available_cases": ["discord", "daily"]
    },
    {
      "name": "Cont 4 (fără Steam case)",
      "profile_dir": "profile_4",
      "available_cases": ["discord", "daily"]
    }
  ]
}
```

### 2. Creează un Bot Telegram

1. Deschide Telegram și caută `@BotFather`
2. Trimite comanda `/newbot`
3. Urmează instrucțiunile și copiază tokenul primit
4. Pune tokenul în `telegram_bot_token` din config.json

### 3. Obține Chat ID pentru Telegram

1. Caută `@userinfobot` pe Telegram
2. Trimite-i orice mesaj
3. Copiază ID-ul primit
4. Pune ID-ul în `telegram_chat_id` din config.json

**SAU**

1. Trimite un mesaj botului tău
2. Accesează: `https://api.telegram.org/bot<YOUR_BOT_TOKEN>/getUpdates`
3. Caută `"chat":{"id":123456789}` și copiază ID-ul

## 🎮 Utilizare

### Prima rulare (Login Steam)

La prima rulare, vei trebui să te loghezi manual pe Steam pentru fiecare cont:

```bash
python main.py
```

1. Se vor deschide 4 browsere Chrome
2. Pentru fiecare browser, programa va aștepta 60 secunde
3. În timpul acesta, loghează-te manual pe Steam în fiecare browser
4. După ce te-ai logat, browserul va salva sesiunea
5. Data viitoare nu va mai fi nevoie să te loghezi!

### Rulări ulterioare

După ce ai făcut login prima dată, poți rula programa oricând:

```bash
python main.py
```

Programa va:
1. Deschide automat cele 4 browsere (deja logate)
2. Accesa casehug.com pentru fiecare cont
3. Deschide casele gratuite disponibile
4. Extrage skin-urile primite și prețurile
5. Trimite un raport pe Telegram cu toate informațiile

## 📊 Exemplu Raport Telegram

```
🎰 Casehug Daily Report
📅 28.02.2026 14:30:00
──────────────────────────────

👤 Cont Principal
💰 Balanță: $15.50

  📦 discord:
     🎁 AK-47 | Redline (Field-Tested)
     💵 $8.50

  📦 steam:
     🎁 AWP | Asiimov (Battle-Scarred)
     💵 $12.30

  📦 daily:
     🎁 Glock-18 | Water Elemental
     💵 $3.20

──────────────────────────────

👤 Cont Secundar
💰 Balanță: $8.30

  📦 discord:
     🎁 M4A4 | Asiimov (Well-Worn)
     💵 $6.50
  ...
```

## 🔧 Personalizare

### Selectoare CSS

Dacă site-ul casehug.com își schimbă structura, va trebui să actualizezi selectoarele CSS în `main.py`:

- **Login button**: linia ~78
- **Profile element**: linia ~69
- **Case buttons**: linia ~110-115
- **Skin name**: linia ~129
- **Price**: linia ~134
- **Balance**: linia ~165

### Headless Mode (pentru server)

Dacă vrei să rulezi botul pe server fără GUI, decomentează linia 50 în `main.py`:

```python
chrome_options.add_argument("--headless")
```

### Închidere browsere după finalizare

Dacă vrei să închizi browserele automat după rulare, decomentează linia 207:

```python
driver.quit()
```

## 📅 Automatizare zilnică

### Windows Task Scheduler

1. Deschide Task Scheduler
2. Create Basic Task
3. Trigger: Daily la ora dorită
4. Action: Start a program
5. Program: `python.exe`
6. Arguments: `d:\github\CasehugAuto\main.py`
7. Start in: `d:\github\CasehugAuto`

### Linux Cron

```bash
crontab -e
```

Adaugă:
```
0 10 * * * cd /path/to/CasehugAuto && python3 main.py
```

## 🐛 Troubleshooting

### Eroare: "selenium.common.exceptions.SessionNotCreatedException"
- Actualizează Chrome la ultima versiune
- Reinstalează: `pip install --upgrade selenium webdriver-manager`

### Browserul nu se deschide
- Verifică dacă Chrome este instalat
- Run: `pip install webdriver-manager --upgrade`

### Nu trimite mesaje pe Telegram
- Verifică dacă tokenul și chat ID sunt corecte
- Asigură-te că ai trimis măcar un mesaj botului

### Nu găsește elementele pe site
- Site-ul s-a schimbat, actualizează selectoarele CSS în main.py
- Adaugă `time.sleep(5)` pentru a aștepta încărcarea paginii

## ⚠️ Atenție

- **Rate limiting**: Nu rula botul prea des, poți fi banat de site
- **Securitate**: Nu partaja `config.json` cu nimeni (conține tokenul Telegram)
- **Legal**: Folosește botul doar pentru conturile tale personale
- **Responsabilitate**: Foloseșt botul pe propriul risc

## 📝 Licență

Acest proiect este pentru uz personal. Folosește-l responsabil!

## 🤝 Support

Dacă ai probleme sau întrebări, verifică:
1. Că toate dependențele sunt instalate
2. Că config.json este corect configurat
3. Că Chrome și ChromeDriver sunt actualizate
4. Că te-ai logat pe Steam în browsere

---

**Made with ❤️ for automating daily tasks**
