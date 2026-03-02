# 🔐 Configurare 2Captcha pentru Bypass Cloudflare Automat

## Ce este 2Captcha?

2Captcha este un serviciu care rezolvă automat challengeuri CAPTCHA (inclusiv Cloudflare Turnstile) folosind inteligență artificială și workeri umani. 

**Costuri:** ~$1-2 per 1000 de rezolvări. Pentru bot-ul nostru: ~360 rezolvări/lună = **$0.36-0.72/lună**.

## 📋 Pași pentru Configurare

### 1. Creează Cont pe 2Captcha

1. Mergi la [https://2captcha.com](https://2captcha.com?from=16573352)
2. Fă click pe "Sign Up" (dreapta sus)
3. Completează formularul de înregistrare
4. Verifică email-ul (confirmă contul)

### 2. Adaugă Fonduri în Cont

1. Login pe [https://2captcha.com](https://2captcha.com)
2. Click pe "Add Funds" sau "Deposit"
3. Alege metoda de plată:
   - **Card bancar** (Visa/Mastercard)
   - **Crypto** (Bitcoin, USDT, etc.) - RECOMANDAT pentru anonimat
   - **PayPal** (dacă disponibil în țara ta)
   - **Webmoney, Perfect Money**, etc.
4. Depune **$2-5** pentru început (suficient pentru ~2000-5000 rezolvări)

### 3. Obține API Key

1. După login, mergi la [https://2captcha.com/setting](https://2captcha.com/setting)
2. Secțiunea "API Key" - copiază cheia (ex: `abc123def456...`)
3. **NU DISTRIBUI această cheie cu nimeni!**

### 4. Configurează Bot-ul

Deschide fișierul `config.json` și înlocuiește:

```json
"2captcha_api_key": "YOUR_API_KEY_HERE"
```

Cu cheia ta reală:

```json
"2captcha_api_key": "abc123def456ghi789jkl012mno345pqr678"
```

### 5. Testează!

Rulează bot-ul normal:

```bash
py -3.11 main.py
```

**Când bot-ul detectează Cloudflare:**
- ✅ **Cu API key configurat:** Rezolvare AUTOMATĂ în 10-30 secunde
- ⏰ **Fără API key:** Așteaptă rezolvare manuală (180 secunde)

## 📊 Cum Funcționează?

```
┌─────────────────────────────────────────────────────────┐
│ 1. Bot detectează Cloudflare Turnstile                 │
│    "⚠️ CLOUDFLARE TURNSTILE DETECTAT!"                 │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 2. Bot extrage "sitekey" din pagina HTML               │
│    🔑 Sitekey găsit: 0x4AAAAAAA...                     │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 3. Bot trimite challenge la 2Captcha API               │
│    🔐 Trimit challenge la 2Captcha...                  │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼ (10-30 secunde)
┌─────────────────────────────────────────────────────────┐
│ 4. 2Captcha rezolvă și returnează token                │
│    ✅ Token primit: eyJ0eXAiOiJKV1QiLCJhbGc...        │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 5. Bot injectează token în pagină                      │
│    💉 Injectez token în pagină...                      │
└──────────────────┬──────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│ 6. Cloudflare verifică token și permite accesul        │
│    ✅ Cloudflare trecut cu 2Captcha!                   │
└─────────────────────────────────────────────────────────┘
```

## 💰 Prețuri 2Captcha (Februarie 2026)

| Tip CAPTCHA            | Preț per 1000      | Cost Bot (360/lună) |
|------------------------|--------------------|---------------------|
| **Turnstile Normal**   | $1.00 - $1.50      | $0.36 - $0.54       |
| Turnstile Managed      | $2.00 - $3.00      | $0.72 - $1.08       |
| reCAPTCHA v2           | $1.00              | $0.36               |
| reCAPTCHA v3           | $2.00              | $0.72               |

**Notă:** Cloudflare Turnstile pe casehug.com este tip "Normal" → Cost lunar: **$0.36-0.54**

## 🔍 Verificare Sold și Statistici

### Verifică Soldul Curent:

1. Login pe [https://2captcha.com](https://2captcha.com)
2. Dashboard-ul arată: **"Balance: $X.XX"**

### Statistici Utilizare:

1. Mergi la [https://2captcha.com/statistic](https://2captcha.com/statistic)
2. Vezi:
   - Număr rezolvări astăzi/săptămâna asta/luna asta
   - Cost total
   - Success rate
   - Timp mediu de rezolvare

### Alerte Sold Mic:

2Captcha trimite email automat când soldul < $0.50

## ⚙️ Setări Avansate (Opțional)

În `main.py`, poți customiza comportamentul 2Captcha:

```python
# Linia ~220: solve_turnstile_with_2captcha()

result = self.captcha_solver.turnstile(
    sitekey=sitekey,
    url=url,
    # OPȚIONAL: Adaugă aceste parametri
    # action='login',  # Specifică acțiunea (dacă știi)
    # data='custom_data',  # Date custom (dacă necesare)
)
```

## 🛠️ Troubleshooting

### ❌ "2Captcha API key lipsește"

**Cauză:** API key nu e configurat în `config.json`

**Soluție:** 
1. Deschide `config.json`
2. Înlocuiește `"YOUR_API_KEY_HERE"` cu cheia ta reală
3. Salvează fișierul

### ❌ "Eroare 2Captcha: ERROR_WRONG_USER_KEY"

**Cauză:** API key invalid sau copiat greșit

**Soluție:**
1. Verifică pe [https://2captcha.com/setting](https://2captcha.com/setting)
2. Re-copiază API key-ul (fără spații la început/sfârșit)
3. Actualizează `config.json`

### ❌ "Eroare 2Captcha: ERROR_ZERO_BALANCE"

**Cauză:** Sold epuizat

**Soluție:**
1. Adaugă fonduri: [https://2captcha.com/pay](https://2captcha.com/pay)
2. Așteaptă 1-2 minute ca soldul să se actualizeze

### ❌ "Nu am găsit sitekey"

**Cauză:** Cloudflare folosește o versiune diferită sau sitekey-ul e ascuns

**Soluție:**
1. Bot-ul va trece automat la rezolvare manuală
2. Sau: Inspectează manual pagina în DevTools și găsește `data-sitekey`
3. Raportează problema (pot actualiza codul)

### ❌ "Token injectat dar Cloudflare încă activ"

**Cauză:** Token expirat, invalid sau Cloudflare cere challenge suplimentar

**Soluție:**
1. Așteaptă 10-15 secunde (bot-ul încearcă automat)
2. Dacă persistă, rezolvă manual (bot intră în mod fallback)
3. Verifică log-urile pentru erori specifice

## 📈 Optimizări pentru Cost Redus

### 1. **Folosește Profile Persistente** (DEJA IMPLEMENTAT ✅)
   - După prima autentificare, browser-ul salvează cookies
   - Cloudflare apare doar la prima rulare sau după 24h
   - **Economie:** 80-90% din rezolvări evitate

### 2. **Rulează Bot-ul Mai Rar**
   - În loc de la fiecare 6 ore → 1x pe zi (dimineața)
   - **Economie:** Cost redus cu 75%

### 3. **Folosește VPN Stabil**
   - Windscribe ($3/lună) reduce frecvența Cloudflare
   - IP rezidențial → mai puține challengeuri

### 4. **Monitorizează Success Rate**
   - Dacă success rate < 80%, contactează 2Captcha support
   - Pot oferi refund pentru rezolvări eșuate

## 🆘 Suport

### 2Captcha Support:
- **Email:** support@2captcha.com
- **Live Chat:** [https://2captcha.com](https://2captcha.com) (dreapta jos)
- **Telegram:** @rucaptcha_support
- **Documentație:** [https://2captcha.com/api-docs](https://2captcha.com/api-docs)

### Bot Support (Mine):
- Verifică log-urile din terminal pentru erori detaliate
- Fișierele debug se salvează în `debug_output/`

## 🎯 Rezumat

| ✅ AVANTAJE                          | ❌ DEZAVANTAJE                    |
|--------------------------------------|-----------------------------------|
| Rezolvare 100% automată              | Cost mic (~$0.50/lună)            |
| Success rate 80-90%                  | Necesită cont cu sold            |
| Timp rezolvare: 10-30 secunde        | Token poate expira (rar)         |
| Funcționează 24/7                    | Depinde de serviciu extern       |
| Fallback la manual dacă eșuează      |                                   |
| API oficial și legal                 |                                   |

---

**🎉 Gata! Bot-ul tău acum rezolvă automat Cloudflare Turnstile! 🚀**
