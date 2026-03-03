# 🎯 SISTEM NOU: Tracking Individual Per Cont

## Ce s-a schimbat?

**ÎNAINTE:**
- Rulare la o oră fixă (ex: 10:00)
- Trebuia să ai laptopul pornit exact la ora aia
- Dacă îl pornești la 12:00, pierdeai ziua

**ACUM:**
- ✅ **Tracking individual** pentru fiecare cont
- ✅ **Flexibil**: deschizi când vrei (la 9:00, 12:00, 15:00, etc)
- ✅ **Automat**: botul ține minte ora exactă și deschide după 24h
- ✅ **Economie resurse**: se închide singur după ce termină

## Cum funcționează?

### 1️⃣ **Prima deschidere**
Rulezi manuat botul CÂND VREI TU:
```powershell
python main.py
```

**Exemplu:**
- Cont 1: deschis la **09:15**
- Cont 2: deschis la **09:16**
- Cont 3: deschis la **09:17**
- Cont 4: deschis la **09:18**

👉 Timestamp-ul este salvat automat în `last_opening.json`

### 2️⃣ **Următoarele deschideri (automate)**

Scheduler-ul **verifică la fiecare 5 minute** dacă au trecut 24h:

- **Dag 1, ora 09:15**: Cont 1 deschis manual
- **Dag 2, ora 09:00**: Scheduler verifică → încă 15 minute → așteapţă
- **Dag 2, ora 09:15**: Scheduler verifică → **24h trecute** → **DESCHIDE AUTOMAT**
- **Dag 2, ora 09:16**: Cont 2 pregătit → **DESCHIDE AUTOMAT**
- ...și așa mai departe pentru fiecare cont

### 3️⃣ **Instalare Scheduler (o singură dată)**

Rulează ca Administrator:
```powershell
.\install_task.ps1 install
```

Asta va:
- Crea task în Windows Task Scheduler
- Pornește automat la boot
- Verifică la fiecare 5 minute
- Se închide automat după procesare (nu consumă resurse inutil)

## ⚙️ Configurare

### `last_opening.json` (SE ACTUALIZEAZĂ AUTOMAT)
```json
{
  "Cont 1": {
    "last_opening": "2026-03-03T09:15:23",  ← Ora exactă
    "last_check": "2026-03-03T09:15:23"
  },
  ...
}
```

### `schedule_config.json`
```json
{
  "enabled": true,
  "check_interval_minutes": 5,        ← Verifică la 5 minute
  "hours_between_runs": 24,           ← 24h între deschideri
  "require_steam_login": true,        ← Verifică Steam
  "accounts_with_steam": [            ← Conturile cu Steam
    "Cont 1", "Cont 2", "Cont 3", "Cont 4"
  ]
}
```

## 📊 Verificare Status

**Rulează scheduler-ul manual pentru a vedea status:**
```powershell
python scheduler.py
```

**Va afișa:**
```
📊 Status conturi:
   ✅ Cont 1: READY (au trecut 24.5h)
   ⏳ Cont 2: 2.3h până la următoarea deschidere
   ✅ Cont 3: READY (au trecut 25.1h)
   ⏳ Cont 4: 18.7h până la următoarea deschidere
```

## 🎮 Exemple Reale

### Exemplu 1: Flexibilitate Completă
```
Luni 09:00    → Deschizi manual (prima dată)
Marți 09:00   → Scheduler deschide automat
Marți 15:00   → Pornești laptopul (scheduler e activ)
Marți 15:05   → Scheduler verifică: "încă 18h până la 24h" → așteaptă
Miercuri 09:05 → Scheduler verifică: "24h trecute!" → DESCHIDE AUTOMAT
```

### Exemplu 2: Pornești laptopul mai târziu
```
Luni 09:00    → Prima deschidere
Marți 09:00   → Scheduler ar trebui să deschidă, dar laptopul e închis
Marți 12:00   → Pornești laptopul
Marți 12:05   → Scheduler verifică: "au trecut 27h!" → DESCHIDE IMEDIAT
Miercuri 12:05 → Următoarea deschidere (după 24h de la 12:00)
```

## 🔧 Comenzi Utile

### Pornire manuală (test)
```powershell
python main.py
```

### Pornire scheduler (verificare continuă)
```powershell
python scheduler.py
```

### Instalare Task Scheduler
```powershell
.\install_task.ps1 install
```

### Dezinstalare Task Scheduler
```powershell
.\install_task.ps1 uninstall
```

### Status Task Scheduler
```powershell
Get-ScheduledTask -TaskName "CasehugBot Scheduler"
```

## ✨ Avantaje Sistem Nou

1. **Flexibilitate Totală**
   - Nu mai ești legat de o oră fixă
   - Deschizi când ai timp, botul continuă automat

2. **Economie Resurse**
   - Scheduler-ul se închide după procesare
   - Nu consumă RAM/CPU când nu lucrează
   - Task Scheduler îl repornește automat la 5 minute

3. **Tracking Precis**
   - Știi exact când s-a deschis fiecare cont
   - Verificări la nivel individual (nu global)
   - Logs clare pentru debugging

4. **Browser Minimizat**
   - Browsere minimizate automat în taskbar
   - Nu întrerupe gaming-ul sau alte activități
   - Complet funcțional în background

## 🐛 Troubleshooting

**Scheduler nu pornește?**
```powershell
# Verifică dacă task-ul există
Get-ScheduledTask -TaskName "CasehugBot Scheduler"

# Pornește manual
Start-ScheduledTask -TaskName "CasehugBot Scheduler"
```

**Verifică logs:**
```powershell
# Rulează scheduler manual pentru a vedea ce se întâmplă
python scheduler.py
```

**Resetare timestamp (test)**
```
Editează last_opening.json și pune null la "last_opening"
Pentru a forța deschiderea imediată
```

## 📝 Note Importante

- ⚠️ **Prima rulare** trebuie făcută **MANUAL** (`python main.py`)
- ⚠️ **Steam** trebuie să fie **pornit și logat** (dacă conturile folosesc Steam)
- ✅ Browserele sunt **minimizate automat** (nu apar pe ecran)
- ✅ Sistemul **salvează automat** timestamp-ul după fiecare deschidere
- ✅ **Nu e nevoie** să faci nimic manual după instalarea Task Scheduler

## 🎯 TL;DR (Rezumat Rapid)

1. **Prima dată**: Rulează `python main.py` când vrei
2. **Instalare**: `.\install_task.ps1 install` (ca Admin)
3. **Gata!** Sistemul va deschide automat după 24h pentru fiecare cont
4. **Flexibil**: Pornești laptopul când vrei, botul se adaptează
5. **Economie**: Se închide singur după ce termină

---

**Creat:** 3 Martie 2026  
**Versiune:** 2.0 - Tracking Individual
