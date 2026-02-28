# 🍪 GHID RAPID: Salvare Cookie-uri pentru Bypass Cloudflare

## ✅ Sistemul este gata! Acum trebuie doar să salvezi cookie-urile.

### 📝 PAȘI (foarte simplu):

#### 1️⃣ Rulează scriptul de salvare cookie-uri
```bash
python save_cookies.py
```

#### 2️⃣ Se va deschide Chrome
- Loghează-te manual pe casehug.com cu contul Steam
- După ce ești complet logat, revino în terminal și apasă Enter
- Cookie-urile se vor salva automat în `cookies.json`

#### 3️⃣ Pornește Docker
```bash
docker-compose up -d
```

#### 4️⃣ Verifică funcționarea
```bash
docker-compose logs -f
```

---

## 🎯 Ce se întâmplă după salvarea cookie-urilor?

- ✅ **Bypass Cloudflare 100%** - Cookie-urile valide trec de protecție
- ✅ **Login automat** - Nu mai trebuie să te loghezi de fiecare dată
- ✅ **Funcționare completă** - Botul va putea deschide case-uri automat
- ✅ **Durabilitate** - Cookie-urile sunt valide săptămâni întregi

---

## ⚠️ Notă importantă

Cookie-urile expiră după câteva săptămâni. Când botul nu mai poate accesa site-ul:
1. Rulează din nou `python save_cookies.py`
2. Loghează-te din nou
3. Restart Docker

---

## 🔧 Troubleshooting

**"No module named 'selenium'"** → Instalează: `pip install selenium`

**"Chrome nu se deschide"** → Instalează ChromeDriver sau Chrome

**"Cookie-uri nu se încarcă"** → Verifică că `cookies.json` nu este gol

---

## 📊 Status actual

- ✅ Docker oprit temporar
- ✅ Xvfb implementat (virtual display)
- ✅ Selenium-stealth activ
- ⏳ **URMEAZĂ: Rulează `python save_cookies.py`**
