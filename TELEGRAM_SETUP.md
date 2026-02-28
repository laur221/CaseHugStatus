# 📱 Ghid Rapid - Configurare Telegram Bot

Acest ghid te ajută să configurezi botul Telegram în câțiva pași simpli.

---

## 🤖 Pasul 1: Creează Botul Telegram

### 1.1 Deschide Telegram
- Pe telefon sau desktop
- Caută `@BotFather` (botul oficial Telegram pentru crearea de boți)

### 1.2 Creează un bot nou
Trimite următoarele comenzi în chat cu BotFather:

```
/newbot
```

BotFather te va întreba:

**1. Nume pentru bot:**
```
CasehugAuto Bot
```
(Poți folosi orice nume vrei)

**2. Username pentru bot:**
```
casehugauto_bot
```
(Trebuie să se termine în `_bot` și să fie unic)

### 1.3 Copiază tokenul
BotFather îți va da un token care arată așa:
```
123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789
```

**⚠️ IMPORTANT:** Păstrează acest token secret! Nu-l împărtăși cu nimeni!

---

## 💬 Pasul 2: Obține Chat ID

### Metoda 1: Cu @userinfobot (Cel mai simplu)

1. Caută `@userinfobot` pe Telegram
2. Click pe "Start" sau trimite orice mesaj
3. Botul îți va răspunde cu informațiile tale, inclusiv **ID-ul**
4. Copiază numărul de la "Id:" (ex: `123456789`)

### Metoda 2: Cu @getidsbot

1. Caută `@getidsbot` pe Telegram
2. Trimite comanda `/start`
3. Copiază "Your user ID"

### Metoda 3: Manual prin API (Dacă primele 2 nu funcționează)

1. **Trimite un mesaj botului tău:**
   - Caută botul tău pe Telegram (username-ul pe care l-ai creat)
   - Click pe "Start" sau trimite orice mesaj (ex: "test")

2. **Deschide în browser:**
   ```
   https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates
   ```
   
   Înlocuiește `<YOUR_TOKEN>` cu tokenul de la BotFather.
   
   Exemplu:
   ```
   https://api.telegram.org/bot123456789:ABCdefGHI/getUpdates
   ```

3. **Găsește chat ID:**
   Vei vedea ceva de genul:
   ```json
   {
     "ok": true,
     "result": [
       {
         "message": {
           "chat": {
             "id": 123456789,
             "first_name": "Numele Tău"
           }
         }
       }
     ]
   }
   ```
   
   Copiază numărul de la `"id"` (în exemplu: `123456789`)

---

## ⚙️ Pasul 3: Configurează config.json

Editează fișierul `config.json`:

```json
{
  "telegram_bot_token": "123456789:ABCdefGHIjklMNOpqrsTUVwxyz123456789",
  "telegram_chat_id": "123456789",
  "accounts": [
    ...
  ]
}
```

Înlocuiește:
- `telegram_bot_token` - cu tokenul de la BotFather
- `telegram_chat_id` - cu ID-ul tău

---

## ✅ Pasul 4: Testează Configurația

### Test rapid în Python:

Creează un fișier `test_telegram.py`:

```python
import requests

# Înlocuiește cu datele tale
TOKEN = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"
CHAT_ID = "123456789"

url = f"https://api.telegram.org/bot{TOKEN}/sendMessage"
data = {
    "chat_id": CHAT_ID,
    "text": "✅ Telegram Bot funcționează corect!"
}

response = requests.post(url, data=data)
print(response.text)

if response.status_code == 200:
    print("\n✅ SUCCESS! Verifică Telegram pentru mesaj.")
else:
    print(f"\n❌ EROARE: {response.status_code}")
    print(response.json())
```

Rulează:
```bash
python test_telegram.py
```

Dacă funcționează, vei primi un mesaj pe Telegram! 🎉

---

## 🔧 Troubleshooting Telegram

### ❌ Eroare: "Unauthorized"
**Problema:** Token-ul este greșit sau bot-ul a fost șters.

**Soluție:**
- Verifică că ai copiat tokenul complet (inclusiv partea după `:`)
- Verifică la @BotFather că botul există (`/mybots`)

---

### ❌ Eroare: "Bad Request: chat not found"
**Problema:** Chat ID-ul este greșit sau nu ai trimis niciun mesaj botului.

**Soluție:**
1. Deschide botul pe Telegram
2. Click pe "Start"
3. Trimite un mesaj (orice mesaj)
4. Apoi obține chat ID-ul din nou

---

### ❌ Nu primesc mesaje
**Problema:** Ai blocat botul sau ai șters conversația.

**Soluție:**
1. Caută botul pe Telegram
2. Click pe "Restart" sau "Unblock"
3. Trimite un mesaj
4. Rulează testul din nou

---

## 📝 Exemplu Complet config.json

```json
{
  "telegram_bot_token": "6123456789:AAFNcL_X12345abcdefGHIJKLMNOPQRSTUVW",
  "telegram_chat_id": "987654321",
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

---

## 🎯 Verificare Finală

Înainte de a rula botul complet, verifică:

- [ ] Ai creat botul cu @BotFather
- [ ] Ai copiat tokenul complet
- [ ] Ai trimis măcar un mesaj botului (click "Start")
- [ ] Ai obținut chat ID-ul
- [ ] Ai editat `config.json` cu datele corecte
- [ ] Testul `test_telegram.py` funcționează
- [ ] Ai primit mesajul de test pe Telegram

---

## 🚀 Gata să rulezi!

Dacă toate verificările de mai sus sunt OK, poți rula:

```bash
python main.py
```

Vei primi rapoarte pe Telegram după ce botul deschide casele! 🎰

---

**Mult succes! 📱✨**
