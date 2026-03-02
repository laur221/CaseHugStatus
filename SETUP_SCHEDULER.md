# 🚀 CasehugBot - Configurare Rulare Automată Background

## 📋 Prezentare Generală

Sistemul de scheduler permite rularea automată a botului în background, cu următoarele caracteristici:

- ⏰ **Rulare programată zilnică** la ora dorită (ex: 10:00 AM)
- 🔄 **Verificare automată** la fiecare 5 minute
- 🎮 **Verificare Steam login** înainte de rulare
- ⏱️ **Protecție interval 23h** - împiedică rulări multiple pe zi
- 🪟 **Background complet** - fără ferestre vizibile
- 🔁 **Restart automat** la pornirea laptop-ului

---

## 🛠️ Configurare Inițială

### 1. Editează Configurația Scheduler

Deschide fișierul `schedule_config.json` și configurează:

```json
{
  "enabled": true,
  "run_time": "10:00",                    // Schimbă cu ora dorită (format 24h)
  "require_steam_login": true,            // true = așteaptă Steam logat
  "accounts_with_steam": [
    "Cont 1",                              // Conturile care folosesc Steam
    "Cont 2"
  ]
}
```

### 2. Adaugă Steam la Conturile Dorite

Deschide `config.json` și modifică `available_cases`:

```json
{
  "name": "Cont 1",
  "profile_dir": "profile_1",
  "available_cases": ["discord", "steam", "wood"]  // Adaugă "steam"
}
```

### 3. Autentificare Manuală Steam

**IMPORTANT:** Înainte de prima rulare automată, trebuie să te autentifici manual pe casehug.com cu fiecare cont Steam:

1. Pornește Steam și loghează-te
2. Deschide Chrome/Edge în modul normal
3. Navighează la https://casehug.com
4. Apasă "Login with Steam" pentru fiecare cont
5. Steam va crea cookies de autentificare
6. Aceste cookies vor fi salvate de Nodriver în `profiles/Cont_X/`

---

## 🪟 Configurare Task Scheduler Windows

### Metoda 1: Rulare PowerShell (Recomandat)

Rulează în PowerShell ca Administrator:

```powershell
# Schimbă calea cu directorul tău
$scriptPath = "D:\github\CasehugAuto\run_scheduler.bat"
$taskName = "CasehugBot Scheduler"

# Creează task care pornește la boot
$action = New-ScheduledTaskAction -Execute $scriptPath
$trigger = New-ScheduledTaskTrigger -AtStartup
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries -StartWhenAvailable
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERNAME" -LogonType Interactive -RunLevel Highest

# Înregistrează task
Register-ScheduledTask -TaskName $taskName -Action $action -Trigger $trigger -Settings $settings -Principal $principal -Force

Write-Host "✅ Task Scheduler configurat cu succes!"
```

### Metoda 2: Interface Grafică Task Scheduler

1. Apasă **Win + R**, scrie `taskschd.msc` și apasă Enter
2. Click dreapta pe **Task Scheduler Library** → **Create Task...**

#### ⚙️ Tab "General"
- **Name:** `CasehugBot Scheduler`
- **Description:** `Rulare automată zilnică CasehugBot cu verificare Steam`
- ☑️ **Run whether user is logged on or not**
- ☑️ **Run with highest privileges**
- **Configure for:** Windows 10/11

#### 🔀 Tab "Triggers"
Click **New...** și configurează:
- **Begin the task:** `At startup`
- ☑️ **Enabled**
- Click **OK**

#### ⚡ Tab "Actions"
Click **New...** și configurează:
- **Action:** `Start a program`
- **Program/script:** `D:\github\CasehugAuto\run_scheduler.bat` (schimbă calea!)
- **Start in:** `D:\github\CasehugAuto` (folder-ul proiectului)
- Click **OK**

#### ⚙️ Tab "Conditions"
- ☐ **Start the task only if the computer is on AC power** (debifare)
- ☑️ **Wake the computer to run this task**

#### ⚙️ Tab "Settings"
- ☑️ **Allow task to be run on demand**
- ☑️ **Run task as soon as possible after a scheduled start is missed**
- ☐ **Stop the task if it runs longer than** (debifare)
- **If the running task does not end when requested:** `Do not stop`

3. Click **OK** pentru a salva

---

## ✅ Testare Scheduler

### Test Manual (Fără Task Scheduler)

```powershell
cd D:\github\CasehugAuto
python scheduler.py
```

Output așteptat:
```
╔═══════════════════════════════════════════════════════════╗
║           CASEHUGBOT SCHEDULER - PORNIT                   ║
╚═══════════════════════════════════════════════════════════╝

📋 Configurație:
   ⏰ Oră programată: 10:00
   🔄 Verificare la fiecare: 5 minute
   🎮 Steam necesar: DA
   📦 Conturi Steam: Cont 1, Cont 2
   ⏱️  Interval minim: 23h
```

### Test Task Scheduler

În Task Scheduler:
1. Găsește task-ul **CasehugBot Scheduler**
2. Click dreapta → **Run**
3. Verifică în **History** tab dacă a pornit corect

---

## 🎮 Workflow Zilnic

### 🌅 Dimineața (După Pornirea Laptop-ului)

1. **Laptop pornește** → Task Scheduler pornește automat `scheduler.py`
2. **Scheduler verifică** la fiecare 5 minute:
   - ✅ Este ora programată? (ex: 10:00)
   - ✅ Au trecut min. 23h de la ultima rulare?
   - ✅ Steam este pornit și logat?
3. **Când toate condițiile sunt îndeplinite:**
   - 🚀 Scheduler pornește `main.py`
   - 🤖 Botul procesează toate conturile (Discord, Steam, Wood)
   - 💾 Salvează timestamp-ul curent
   - 📊 Trimite raport pe Telegram
4. **Scheduler continuă să ruleze în background** și va verifica din nou mâine

### 🔴 Dacă Steam NU este logat

```
⚠️  AȘTEPT AUTENTIFICARE STEAM
   💡 Te rog să pornești Steam și să te loghezi
   🔄 Voi verifica din nou în 5 minute...
```

**Soluție:**
1. Pornește Steam
2. Loghează-te cu contul tău
3. Scheduler va detecta automat și va rula botul

---

## 📂 Fișiere Generate

| Fișier | Descriere |
|--------|-----------|
| `last_run.txt` | Timestamp ultima rulare (previne rulări multiple) |
| `schedule_config.json` | Configurație scheduler (oră, conturi Steam) |
| `profiles/Cont_X/` | Cookie-uri Steam salvate pentru fiecare cont |
| `debug_output/` | HTML/PNG debug dacă apar erori |

---

## 🔧 Troubleshooting

### Scheduler nu pornește la boot

```powershell
# Verifică dacă task-ul există
Get-ScheduledTask -TaskName "CasehugBot Scheduler"

# Verifică status
Get-ScheduledTask -TaskName "CasehugBot Scheduler" | Get-ScheduledTaskInfo

# Pornește manual
Start-ScheduledTask -TaskName "CasehugBot Scheduler"
```

### Steam nu este detectat

- ✅ Verifică că Steam este pornit (vezi in System Tray)
- ✅ Steam trebuie să fie **logat** (nu doar pornit)
- ✅ Verifică că calea Steam este corectă: `C:\Program Files (x86)\Steam`

### Botul rulează de 2 ori pe zi

- Șterge `last_run.txt` doar dacă vrei să forțezi o nouă rulare
- Crește `min_hours_between_runs` în `schedule_config.json` la 24

### Vreau să opresc scheduler-ul temporar

**Opțiune 1 - Dezactivează în config:**
```json
{
  "enabled": false
}
```

**Opțiune 2 - Dezactivează Task Scheduler:**
```powershell
Disable-ScheduledTask -TaskName "CasehugBot Scheduler"
```

---

## 💡 Tips & Tricks

### Schimbă Ora Programată

Editează `schedule_config.json`:
```json
{
  "run_time": "14:30"  // Va rula zilnic la 14:30
}
```

### Rulare Imediată la Pornire (Prima Dată)

```json
{
  "run_on_startup": true  // Va rula imediat, apoi va respecta programul
}
```

### Vezi Loguri Scheduler

Scheduler-ul printează în consolă. Pentru a vedea output-ul:

1. Schimbă în `run_scheduler.bat`:
   ```batch
   python scheduler.py > scheduler_log.txt 2>&1
   ```

2. Verifică fișierul `scheduler_log.txt`

### Notificări Telegram

Raportul zilnic este trimis automat pe Telegram după fiecare rulare cu succes.

---

## ⚡ Comenzi Rapide

```powershell
# Test manual scheduler
python scheduler.py

# Test manual bot (o singură rulare)
python main.py

# Verifică Task Scheduler status
Get-ScheduledTask -TaskName "CasehugBot Scheduler"

# Pornește task manual
Start-ScheduledTask -TaskName "CasehugBot Scheduler"

# Oprește task
Stop-ScheduledTask -TaskName "CasehugBot Scheduler"

# Șterge task
Unregister-ScheduledTask -TaskName "CasehugBot Scheduler" -Confirm:$false
```

---

## 📞 Suport

Dacă întâmpini probleme:
1. Verifică `last_run.txt` - vezi când a rulat ultima dată
2. Verifică `schedule_config.json` - configurație corectă?
3. Pornește manual: `python scheduler.py` - vezi erori?
4. Verifică Task Scheduler History tab
5. Verifică `debug_output/` pentru erori Cloudflare

---

**Succes cu automatizarea! 🚀**
