# 🐛 Debug Guide - Cum să Corectezi Selectoarele

Acest ghid te ajută să înțelegi fișierele de debugging și să corectezi selectoarele CSS pentru casehug.com.

---

## 📁 Fișiere Generate

După rulare, botul generează automat fișiere de debugging:

### HTML Files (`debug_*.html`)
- `debug_Cont1_homepage.html` - Pagina principală
- `debug_Cont1_free_cases_discord.html` - Pagina free cases
- `debug_Cont1_after_open_discord.html` - După deschiderea case-ului

### Screenshots (`debug_*.png`)
- `debug_Cont1_homepage.png` - Screenshot homepage
- `debug_Cont1_free_cases_discord.png` - Screenshot free cases
- etc.

---

## 🔍 Cum să Găsești Selectoarele Corecte

### Pasul 1: Deschide fișierul HTML

Deschide `debug_Cont1_homepage.html` în browser (Chrome/Firefox).

### Pasul 2: Deschide Developer Tools

Apasă `F12` sau `Ctrl+Shift+I`.

### Pasul 3: Găsește Butonul de Login

1. În HTML, caută după cuvinte cheie:
   - "login"
   - "steam"
   - "sign in"
   - "auth"

2. Click dreapta pe element → "Inspect"

3. Notează:
   - **Clasa CSS**: exemplu `class="btn-steam-login"`
   - **ID**: exemplu `id="steam-btn"`
   - **Href**: exemplu `href="/auth/steam"`

### Exemplu:

Dacă găsești:
```html
<a href="/auth/steam" class="login-button steam">
  <span>Login with Steam</span>
</a>
```

Selectoarele potrivite ar fi:
- `a[href='/auth/steam']`
- `.login-button.steam`
- `a.steam`

---

## 🛠️ Cum să Actualizezi main.py

### Pentru Butonul de Login:

Deschide `main.py` și caută funcția `login_steam()`.

Găsește linia ~115:
```python
login_selectors = [
    "a[href*='steam']",
    "a[href*='auth']",
    ...
]
```

Adaugă selectorul tău la început:
```python
login_selectors = [
    ".login-button.steam",  # ADAUGĂ SELECTORUL TĂU AICI
    "a[href*='steam']",
    "a[href*='auth']",
    ...
]
```

### Pentru Case-uri (Discord/Steam/Daily):

Deschide `debug_Cont1_free_cases_discord.html` în browser.

Caută butonul pentru "Discord Case" sau "Steam Case".

Exemplu găsit:
```html
<button class="free-case discord-case" data-type="discord">
  Discord Case
</button>
```

Actualizează în `main.py`, funcția `open_free_cases()`, linia ~200:
```python
case_selectors = [
    f"button.discord-case",  # ADAUGĂ SELECTORUL TĂU
    f".free-case[data-type='discord']",  # SAU ASTA
    f".case-{case_type.lower()}",
    ...
]
```

### Pentru Skin Name și Price:

După ce deschizi un case, verifică `debug_Cont1_after_open_discord.html`.

Caută elementul care conține numele skin-ului.

Exemplu:
```html
<div class="reward-item">
  <h3 class="item-name">AK-47 | Redline (Field-Tested)</h3>
  <span class="item-value">$8.50</span>
</div>
```

Actualizează în `main.py`, funcția `open_free_cases()`, linia ~240:
```python
skin_selectors = [
    ".item-name",  # SELECTORUL TĂU PENTRU SKIN
    ...
]

price_selectors = [
    ".item-value",  # SELECTORUL TĂU PENTRU PREȚ
    ...
]
```

---

## 📊 Înțelegerea Output-ului Botului

Când rulezi botul, vei vedea:

```
🔍 Analizez structura paginii: casehug.com homepage
   📊 Total elemente cu text: 156
   🔗 Link-uri vizibile: 23
   🔘 Butoane vizibile: 8

   📋 Primele butoane găsite:
      1. [Login with Steam] - class: btn btn-primary steam-login
      2. [Free Cases] - class: btn btn-secondary
      3. [Deposit] - class: btn btn-success
```

Folosește aceste informații pentru a găsi selectoarele corecte!

---

## 🎯 Exemplu Complet de Debugging

### Problema: Nu găsește butonul Discord Case

**1. Verifică output-ul botului:**
```
🔍 Analizez structura paginii: free cases page - discord
   📋 Primele butoane găsite:
      1. [Collect] - class: case-button discord
      2. [Open Now] - class: case-button steam
```

**2. Deschide `debug_Cont1_free_cases_discord.html`**

Caută "discord" în HTML (Ctrl+F).

**3. Găsești:**
```html
<button class="case-button discord" onclick="openCase('discord')">
  Collect
</button>
```

**4. Actualizează main.py:**
```python
# În funcția open_free_cases(), adaugă:
case_selectors = [
    f"button.case-button.{case_type.lower()}",  # ADAUGĂ ASTA
    f"button[onclick*='{case_type.lower()}']",  # SAU ASTA
    ...
]
```

**5. Rulează din nou:**
```bash
python main.py
```

---

## 💡 Tips & Tricks

### Tip 1: Folosește Consola JavaScript

În Developer Tools, tab "Console", testează selectorul:
```javascript
document.querySelector(".case-button.discord")
```

Dacă returnează `null`, selectorul e greșit.
Dacă returnează un element, selectorul e corect!

### Tip 2: Verifică Multiple Pagini

Site-ul poate arăta diferit:
- Cu/fără login
- Desktop vs Mobile
- Diferit pentru fiecare cont

Compară `debug_Cont1_*.html` cu `debug_Cont2_*.html`.

### Tip 3: Caută Pattern-uri

Site-urile folosesc pattern-uri consistente:
- Toate case-urile au clasa `.case-button`
- Toate prețurile au clasa `.price` sau `.value`
- Toate skin-urile sunt în tag-uri `<h3>` sau `<h4>`

### Tip 4: Folosește Wildcard

Dacă clasa se schimbă dinamic:
```python
# În loc de:
".case-button-discord-v2"

# Folosește:
"[class*='case'][class*='discord']"
```

---

## 🚨 Probleme Comune

### ❌ "Nu am găsit case-ul discord"

**Cauze posibile:**
1. Case-ul nu e disponibil (deja deschis astăzi)
2. Selectorul CSS e greșit
3. Case-ul e ascuns de un popup
4. Pagina nu s-a încărcat complet

**Soluții:**
1. Verifică manual pe site dacă case-ul e disponibil
2. Analizează `debug_*.html` și actualizează selectorul
3. Adaugă mai mult timp de așteptare: `time.sleep(5)`
4. Verifică `debug_*.png` pentru popup-uri

### ❌ "Skin: Necunoscut, Price: N/A"

**Cauze posibile:**
1. Numele skin-ului e într-un iframe sau shadow DOM
2. Selectorul CSS e greșit
3. Trebuie mai mult timp de așteptare

**Soluții:**
1. Verifică `debug_*_after_open_*.html`
2. Caută după text direct în HTML
3. Adaugă `time.sleep(3)` după click pe case

---

## 📚 Resurse Utile

### Selectoare CSS

- **Clasă**: `.class-name`
- **ID**: `#element-id`
- **Atribut**: `[data-type='value']`
- **Conține**: `[class*='partial']`
- **Începe cu**: `[href^='/auth']`
- **Se termină**: `[href$='.html']`
- **Combinat**: `button.class-name[data-type='value']`

### XPath (alternativă)

În loc de CSS selector, poți folosi XPath:
```python
# CSS
driver.find_element(By.CSS_SELECTOR, ".button")

# XPath
driver.find_element(By.XPATH, "//button[@class='button']")
```

---

## ✅ Checklist Final

Înainte de a declara că "nu funcționează":

- [ ] Am verificat fișierele `debug_*.html` generate
- [ ] Am testat selectorul în Developer Tools Console
- [ ] Am verificat pe site manual că elementul există
- [ ] Am adăugat suficient timp de așteptare (`time.sleep`)
- [ ] Am verificat că nu sunt popup-uri care blochează
- [ ] Am comparat HTML-ul între conturi diferite
- [ ] Am citit output-ul complet al botului pentru erori

---

**Mult succes la debugging! 🎯**

Dacă ai întrebări, verifică:
1. Fișierele `debug_*.html` și `debug_*.png`
2. Output-ul complet al botului
3. TROUBLESHOOTING.md pentru soluții comune
