#!/usr/bin/env python3
"""
CasehugBot Smart Scheduler - Calculates exact time for the next runs
Runs ONLY when needed (no periodic checks)
Example: opened on March 7 at 12:45 -> next run: March 8 at 12:46
If PC starts late (ex: March 8 16:32) -> run IMMEDIATELY
"""

import os
import json
import time
import asyncio
import psutil
import subprocess
import sys
import atexit
from datetime import datetime, timedelta
from pathlib import Path

# Configuration
LAST_OPENING_FILE = "last_opening.json"
SCHEDULE_CONFIG_FILE = "schedule_config.json"
LOCK_FILE = "scheduler.lock"

class CasehugScheduler:
    def __init__(self):
        """Initialize scheduler"""
        self.config = self.load_schedule_config()
        self.last_opening = self.load_last_opening()
        self.lock_file_path = os.path.abspath(LOCK_FILE)
        
        # Register cleanup at exit
        atexit.register(self.cleanup_lock)
    
    def is_already_running(self):
        """Check whether another scheduler instance is running"""
        if not os.path.exists(self.lock_file_path):
            return False
        
        try:
            with open(self.lock_file_path, 'r') as f:
                pid = int(f.read().strip())
            
            # Check if process with this PID is still running
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    # Check if e scheduler.py
                    cmdline = ' '.join(proc.cmdline())
                    if 'scheduler.py' in cmdline:
                        print(f"⚠️  Scheduler is already running (PID: {pid})")
                        return True
                except:
                    pass
            
            # PID no longer exists or is not scheduler - delete old lock
            os.remove(self.lock_file_path)
            return False
            
        except Exception as e:
            print(f"⚠️  Lock verification error: {e}")
            return False
    
    def create_lock(self):
        """Create lock file with current PID"""
        try:
            pid = os.getpid()
            with open(self.lock_file_path, 'w') as f:
                f.write(str(pid))
            print(f"🔒 Lock created (PID: {pid})")
            return True
        except Exception as e:
            print(f"❌ Lock creation error: {e}")
            return False
    
    def cleanup_lock(self):
        """Delete lock file on exit"""
        try:
            if os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
                print(f"🔓 Lock removed")
        except Exception as e:
            print(f"⚠️  Lock deletion error: {e}")
    
    def load_schedule_config(self):
        """Load scheduler configuration"""
        default_config = {
            "enabled": True,
            "scheduler_mode": "periodic",  # "smart" = exact time calculation | "periodic" = check every X minutes
            "check_interval_minutes": 30,  # For periodic mode only - check every X minutes
            "cooldown_grace_minutes": 1,  # Added after hours_between_runs to avoid edge timing issues
            "require_steam_login": True,  # Check if Steam e pornit and logat
            "hours_between_runs": 24,  # 24 hours + 1 min between runs (standard for cases)
            "accounts_with_steam": []  # List of accounts that use Steam ["Account 1", "Account 2"]
        }
        
        if os.path.exists(SCHEDULE_CONFIG_FILE):
            with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                default_config.update(loaded)
        else:
            # Create default config
            with open(SCHEDULE_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"✅ Config created: {SCHEDULE_CONFIG_FILE}")
        
        return default_config
    
    def load_last_opening(self):
        """Load tracking for latest openings per account"""
        if not os.path.exists(LAST_OPENING_FILE):
            # Create new file
            default_data = {}
            # Load accounts from config.json
            try:
                with open('config.json', 'r', encoding='utf-8') as f:
                    config = json.load(f)
                    for account in config.get('accounts', []):
                        account_name = account.get('name', '')
                        if account_name:
                            default_data[account_name] = {
                                "last_opening": None,
                                "last_check": None
                            }
            except:
                pass
            
            with open(LAST_OPENING_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
            
            return default_data
        
        try:
            with open(LAST_OPENING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save_last_opening(self):
        """Save latest openings tracking"""
        with open(LAST_OPENING_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.last_opening, f, indent=2, ensure_ascii=False)
    
    def update_account_opening(self, account_name):
        """Update timestamp of latest opening for an account"""
        if account_name not in self.last_opening:
            self.last_opening[account_name] = {}
        
        timestamp = datetime.now().isoformat()
        self.last_opening[account_name]['last_opening'] = timestamp
        self.last_opening[account_name]['last_check'] = timestamp
        self.save_last_opening()
        print(f"   ✅ Saved timestamp for {account_name}: {timestamp}")
    
    def update_account_check(self, account_name):
        """Update only latest check timestamp (without opening)"""
        if account_name not in self.last_opening:
            self.last_opening[account_name] = {}
        
        timestamp = datetime.now().isoformat()
        self.last_opening[account_name]['last_check'] = timestamp
        self.save_last_opening()
    
    def calculate_next_run_time(self):
        """Calculate exact time for next run (closest account that should run)"""
        hours_required = self.config.get('hours_between_runs', 24)
        grace_minutes = self.config.get('cooldown_grace_minutes', 1)
        next_runs = []
        
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            
            # First run or never opened - run immediately
            if not last_opening_str:
                return datetime.now()  # Run now
            
            # Calculate exact next run time: last_opening + hours + grace_minutes
            try:
                last_opening = datetime.fromisoformat(last_opening_str)
                next_run = last_opening + timedelta(hours=hours_required, minutes=grace_minutes)
                next_runs.append((account_name, next_run))
            except:
                # Parse error - run immediately
                return datetime.now()
        
        # Return closest time (account that should run first)
        if next_runs:
            next_runs.sort(key=lambda x: x[1])  # Sort by time
            earliest_account, earliest_time = next_runs[0]
            return earliest_time
        else:
            # No account in tracking - run immediately
            return datetime.now()
    
    def get_accounts_ready_to_open(self):
        """Get list of accounts that can open cases (24h passed)"""
        ready_accounts = []
        hours_required = self.config.get('hours_between_runs', 24)
        
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            
            # First run or never opened
            if not last_opening_str:
                ready_accounts.append({
                    'name': account_name,
                    'reason': 'First opening',
                    'hours_passed': None
                })
                continue
            
            # Calculate elapsed time
            try:
                last_opening = datetime.fromisoformat(last_opening_str)
                hours_passed = (datetime.now() - last_opening).total_seconds() / 3600
                
                if hours_passed >= hours_required:
                    ready_accounts.append({
                        'name': account_name,
                        'reason': f'{hours_passed:.1f}h passed',
                        'hours_passed': hours_passed
                    })
            except:
                # Parse error - treat as first opening
                ready_accounts.append({
                    'name': account_name,
                    'reason': 'Timestamp error - reset',
                    'hours_passed': None
                })
        
        return ready_accounts
    
    def is_steam_running_and_logged_in(self):
        """Check if Steam is running and user is logged in"""
        try:
            # Check if Steam process is running
            steam_running = False
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'steam.exe' in proc.info['name'].lower():
                    steam_running = True
                    break
            
            if not steam_running:
                return False
            
            # Check if Steam is logged in (check loginusers.vdf)
            steam_path = None
            possible_paths = [
                r"C:\Program Files (x86)\Steam",
                r"C:\Program Files\Steam",
                os.path.join(os.environ.get('PROGRAMFILES(X86)', ''), 'Steam'),
                os.path.join(os.environ.get('PROGRAMFILES', ''), 'Steam')
            ]
            
            for path in possible_paths:
                if os.path.exists(path):
                    steam_path = path
                    break
            
            if not steam_path:
                return False
            
            loginusers_file = os.path.join(steam_path, 'config', 'loginusers.vdf')
            
            if not os.path.exists(loginusers_file):
                return False
            
            # Read file and check if there is a recent user
            with open(loginusers_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if '"users"' in content.lower() or '"76561' in content:
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    def check_internet_connection(self):
        """Check if internet connection exists"""
        import socket
        
        try:
            # Try connecting to Google DNS (8.8.8.8) on port 53
            # 3-second timeout to avoid waiting too long
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            return True
        except socket.error:
            # Try Cloudflare DNS (1.1.1.1) as backup
            try:
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
                return True
            except socket.error:
                return False
    
    async def run_bot_for_accounts(self, account_names):
        """Run bot for specified accounts"""
        try:
            print("\n" + "="*60)
            print(f"🚀 STARTING CASEHUGBOT - {len(account_names)} ACCOUNTS")
            print("="*60)
            
            # Import and run main.py
            from main import CasehugBotNodriver
            
            # Filter accounts in temporary config
            with open('config.json', 'r', encoding='utf-8') as f:
                full_config = json.load(f)
            
            # Save original configuration
            original_accounts = full_config['accounts'].copy()
            
            # Keep only ready accounts
            full_config['accounts'] = [
                acc for acc in full_config['accounts'] 
                if acc['name'] in account_names
            ]
            
            # Save temporary config
            with open('config_temp.json', 'w', encoding='utf-8') as f:
                json.dump(full_config, f, indent=2, ensure_ascii=False)
            
            # Run bot with temporary config
            bot = CasehugBotNodriver('config_temp.json')
            results = await bot.run()
            
            # Update timestamps for processed accounts
            for account_name in account_names:
                # Check if account opened cases successfully
                # (we can assume yes if no error occurred)
                self.update_account_opening(account_name)
            
            # Delete temporary config
            if os.path.exists('config_temp.json'):
                os.remove('config_temp.json')
            
            print("\n" + "="*60)
            print("✅ CASEHUGBOT COMPLETED - AUTO SHUTDOWN")
            print("="*60)
            
            return True
            
        except Exception as e:
            print(f"\n❌ EROARE RULARE BOT: {e}")
            import traceback
            traceback.print_exc()
            
            # Clean temporary config
            if os.path.exists('config_temp.json'):
                os.remove('config_temp.json')
            
            return False
    
    async def check_and_run(self):
        """Check conditions and run bot for ready accounts"""
        print("\n" + "="*60)
        print(f"🔍 CHECK - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 1. Check whether scheduler is enabled
        if not self.config.get('enabled', True):
            print("❌ Scheduler is disabled in configuration")
            return False
        
        # 2. Get ready accounts (24h passed)
        ready_accounts = self.get_accounts_ready_to_open()
        
        if not ready_accounts:
            print("⏳ No ready accounts - waiting 24h since the last opening")
            
            # Show status for each account
            hours_required = self.config.get('hours_between_runs', 24)
            for account_name, data in self.last_opening.items():
                last_opening_str = data.get('last_opening')
                if last_opening_str:
                    try:
                        last_opening = datetime.fromisoformat(last_opening_str)
                        hours_passed = (datetime.now() - last_opening).total_seconds() / 3600
                        remaining = hours_required - hours_passed
                        print(f"   {account_name}: {hours_passed:.1f}h passed | {remaining:.1f}h remaining")
                    except:
                        pass
                else:
                    print(f"   {account_name}: Never opened (will run at next check)")
            
            return False
        
        print(f"✅ {len(ready_accounts)} accounts READY:")
        for acc in ready_accounts:
            print(f"   • {acc['name']}: {acc['reason']}")
        
        # 3. Check internet connection
        print(f"\n🌐 Check internet...")
        if not self.check_internet_connection():
            check_interval_minutes = self.config.get('check_interval_minutes', 30)
            print("❌ NO INTERNET CONNECTION!")
            print("   💡 Connect to the internet and try again")
            print(f"   ⏳ Next check in {check_interval_minutes} minutes...")
            return False
        print("✅ Internet connected")
        
        # 4. Check Steam if required
        require_steam = self.config.get('require_steam_login', True)
        if require_steam:
            accounts_with_steam = self.config.get('accounts_with_steam', [])
            # Check if at least one ready account uses Steam
            ready_with_steam = [acc for acc in ready_accounts if acc['name'] in accounts_with_steam]
            
            if ready_with_steam:
                print(f"\n🔍 Check Steam...")
                if not self.is_steam_running_and_logged_in():
                    check_interval_minutes = self.config.get('check_interval_minutes', 30)
                    print("⚠️  STEAM IS NOT RUNNING OR YOU ARE NOT LOGGED IN")
                    print("   💡 Start Steam and log in")
                    print(f"   🔄 Will check again in {check_interval_minutes} minutes...")
                    return False
                else:
                    print("✅ Steam detected and logged in")
        
        # 4. All conditions met - RUN BOT
        print("\n🚀 PORNESC BOTUL...\n")
        account_names = [acc['name'] for acc in ready_accounts]
        success = await self.run_bot_for_accounts(account_names)
        return success
    
    async def run_scheduler_loop(self):
        """Dual-mode scheduler: SMART (exact time) or PERIODIC (check every X min)"""
        mode = self.config.get('scheduler_mode', 'smart').lower()
        
        if mode == 'periodic':
            await self._run_periodic_mode()
        else:
            await self._run_smart_mode()
    
    async def _run_periodic_mode(self):
        """PERIODIC MODE - Check every X minutes (old behavior)"""
        check_interval_minutes = self.config.get('check_interval_minutes', 30)
        check_interval = check_interval_minutes * 60
        
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║      CASEHUGBOT SCHEDULER - PERIODIC MODE (CLASSIC)       ║
╚═══════════════════════════════════════════════════════════╝

📋 Configuration:
   🔄 Mode: PERIODIC (check constant)
    ⏱️  Interval check: {check_interval_minutes} minute
   ⏳ Interval openings: {self.config.get('hours_between_runs', 24)}h
   🎮 Steam required: {'DA' if self.config.get('require_steam_login') else 'NU'}
   📦 Steam accounts: {', '.join(self.config.get('accounts_with_steam', [])) or 'All'}

💡 PERIODIC SYSTEM:
    • Check every {check_interval_minutes} minute if 24h have passed
   • Run automatically when accounts are ready
   • Close after processing (Task Scheduler restarts it)

📊 Status accounts:""")
        
        hours_required = self.config.get('hours_between_runs', 24)
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            if last_opening_str:
                try:
                    last_opening = datetime.fromisoformat(last_opening_str)
                    hours_passed = (datetime.now() - last_opening).total_seconds() / 3600
                    remaining = hours_required - hours_passed
                    
                    if remaining > 0:
                        print(f"   ⏳ {account_name}: {remaining:.1f}h until next opening")
                    else:
                        print(f"   ✅ {account_name}: READY ({hours_passed:.1f}h passed)")
                except:
                    print(f"   • {account_name}: Timestamp error - will be reset")
            else:
                print(f"   • {account_name}: First run - READY")
        
        print("\n" + "="*60 + "\n")
        
        # Loop periodic - check constant
        while True:
            try:
                success = await self.check_and_run()
                
                if success:
                    print("\n✅ Processing complete - SCHEDULER EXIT")
                    print("   💡 Task Scheduler will restart automatically")
                    break  # Exit loop - close scheduler
                
                # Wait next check
                print(f"\n⏰ Next check in {check_interval_minutes} minutes...")
                print(f"   (at {(datetime.now() + timedelta(seconds=check_interval)).strftime('%H:%M:%S')})")
                await asyncio.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Scheduler stopped manually (Ctrl+C)")
                break
    
    async def _run_smart_mode(self):
        """SMART MODE - Calculate exact time, run only when needed (new behavior)"""
        grace_minutes = self.config.get('cooldown_grace_minutes', 1)
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║      CASEHUGBOT SCHEDULER - SMART MODE (ZERO CHECKS)      ║
╚═══════════════════════════════════════════════════════════╝

📋 Configuration:
   🧠 Mode: SMART (exact calculation, zero periodic checks)
    ⏱️  Interval: {self.config.get('hours_between_runs', 24)}h + {grace_minutes}min between openings
   🎮 Steam required: {'DA' if self.config.get('require_steam_login') else 'NU'}
   📦 Steam accounts: {', '.join(self.config.get('accounts_with_steam', [])) or 'All'}

💡 SMART SYSTEM:
   • Calculate EXACT time of next openings
   • Task Scheduler starts ONLY when it is time
   • If PC starts late → run IMEDIAT
   • ZERO periodic checks = ZERO resource usage

📊 Status accounts:""")
        
        hours_required = self.config.get('hours_between_runs', 24)
        now = datetime.now()
        
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            if last_opening_str:
                try:
                    last_opening = datetime.fromisoformat(last_opening_str)
                    next_run = last_opening + timedelta(hours=hours_required, minutes=grace_minutes)
                    
                    if now >= next_run:
                        print(f"   ✅ {account_name}: READY NOW (deadline passed)")
                    else:
                        time_remaining = next_run - now
                        hours_rem = time_remaining.total_seconds() / 3600
                        print(f"   ⏳ {account_name}: Next run at {next_run.strftime('%Y-%m-%d %H:%M')} ({hours_rem:.1f}h remaining)")
                except:
                    print(f"   • {account_name}: Error in timestamp - will reset")
            else:
                print(f"   • {account_name}: First run - READY NOW")
        
        print("\n" + "="*60 + "\n")
        
        # Calculate exact time of next runs
        next_run_time = self.calculate_next_run_time()
        
        # Calculate time difference (in seconds)
        time_until_seconds = (next_run_time - now).total_seconds()
        
        # Check if time has arrived (or passed) - 1 second tolerance
        if time_until_seconds <= 1:
            print(f"⏰ TIME TO RUN! Scheduled time: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   → Running bot immediately...\n")
            
            try:
                success = await self.check_and_run()
                
                if success:
                    print("\n✅ Bot completed successfully - SCHEDULER EXIT")
                    print("   💡 Task Scheduler will run again at next calculated time")
                else:
                    print("\n⚠️  Bot execution skipped (conditions not met)")
                    print("   💡 Task Scheduler will check again at startup")
                    
            except KeyboardInterrupt:
                print("\n\n⚠️  Scheduler stopped manually (Ctrl+C)")
        else:
            # Time has not arrived yet - show when it will
            time_until = next_run_time - now
            hours_until = time_until.total_seconds() / 3600
            print(f"⏰ NOT TIME YET")
            print(f"   Next scheduled run: {next_run_time.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Current time: {now.strftime('%Y-%m-%d %H:%M:%S')}")
            print(f"   Time remaining: {hours_until:.1f}h")
            print(f"\n💡 Scheduler will run automatically at scheduled time")
            print(f"   Task Scheduler ensures execution even if PC was off")
            print(f"\n💡 TIP: Switch to PERIODIC mode if you prefer constant checking:")
            print(f'   Edit schedule_config.json: "scheduler_mode": "periodic"')
    
    def run(self):
        """Start scheduler"""
        # Check if another instance is already running
        if self.is_already_running():
            print("❌ Another scheduler instance is already running!")
            print("   Not starting a new instance (prevents multiple processes)")
            return False
        
        # Create lock file
        if not self.create_lock():
            print("❌ Could not create lock file!")
            return False
        
        try:
            asyncio.run(self.run_scheduler_loop())
            return True
        except KeyboardInterrupt:
            print("\n\n⛔ Scheduler stopped by user")
            return False
        except Exception as e:
            print(f"\n❌ Critical scheduler error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup lock at exit
            self.cleanup_lock()


if __name__ == "__main__":
    scheduler = CasehugScheduler()
    exit_code = 0 if scheduler.run() else 1
    sys.exit(exit_code)
