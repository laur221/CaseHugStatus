# 🎮 CasehugBot - Automated CS2 Case Opening Bot

**Automate free daily case openings on Casehug.com with intelligent 24-hour tracking per account**

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## ✨ Features

- 🎯 **Multi-Account Support** - Manage multiple Steam accounts
- ⏰ **Individual 24h Tracking** - Each account tracked independently
- 🤖 **Automated Scheduler** - Checks every 5 minutes, runs when ready
- 👻 **Invisible Operation** - Runs silently in background with minimized Chrome
- 🔄 **Auto Steam Login** - Handles Steam OAuth automatically
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
- Checks every **5 minutes** if any account is ready (24h passed)
- Runs **invisibly in background**
- Opens cases **automatically** when ready

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
  "check_interval_minutes": 5,
  "hours_between_runs": 24,
  "require_steam_login": true,
  "accounts_with_steam": ["Account 1", "Account 2"]
}
```

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

```
Every 5 minutes:
├─ Read last_opening.json (0.01s - instant)
├─ Check if 24h passed for each account
├─ Check internet connection
├─ Check Steam is running
└─ If ready: Launch bot → Open cases → Send report
```

### Case Opening Flow

```
1. Launch Chrome (minimized, muted)
2. Navigate to casehug.com/free-cases
3. Auto-login with Steam if needed
4. Check available cases (DISCORD, STEAM, WOOD)
5. Open each available case
6. Navigate to casehug.com/user-account
7. Extract NEW skins with rarity
8. Send Telegram report
9. Close browser
```

## 📊 Telegram Report Format

```
🎰 Casehug Daily Report
📅 06.03.2026 18:45:23
──────────────────────────────

Account 1
⚪ DISCORD: G3SG1 | Jungle Dashed - $0.01
🔵 WOOD: MP7 | Groundwater - $0.05
🟣 STEAM: M4A4 | Neo-Noir - $8.50

Account 2
❌ No new skins

──────────────────────────────
```

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

### Manual Run for Specific Account

Edit `config.json` temporarily to include only one account, then run:
```bash
python main.py
```

### Change Check Interval

Edit `schedule_config.json`:
```json
{
  "check_interval_minutes": 10  // Check every 10 minutes instead of 5
}
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
├── scheduler.py                 # Auto-scheduler (5min checks)
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
- 💬 **Discussions:** [GitHub Discussions](https://github.com/laur221/CaseHugStatus/discussions)

---

**Made with ❤️ for the CS2 community**
