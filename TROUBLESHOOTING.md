# 🐛 Troubleshooting Guide - CasehugAuto

Acest ghid te ajută să rezolvi problemele comune întâlnite la rularea botului.

---

## 📋 Probleme Comune și Soluții

### ❌ Eroare: "config.json nu există"

**Problema:** Fișierul de configurație lipsește.

**Soluție:**
```bash
# Copiază fișierul exemplu
copy config.example.json config.json

# Sau pe Linux/Mac
cp config.example.json config.json
```

Apoi editează `config.json` cu datele tale.

---

### ❌ Eroare: "selenium.common.exceptions.SessionNotCreatedException"

**Problema:** Versiunea ChromeDriver nu se potrivește cu versiunea Chrome.

**Soluție:**
```bash
# Actualizează Chrome la ultima versiune
# Apoi reinstalează webdriver-manager
pip install --upgrade webdriver-manager selenium
```

---

### ❌ Eroare: "ModuleNotFoundError: No module named 'selenium'"

**Problema:** Dependențele nu sunt instalate.

**Soluție:**
```bash
pip install -r requirements.txt
```

---

### ❌ Browserul nu se deschide / Se închide imediat

**Problema:** ChromeDriver nu este configurat corect sau Chrome lipsește.

**Soluție:**
1. Verifică că Google Chrome este instalat
2. Actualizează Chrome la ultima versiune
3. Reinstalează dependențele:
```bash
pip uninstall selenium webdriver-manager
pip install selenium webdriver-manager
```

---

### ❌ Nu primesc mesaje pe Telegram

**Problema:** Bot token sau chat ID greșit.

**Soluție:**

**1. Verifică tokenul botului:**
- Accesează @BotFather pe Telegram
- Folosește comanda `/mybots`
- Selectează botul tău
- Alege "API Token" și copiază tokenul
- Pune-l în `config.json` la `telegram_bot_token`

**2. Verifică chat ID:**
- Trimite un mesaj botului tău
- Accesează în browser: `https://api.telegram.org/bot<YOUR_TOKEN>/getUpdates`
- Caută `"chat":{"id":123456789}`
- Copiază ID-ul (numărul)
- Pune-l în `config.json` la `telegram_chat_id`

**Test rapid:**
```python
import requests
token = "YOUR_TOKEN"
chat_id = "YOUR_CHAT_ID"
url = f"https://api.telegram.org/bot{token}/sendMessage"
data = {"chat_id": chat_id, "text": "Test"}
print(requests.post(url, data=data).text)
```

---

### ❌ Eroare: "element not found" sau "TimeoutException"

**Problema:** Site-ul casehug.com s-a schimbat sau funcționează diferit.

**Soluție:**

**1. Verifică dacă site-ul funcționează:**
- Deschide manual casehug.com în browser
- Verifică dacă poți accesa casele gratuite

**2. Actualizează selectoarele CSS:**

Deschide `main.py` și găsește funcția `open_free_cases()`. Inspectează elementele pe site (F12 în browser) și actualizează selectoarele:

```python
# Exemplu: găsește selectorul corect pentru butonul case-ului
case_button = driver.find_element(By.CSS_SELECTOR, ".case-discord")  # Actualizează aici
```

**3. Adaugă mai mult timp de așteptare:**

În `main.py`, crește timpul de așteptare:
```python
time.sleep(5)  # În loc de 2-3 secunde
```

---

### ❌ Nu pot să mă loghez pe Steam / Redirecționează la login mereu

**Problema:** Cookies nu se salvează sau profilul Chrome nu este persistent.

**Soluție:**

**1. Verifică că directorul profiles există:**
```bash
dir profiles     # Windows
ls -la profiles  # Linux/Mac
```

**2. Șterge profilurile și încearcă din nou:**
```bash
rmdir /s profiles  # Windows
rm -rf profiles    # Linux/Mac
```

**3. Asigură-te că browserul nu rulează în headless mode:**
În `main.py`, comentează linia:
```python
# chrome_options.add_argument("--headless")  # Comentează această linie
```

**4. Login manual corect:**
- Rulează `python main.py`
- Când se deschide browserul, așteaptă să vezi butonul "Login with Steam"
- Click pe el și loghează-te
- Așteaptă până se încarcă complet pagina
- Abia apoi lasă programa să continue

---

### ❌ Eroare: "Permission denied" pe Linux/Server

**Problema:** Permisiuni insuficiente pentru Chrome sau directoare.

**Soluție:**
```bash
# Dă permisiuni corectului
chmod +x /usr/bin/chromedriver
chmod -R 755 profiles/

# Sau rulează ca root (nu recomandat pentru producție)
sudo python3 main.py
```

---

### ❌ Botul nu găsește skin-urile sau prețurile

**Problema:** Selectoarele CSS pentru skin/preț sunt greșite sau s-au schimbat.

**Soluție:**

**1. Inspectează elementele pe site:**
- Deschide casehug.com în browser
- Click dreapta pe numele skin-ului → "Inspect"
- Găsește clasa CSS (ex: `.skin-name`, `.item-title`, etc.)

**2. Actualizează în main.py:**
```python
# Linia ~129
skin_name_element = WebDriverWait(driver, 10).until(
    EC.presence_of_element_located((By.CSS_SELECTOR, ".NEW-SELECTOR-HERE"))
)

# Linia ~134
price_element = driver.find_element(By.CSS_SELECTOR, ".NEW-PRICE-SELECTOR")
```

**3. Adaugă debugging pentru a vedea HTML-ul:**
```python
# După ce deschizi case-ul, adaugă:
print(driver.page_source)  # Vezi tot HTML-ul paginii
```

---

### ❌ "Rate limit" sau "Too many requests"

**Problema:** Rulezi botul prea des și site-ul te blochează temporar.

**Soluție:**
1. Așteaptă câteva ore
2. Nu rula botul mai mult de o dată pe zi
3. Adaugă mai mult delay între acțiuni:

```python
time.sleep(5)  # În loc de 2-3 secunde
```

---

### ❌ Eroare pe server (Linux) fără GUI

**Problema:** Chrome trebuie să ruleze în headless mode pe server.

**Soluție:**

**1. Decomentează headless mode în main.py:**
```python
chrome_options.add_argument("--headless")  # Linia 50
```

**2. Instalează dependențe pentru Chrome headless:**
```bash
# Ubuntu/Debian
sudo apt-get update
sudo apt-get install -y chromium-browser chromium-chromedriver
sudo apt-get install -y xvfb

# Sau folosește Xvfb
Xvfb :99 -ac &
export DISPLAY=:99
python3 main.py
```

---

### ❌ Programă se oprește după ce deschide browserele

**Problema:** Excepție neașteptată sau browser crashes.

**Soluție:**

**1. Rulează cu debugging:**
```bash
python main.py 2>&1 | tee debug.log
```

**2. Verifică memoria:**
- 4 browsere Chrome pot consuma multă memorie (2-4 GB RAM)
- Verifică Task Manager / htop

**3. Adaugă try-catch mai detaliat:**
```python
import traceback

try:
    bot.run()
except Exception as e:
    print(f"EROARE: {e}")
    print(traceback.format_exc())
```

---

## 🔍 Debugging Tips

### 1. Rulează în mod interactiv

Comentează închiderea browserelor pentru a investiga:
```python
# driver.quit()  # Comentează pentru a păstra browserul deschis
```

### 2. Screenshot la erori

Adaugă în `main.py` la catch-urile de excepții:
```python
except Exception as e:
    driver.save_screenshot(f"error_{account_name}.png")
    print(f"Eroare: {e}")
```

### 3. Print HTML-ul paginii

Pentru a vedea ce primește botul:
```python
with open(f"page_{account_name}.html", "w", encoding="utf-8") as f:
    f.write(driver.page_source)
```

### 4. Reduce viteza

Adaugă mai mult delay pentru a vedea ce se întâmplă:
```python
time.sleep(10)  # Așteaptă 10 secunde
```

---

## 📞 Încă ai probleme?

Dacă nicio soluție de mai sus nu funcționează:

1. **Verifică logs:**
   - Rulează `python main.py > log.txt 2>&1`
   - Trimite-mi `log.txt`

2. **Instalare curată:**
   ```bash
   # Șterge tot și reinstalează
   pip uninstall selenium webdriver-manager requests
   pip install -r requirements.txt
   ```

3. **Test manual:**
   - Deschide Chrome manual
   - Navighează pe casehug.com
   - Verifică dacă site-ul funcționează corect

---

## ✅ Checklist înainte de a cere ajutor

- [ ] Python 3.8+ instalat (`python --version`)
- [ ] Dependențe instalate (`pip list | grep selenium`)
- [ ] Chrome actualizat la ultima versiune
- [ ] `config.json` există și este completat corect
- [ ] Telegram bot token și chat ID sunt corecte
- [ ] Site-ul casehug.com funcționează în browser normal
- [ ] Firewall/Antivirus nu blochează Python sau Chrome
- [ ] Ai citit README.md complet

---

**Mult succes! 🎰**
