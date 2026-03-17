# CaseHugAuto

CaseHugAuto is a desktop app that automates free case opening on casehug.com across multiple accounts, tracks skins, and keeps account statistics in PostgreSQL.

## What The App Does

- Manages multiple accounts in one place
- Checks each active account cooldown independently (24h per account)
- Opens available free cases automatically when cooldown is passed
- Imports newly obtained skins with price and rarity metadata
- Stores account, skin, and run data in PostgreSQL
- Supports optional Telegram notifications
- Can run headless in background and start with Windows

## Main Features

- Multi-account workflow with per-account status
- Smart cooldown handling (24h logic anchored to last successful case opening)
- Periodic cooldown checks (configurable interval in minutes)
- Headless background worker mode
- Steam login flow handling with retries
- Newest-first skin listing and account filters
- Data folder and browser profile folder relocation from Settings
- Automatic log cleanup for old log files

## Installation (No Terminal Required)

1. Run `CaseHugAuto-Setup.exe`.
2. Choose the install location.
3. Optionally enable desktop shortcut creation.
4. Finish installation and launch CaseHugAuto.

Release artifacts:
- `dist/CaseHugAuto.exe`
- `dist/installer/CaseHugAuto-Setup.exe`

## First-Time Setup In App

### 1) Database Connection
Open `Settings` -> `Database Connection` and configure PostgreSQL credentials.

### 2) Accounts
Open `Accounts`, add your accounts, and set the accounts you want automated to `Active`.

### 3) Bot Configuration
Open `Settings` -> `Bot Configuration` and configure:
- `Cooldown check interval (minutes)` (for example: `10`)
- `Max retries`
- `Steam login retries`
- `Start headless background worker with Windows` (enable if you want background auto-start)
- Optional auto-start flags for account processing behavior

### 4) Notifications (Optional)
Open `Settings` -> `Notifications` and configure Telegram token/chat ID if required.

## Background Automation Behavior

When background worker is enabled:
- The worker starts automatically with Windows (headless)
- Only active accounts are processed
- Every interval, the worker checks if 24h has passed for each account
- If cooldown is not passed, it waits until next check
- If cooldown is passed, it runs automation immediately for that account
- After successful case opening, cooldown is reset for that account

## Data And Logs

Default runtime data location on Windows:
- `%APPDATA%\\CaseHugAuto`

From `Settings` -> `Bot Configuration` you can change:
- Data folder (app data, logs, local config)
- Profiles folder (browser sessions)

This helps when the C: drive is low on space.

## Troubleshooting

### Desktop shortcut is missing after install
Use the latest installer and enable desktop shortcut during setup.

### Accounts are not opening cases
Check:
- Account is set to `Active`
- Database connection is valid
- 24h cooldown has passed for that account
- Background worker is enabled if you expect Windows auto-start

### Steam login keeps failing
Increase `Steam login retries` in `Settings` -> `Bot Configuration`.

## Language Policy

Application UI text is English-only.
