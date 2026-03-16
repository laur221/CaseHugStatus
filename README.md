# 🎮 CasehugBot - Automated CS2 Case Opening Bot

**Automate free daily case openings on Casehug.com with intelligent 24-hour tracking per account**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- 🎯 **Multi-Account Support** - Manage multiple Steam accounts
- ⏰ **Individual 24h Tracking** - Each account tracked independently
- � **Smart Scheduler** - Calculates exact run time, runs only when needed (zero periodic checks)
- 👻 **Invisible Operation** - Runs silently in background with minimized Chrome
- 🔄 **Auto Steam Login** - Handles Steam OAuth automatically
- 🛄 **Smart Case Detection** - Auto-detects all available cases (Discord, Steam, + 13 level-based cases)
- 🎚️ **Level-Based Progression** - Automatically handles wood → iron → bronze → diamond → immortal
- 📊 **Skin Rarity Detection** - Extracts skins with rarity colors (⚪🔵🟣🩷🔴🟡)
- 📱 **Telegram Notifications** - Get notified when cases are opened
- 🛡️ **Cloudflare Bypass** - Automatic Cloudflare challenge solving
- 🌐 **Internet Check** - Only runs when internet is available
- 🔒 **Lock System** - Prevents multiple instances from running

## 📋 Requirements

- **Windows 10/11** (for Task Scheduler automation)
- **Python 3.8+**
- **Steam Account(s)** - Must own CS:GO/CS2 with sufficient playtime
- **Google Chrome** - Installed and up to date

## 🚀 Quick Start

### 1. Clone Repository

```bash
git clone https://github.com/yourusername/CasehugAuto.git
cd CasehugAuto
```

### 2. Install Dependencies

```bash
# Create virtual environment (recommended)
python -m venv .venv
.venv\Scripts\activate

# Install requirements
pip install -r requirements.txt
```

### 3. Run Setup Wizard

```bash
python setup.py
```

The wizard will guide you through:
- ✅ Adding Steam accounts
- ✅ Configuring Telegram notifications (optional)
- ✅ Setting up automatic scheduler

### 4. Test Run

```bash
python main.py
```

Watch the bot:
- Login to Steam automatically
- Check available cases
- Open cases
- Extract skin information from profile
- Send report to Telegram

### 5. Install Auto-Scheduler (Optional)

For fully automated daily runs:

```powershell
powershell -ExecutionPolicy Bypass -File install_task_new.ps1
```

This adds a Windows Task Scheduler entry that:
- **Calculates exact next run time** (last_opening + 24h + 1min)
- Runs **invisibly in background**
- **Zero periodic checks** = zero resource usage
- **Smart detection**: If PC starts late (e.g., next run was at 12:46, but PC started at 16:32) → **runs immediately**

## ⚙️ Configuration

### Main Config (`config.json`)

```json
{
  "accounts": [
    {
      "name": "Account 1",
      "steam_cookies": []
    }
  ],
  "telegram_token": "YOUR_BOT_TOKEN",
  "telegram_chat_id": "YOUR_CHAT_ID",
  "bypass_method": "nodriver_primary"
}
```

### Scheduler Config (`schedule_config.json`)

```json
{
  "enabled": true,
  "scheduler_mode": "smart",
  "check_interval_minutes": 5,
  "hours_between_runs": 24,
  "require_steam_login": true,
  "accounts_with_steam": ["Account 1", "Account 2"]
}
```

**Scheduler Modes:**

| Mode | Description | Resource Usage | Best For |
|------|-------------|----------------|----------|
| **`smart`** (default) | Calculates exact run time, runs only when needed | **Zero** - no periodic checks | Most users, laptops |
| **`periodic`** | Checks every X minutes (classic behavior) | Low - checks every 5min | 24/7 PCs, prefer constant monitoring |

**Config Parameters:**
- `scheduler_mode`: `"smart"` or `"periodic"` (default: `smart`)
- `check_interval_minutes`: For periodic mode - check every X minutes (default: 5)
- `hours_between_runs`: Hours between case openings (default: 24)
- `require_steam_login`: Check if Steam is running and logged in (default: true)
- `accounts_with_steam`: List of accounts that use Steam (empty = all accounts)

## 📱 Telegram Setup

1. **Create Bot:**
   - Message [@BotFather](https://t.me/BotFather) on Telegram
   - Send `/newbot` and follow instructions
   - Save the **bot token**

2. **Get Chat ID:**
   - Message [@userinfobot](https://t.me/userinfobot)
   - Save your **chat ID**

3. **Add to Config:**
   - Run `python setup.py` again
   - Or manually edit `config.json`

## 🎮 How It Works

### Individual Account Tracking

Each account is tracked independently:

```
Account 1: Opens at 10:00 AM → Next at 10:00 AM (24h later)
Account 2: Opens at 2:00 PM → Next at 2:00 PM (24h later)
Account 3: Opens at 8:00 PM → Next at 8:00 PM (24h later)
```

### Scheduler Logic

**Two Modes Available:**

#### 1. SMART Mode (Default - Zero Periodic Checks)

```
Scheduler starts (at logon / daily 00:01):
├─ Read last_opening.json
├─ Calculate exact next run time for each account:
│  └─ next_run = last_opening + 24h + 1min
├─ Find earliest next_run time
├─ If now >= next_run:
│  ├─ Check internet connection
│  ├─ Check Steam is running
│  └─ Launch bot → Open cases → Send report → EXIT
└─ Else: Display next run time and EXIT

**Example**: Account opened on March 7 at 12:45
→ Next run: March 8 at 12:46
→ If PC starts at March 8 at 16:32 (late): Runs immediately
```

#### 2. PERIODIC Mode (Classic - Check Every X Minutes)

```
Scheduler starts (at logon / daily 00:01):
└─ LOOP every 5 minutes:
   ├─ Read last_opening.json
   ├─ Check if 24h passed for each account
   ├─ If any account ready:
   │  ├─ Check internet connection
   │  ├─ Check Steam is running
   │  └─ Launch bot → Open cases → Send report → EXIT
   └─ Wait 5 minutes and repeat

**Example**: Account ready at 12:45
→ Next check: 12:50 (runs within 5 minutes of being ready)
```

### Case Opening Flow

```
1. Launch Chrome (minimized, muted)
2. Navigate to casehug.com/free-cases
3. Auto-login with Steam if needed
4. Auto-detect available cases:
   ├─ Always check: DISCORD, STEAM
   └─ Level-based (in order): WOOD → IRON → BRONZE → SILVER → GOLD
       → PLATINUM → EMERALD → DIAMOND → MASTER → CHALLENGER
       → LEGEND → MYTHIC → IMMORTAL
5. Open each available case (stops at first level-locked case)
6. Navigate to casehug.com/user-account
7. Extract NEW skins with rarity
8. Send Telegram report
9. Close browser
```

**Smart Detection Logic:**
- **Discord & Steam**: Always checked (not level-dependent)
- **Level cases**: Checked in progression order
  - If case is **🔒 locked** (level too low) → **STOP** (all higher cases are locked too)
  - If case is **⏰ on cooldown** → **CONTINUE** (higher cases might be available)
  - If case is **✅ available** → **OPEN** and continue

**Example**: Account at level 30
```
✅ DISCORD - Available
✅ STEAM - Available  
✅ WOOD (Level 0) - Available
✅ IRON (Level 12) - Available
✅ BRONZE (Level 24) - Available
🔒 SILVER (Level 32) - LOCKED → STOP
   (No need to check Gold/Platinum/etc.)
```

## 📊 Telegram Report Format

```
🎰 Casehug Daily Report
📅 06.03.2026 18:45:23
──────────────────────────────

Account 1 (Level 45)
⚪ DISCORD: G3SG1 | Jungle Dashed - $0.01
🔵 WOOD: MP7 | Groundwater - $0.05
🟣 STEAM: M4A4 | Neo-Noir - $8.50
🩷 BRONZE: AK-47 | Redline - $12.00
🔴 GOLD: AWP | Asiimov - $45.50

Account 2 (Level 5)
⚪ DISCORD: P250 | Sand Dune - $0.01
🔵 WOOD: Nova | Candy Apple - $0.03
❌ STEAM: Not available

──────────────────────────────
```

**Case Types:**
- **Discord** - Always available (Level 0)
- **Steam** - Requires Steam login (Level 0)
- **Wood** → **Iron** → **Bronze** → **Silver** → **Gold** → **Platinum** → **Emerald** → **Diamond** → **Master** → **Challenger** → **Legend** → **Mythic** → **Immortal** (Level 0-120)

**Rarity Colors:**
- ⚪ Consumer/Industrial (White/Gray)
- 🔵 Mil-Spec (Blue)
- 🟣 Restricted (Purple)
- 🩷 Classified (Pink)
- 🔴 Covert (Red)
- 🟡 Contraband/Gold (Yellow)

## 🛠️ Troubleshooting

### Bot doesn't start
```bash
# Check if Chrome is installed
where chrome

# Check Python version
python --version

# Reinstall dependencies
pip install -r requirements.txt --force-reinstall
```

### Multiple instances running
```bash
# Run cleanup script
FIX_MULTIPLE_INSTANCES.bat
```

### Steam login fails
- Make sure Steam is installed and you're logged in
- Browser may ask for Steam credentials - they'll be saved in profile

### Cloudflare blocks bot
- Bot uses Nodriver with stealth mode
- Usually bypasses Cloudflare in 10-15 seconds
- If blocked: wait a few minutes and try again

### Task Scheduler not working
```powershell
# Check task status
Get-ScheduledTask -TaskName "CasehugAutoScheduler"

# Reinstall task
powershell -ExecutionPolicy Bypass -File install_task_new.ps1
```

## 🔧 Advanced Usage

### Switch Between Scheduler Modes

**Switch to SMART mode** (exact time calculation, zero periodic checks):
```json
// schedule_config.json
{
  "scheduler_mode": "smart"
}
```
- ✅ Zero resource usage (no periodic checks)
- ✅ Runs immediately if PC starts late
- ✅ Best for laptops and daily-use PCs

**Switch to PERIODIC mode** (check every 5 minutes):
```json
// schedule_config.json
{
  "scheduler_mode": "periodic",
  "check_interval_minutes": 5
}
```
- ✅ Constant monitoring (classic behavior)
- ✅ Runs within 5 minutes of being ready
- ✅ Best for 24/7 PCs or servers

### Manual Run for Specific Account

Edit `config.json` temporarily to include only one account, then run:
```bash
python main.py
```

### Disable Telegram Notifications

Set empty strings in `config.json`:
```json
{
  "telegram_token": "",
  "telegram_chat_id": ""
}
```

### Run Without Scheduler

Just run manually whenever you want:
```bash
python main.py
```

The bot will track 24h intervals per account automatically.

## 📁 Project Structure

```
CasehugAuto/
├── main.py                      # Main bot logic
├── scheduler.py                 # Smart scheduler (exact time calculation)
├── setup.py                     # First-run configuration wizard
├── install_task_new.ps1         # Task Scheduler installer
├── run_scheduler_hidden.vbs     # Invisible execution wrapper
├── FIX_MULTIPLE_INSTANCES.bat   # Cleanup utility
├── requirements.txt             # Python dependencies
├── config.json                  # Main configuration (created by setup)
├── schedule_config.json         # Scheduler settings (created by setup)
├── last_opening.json            # Timestamp tracking (created by setup)
├── profiles/                    # Chrome profiles (auto-created)
│   ├── Account_1/
│   ├── Account_2/
│   └── ...
└── debug_output/                # Debug HTML files (auto-created)
```

## 🤝 Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/AmazingFeature`)
3. Commit your changes (`git commit -m 'Add some AmazingFeature'`)
4. Push to the branch (`git push origin feature/AmazingFeature`)
5. Open a Pull Request

## ⚠️ Disclaimer

This bot is for educational purposes only. Use at your own risk. The authors are not responsible for:
- Account bans or restrictions
- Loss of items or skins
- Any violations of Casehug.com Terms of Service

**Always use responsibly and respect website terms of service.**

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- [Nodriver](https://github.com/ultrafunkamsterdam/nodriver) - Undetected Chrome automation
- [psutil](https://github.com/giampaolo/psutil) - Process management
- Casehug.com - CS2 case opening platform

## 📞 Support

- 🐛 **Issues:** [GitHub Issues](https://github.com/laur221/CaseHugStatus/issues)

---

**Made with ❤️ for the CS2 community**

## 📦 Windows Release (EXE + Installer)

Build a distributable executable and optional installer:

```bash
python scripts/build_release.py
```

Build only executable (skip installer):

```bash
python scripts/build_release.py --skip-installer
```

Artifacts:
- `dist/CaseHugAuto.exe`
- `dist/installer/CaseHugAuto-Setup.exe` (if Inno Setup is installed)

Installer script location:
- `installer/CaseHugAuto.iss`

## 🗂️ Data Directory

By default, application data is stored per-user in:
- Windows: `%APPDATA%\CaseHugAuto`

You can override storage location:
- Command line: `CaseHugAuto.exe --data-dir "D:\MyCaseHugData"`
- Environment variable: `CASEHUGAUTO_HOME=D:\MyCaseHugData`

This folder contains logs, profiles, runtime config and state files.
