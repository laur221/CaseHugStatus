#!/usr/bin/env python3
"""
CasehugBot - First Run Setup Wizard
Configures accounts, Telegram notifications, and scheduler settings
"""

import json
import os
import sys
from pathlib import Path

def print_header():
    """Print welcome header"""
    print("\n" + "="*60)
    print("🎮 CASEHUGBOT - FIRST RUN SETUP")
    print("="*60 + "\n")

def print_section(title):
    """Print section header"""
    print("\n" + "-"*60)
    print(f"📋 {title}")
    print("-"*60 + "\n")

def get_input(prompt, default=None, required=True):
    """Get user input with optional default"""
    if default:
        full_prompt = f"{prompt} [{default}]: "
    else:
        full_prompt = f"{prompt}: "
    
    while True:
        value = input(full_prompt).strip()
        
        if value:
            return value
        elif default:
            return default
        elif not required:
            return ""
        else:
            print("❌ This field is required. Please enter a value.")

def get_yes_no(prompt, default="y"):
    """Get yes/no input"""
    while True:
        value = input(f"{prompt} [y/n, default={default}]: ").strip().lower()
        
        if not value:
            value = default
        
        if value in ['y', 'yes']:
            return True
        elif value in ['n', 'no']:
            return False
        else:
            print("❌ Please enter 'y' or 'n'")

def setup_accounts():
    """Configure Steam accounts"""
    print_section("STEAM ACCOUNTS SETUP")
    print("ℹ️  You can configure multiple Steam accounts")
    print("   Each account will be checked independently every 24 hours\n")
    
    accounts = []
    account_num = 1
    
    while True:
        print(f"\n{'─'*40}")
        print(f"Account #{account_num}")
        print(f"{'─'*40}\n")
        
        name = get_input(f"Account name", f"Account {account_num}")
        
        # Account configuration
        account = {
            "name": name,
            "steam_cookies": []  # Will be set automatically on first run
        }
        
        accounts.append(account)
        
        if not get_yes_no(f"\n➕ Add another account?", "n"):
            break
        
        account_num += 1
    
    print(f"\n✅ Configured {len(accounts)} account(s)")
    return accounts

def setup_telegram():
    """Configure Telegram notifications"""
    print_section("TELEGRAM NOTIFICATIONS")
    print("ℹ️  Get Telegram notifications when cases are opened")
    print("   To get your bot token and chat ID:")
    print("   1. Message @BotFather on Telegram to create a bot")
    print("   2. Message @userinfobot to get your chat ID\n")
    
    if not get_yes_no("Enable Telegram notifications?", "y"):
        return None, None
    
    token = get_input("Bot Token (from @BotFather)")
    chat_id = get_input("Chat ID (from @userinfobot)")
    
    return token, chat_id

def setup_scheduler():
    """Configure scheduler settings"""
    print_section("AUTO-SCHEDULER CONFIGURATION")
    print("ℹ️  Bot will check every 5 minutes if 24 hours have passed")
    print("   Cases will open automatically when ready\n")
    
    enabled = get_yes_no("Enable automatic scheduler?", "y")
    
    hours_between = get_input("Hours between runs", "24")
    try:
        hours_between = int(hours_between)
    except:
        hours_between = 24
    
    return {
        "enabled": enabled,
        "check_interval_minutes": 5,
        "hours_between_runs": hours_between,
        "require_steam_login": True
    }

def create_config_files(accounts, telegram_token, telegram_chat_id, scheduler_config):
    """Create configuration files"""
    print_section("CREATING CONFIGURATION FILES")
    
    # Main config
    config = {
        "accounts": accounts,
        "telegram_token": telegram_token or "",
        "telegram_chat_id": telegram_chat_id or "",
        "bypass_method": "nodriver_primary"
    }
    
    with open("config.json", "w", encoding="utf-8") as f:
        json.dump(config, f, indent=2)
    print("✅ Created config.json")
    
    # Scheduler config
    scheduler_config["accounts_with_steam"] = [acc["name"] for acc in accounts]
    
    with open("schedule_config.json", "w", encoding="utf-8") as f:
        json.dump(scheduler_config, f, indent=2)
    print("✅ Created schedule_config.json")
    
    # Last opening tracking
    last_opening = {}
    for account in accounts:
        last_opening[account["name"]] = {
            "last_opening": None,
            "last_check": None
        }
    
    with open("last_opening.json", "w", encoding="utf-8") as f:
        json.dump(last_opening, f, indent=2)
    print("✅ Created last_opening.json")

def print_next_steps():
    """Print next steps after setup"""
    print_section("NEXT STEPS")
    print("1️⃣  Test the bot:")
    print("   python main.py\n")
    print("2️⃣  Install Windows Task Scheduler (runs automatically):")
    print("   powershell -ExecutionPolicy Bypass -File install_task_new.ps1\n")
    print("3️⃣  Or run manually when needed:")
    print("   python main.py\n")
    print("📚 For more information, see README.md\n")

def main():
    """Main setup function"""
    print_header()
    
    # Check if already configured
    if os.path.exists("config.json"):
        print("⚠️  Configuration already exists!")
        if not get_yes_no("Do you want to reconfigure?", "n"):
            print("\n✅ Setup cancelled. Your existing configuration is untouched.")
            return
        print("")
    
    try:
        # Setup steps
        accounts = setup_accounts()
        telegram_token, telegram_chat_id = setup_telegram()
        scheduler_config = setup_scheduler()
        
        # Create config files
        create_config_files(accounts, telegram_token, telegram_chat_id, scheduler_config)
        
        # Print next steps
        print_next_steps()
        
        print("="*60)
        print("🎉 SETUP COMPLETE!")
        print("="*60 + "\n")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Setup cancelled by user.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Error during setup: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
