#!/usr/bin/env python3
"""
CasehugBot Smart Scheduler - Calculează timpul exact al următoarei rulări
Rulează DOAR când e necesar (nu mai verifică periodic)
Exemplu: deschis pe 7 martie la 12:45 → next run: 8 martie la 12:46
Dacă PC pornește târziu (ex: 8 martie 16:32) → rulează IMEDIAT
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

# Configurație
LAST_OPENING_FILE = "last_opening.json"
SCHEDULE_CONFIG_FILE = "schedule_config.json"
LOCK_FILE = "scheduler.lock"

class CasehugScheduler:
    def __init__(self):
        """Inițializează scheduler-ul"""
        self.config = self.load_schedule_config()
        self.last_opening = self.load_last_opening()
        self.lock_file_path = os.path.abspath(LOCK_FILE)
        
        # Înregistrează cleanup la exit
        atexit.register(self.cleanup_lock)
    
    def is_already_running(self):
        """Verifică dacă există o altă instanță a scheduler-ului care rulează"""
        if not os.path.exists(self.lock_file_path):
            return False
        
        try:
            with open(self.lock_file_path, 'r') as f:
                pid = int(f.read().strip())
            
            # Verifică dacă procesul cu acest PID încă rulează
            if psutil.pid_exists(pid):
                try:
                    proc = psutil.Process(pid)
                    # Verifică dacă e scheduler.py
                    cmdline = ' '.join(proc.cmdline())
                    if 'scheduler.py' in cmdline:
                        print(f"⚠️  Scheduler deja rulează (PID: {pid})")
                        return True
                except:
                    pass
            
            # PID-ul nu mai există sau nu e scheduler - șterge lock vechi
            os.remove(self.lock_file_path)
            return False
            
        except Exception as e:
            print(f"⚠️  Eroare verificare lock: {e}")
            return False
    
    def create_lock(self):
        """Creează fișier lock cu PID-ul curent"""
        try:
            pid = os.getpid()
            with open(self.lock_file_path, 'w') as f:
                f.write(str(pid))
            print(f"🔒 Lock creat (PID: {pid})")
            return True
        except Exception as e:
            print(f"❌ Eroare creare lock: {e}")
            return False
    
    def cleanup_lock(self):
        """Șterge fișierul lock la ieșire"""
        try:
            if os.path.exists(self.lock_file_path):
                os.remove(self.lock_file_path)
                print(f"🔓 Lock șters")
        except Exception as e:
            print(f"⚠️  Eroare ștergere lock: {e}")
    
    def load_schedule_config(self):
        """Încarcă configurația scheduler-ului"""
        default_config = {
            "enabled": True,
            "scheduler_mode": "smart",  # "smart" = exact time calculation | "periodic" = check every X minutes
            "check_interval_minutes": 5,  # For periodic mode only - check every X minutes
            "require_steam_login": True,  # Verifică dacă Steam e pornit și logat
            "hours_between_runs": 24,  # 24 ore + 1 min între rulări (standard pentru case-uri)
            "accounts_with_steam": []  # Lista conturi care folosesc Steam ["Cont 1", "Cont 2"]
        }
        
        if os.path.exists(SCHEDULE_CONFIG_FILE):
            with open(SCHEDULE_CONFIG_FILE, 'r', encoding='utf-8') as f:
                loaded = json.load(f)
                default_config.update(loaded)
        else:
            # Creează config implicit
            with open(SCHEDULE_CONFIG_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_config, f, indent=2, ensure_ascii=False)
            print(f"✅ Config creat: {SCHEDULE_CONFIG_FILE}")
        
        return default_config
    
    def load_last_opening(self):
        """Încarcă tracking-ul ultimelor deschideri pe cont"""
        if not os.path.exists(LAST_OPENING_FILE):
            # Creează fișier nou
            default_data = {}
            # Încarcă conturile din config.json
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
        """Salvează tracking-ul ultimelor deschideri"""
        with open(LAST_OPENING_FILE, 'w', encoding='utf-8') as f:
            json.dump(self.last_opening, f, indent=2, ensure_ascii=False)
    
    def update_account_opening(self, account_name):
        """Actualizează timestamp-ul ultimei deschideri pentru un cont"""
        if account_name not in self.last_opening:
            self.last_opening[account_name] = {}
        
        timestamp = datetime.now().isoformat()
        self.last_opening[account_name]['last_opening'] = timestamp
        self.last_opening[account_name]['last_check'] = timestamp
        self.save_last_opening()
        print(f"   ✅ Salvat timestamp pentru {account_name}: {timestamp}")
    
    def update_account_check(self, account_name):
        """Actualizează doar timestamp-ul ultimei verificări (fără deschidere)"""
        if account_name not in self.last_opening:
            self.last_opening[account_name] = {}
        
        timestamp = datetime.now().isoformat()
        self.last_opening[account_name]['last_check'] = timestamp
        self.save_last_opening()
    
    def calculate_next_run_time(self):
        """Calculează timpul exact al următoarei rulări (cel mai apropiat cont care trebuie să ruleze)"""
        hours_required = self.config.get('hours_between_runs', 24)
        next_runs = []
        
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            
            # Prima rulare sau niciodată deschis - rulează imediat
            if not last_opening_str:
                return datetime.now()  # Rulează acum
            
            # Calculează timpul exact al următoarei rulări: last_opening + 24h + 1min (pentru siguranță)
            try:
                last_opening = datetime.fromisoformat(last_opening_str)
                next_run = last_opening + timedelta(hours=hours_required, minutes=1)
                next_runs.append((account_name, next_run))
            except:
                # Eroare parsare - rulează imediat
                return datetime.now()
        
        # Returnează cel mai apropiat timp (contul care trebuie să ruleze primul)
        if next_runs:
            next_runs.sort(key=lambda x: x[1])  # Sortează după timp
            earliest_account, earliest_time = next_runs[0]
            return earliest_time
        else:
            # Niciun cont în tracking - rulează imediat
            return datetime.now()
    
    def get_accounts_ready_to_open(self):
        """Obține lista conturilor care pot deschide case-uri (au trecut 24h)"""
        ready_accounts = []
        hours_required = self.config.get('hours_between_runs', 24)
        
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            
            # Prima rulare sau niciodată deschis
            if not last_opening_str:
                ready_accounts.append({
                    'name': account_name,
                    'reason': 'Prima deschidere',
                    'hours_passed': None
                })
                continue
            
            # Calculează timp trecut
            try:
                last_opening = datetime.fromisoformat(last_opening_str)
                hours_passed = (datetime.now() - last_opening).total_seconds() / 3600
                
                if hours_passed >= hours_required:
                    ready_accounts.append({
                        'name': account_name,
                        'reason': f'Au trecut {hours_passed:.1f}h',
                        'hours_passed': hours_passed
                    })
            except:
                # Eroare parsare - tratează ca prima deschidere
                ready_accounts.append({
                    'name': account_name,
                    'reason': 'Eroare timestamp - reset',
                    'hours_passed': None
                })
        
        return ready_accounts
    
    def is_steam_running_and_logged_in(self):
        """Verifică dacă Steam este pornit și utilizatorul este logat"""
        try:
            # Verifică dacă procesul Steam rulează
            steam_running = False
            for proc in psutil.process_iter(['name']):
                if proc.info['name'] and 'steam.exe' in proc.info['name'].lower():
                    steam_running = True
                    break
            
            if not steam_running:
                return False
            
            # Verifică dacă Steam este logat (check loginusers.vdf)
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
            
            # Citește fișierul și verifică dacă există utilizator recent
            with open(loginusers_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                if '"users"' in content.lower() or '"76561' in content:
                    return True
            
            return False
            
        except Exception as e:
            return False
    
    def check_internet_connection(self):
        """Verifică dacă există conexiune la internet"""
        import socket
        
        try:
            # Încearcă să conecteze la Google DNS (8.8.8.8) pe port 53
            # Timeout de 3 secunde pentru a nu aștepta prea mult
            socket.setdefaulttimeout(3)
            socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("8.8.8.8", 53))
            return True
        except socket.error:
            # Încearcă Cloudflare DNS (1.1.1.1) ca backup
            try:
                socket.socket(socket.AF_INET, socket.SOCK_STREAM).connect(("1.1.1.1", 53))
                return True
            except socket.error:
                return False
    
    async def run_bot_for_accounts(self, account_names):
        """Rulează botul pentru conturile specificate"""
        try:
            print("\n" + "="*60)
            print(f"🚀 PORNIRE CASEHUGBOT - {len(account_names)} CONTURI")
            print("="*60)
            
            # Importă și rulează main.py
            from main import CasehugBotNodriver
            
            # Filtrează conturile în config temporar
            with open('config.json', 'r', encoding='utf-8') as f:
                full_config = json.load(f)
            
            # Salvează configurația originală
            original_accounts = full_config['accounts'].copy()
            
            # Filtrează doar conturile ready
            full_config['accounts'] = [
                acc for acc in full_config['accounts'] 
                if acc['name'] in account_names
            ]
            
            # Salvează config temporar
            with open('config_temp.json', 'w', encoding='utf-8') as f:
                json.dump(full_config, f, indent=2, ensure_ascii=False)
            
            # Rulează botul cu config temporar
            bot = CasehugBotNodriver('config_temp.json')
            results = await bot.run()
            
            # Actualizează timestamp-urile pentru conturile procesate
            for account_name in account_names:
                # Verifică dacă contul a deschis case-uri cu succes
                # (putem presupune că da dacă nu a fost eroare)
                self.update_account_opening(account_name)
            
            # Șterge config temporar
            if os.path.exists('config_temp.json'):
                os.remove('config_temp.json')
            
            print("\n" + "="*60)
            print("✅ CASEHUGBOT FINALIZAT - ÎNCHIDERE AUTOMATĂ")
            print("="*60)
            
            return True
            
        except Exception as e:
            print(f"\n❌ EROARE RULARE BOT: {e}")
            import traceback
            traceback.print_exc()
            
            # Curăță config temporar
            if os.path.exists('config_temp.json'):
                os.remove('config_temp.json')
            
            return False
    
    async def check_and_run(self):
        """Verifică condițiile și rulează botul pentru conturile ready"""
        print("\n" + "="*60)
        print(f"🔍 VERIFICARE - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 1. Verifică dacă scheduler-ul este activat
        if not self.config.get('enabled', True):
            print("❌ Scheduler dezactivat în configurație")
            return False
        
        # 2. Obține conturile ready (au trecut 24h)
        ready_accounts = self.get_accounts_ready_to_open()
        
        if not ready_accounts:
            print("⏳ Niciun cont ready - aștept 24h de la ultima deschidere")
            
            # Afișează status pentru fiecare cont
            hours_required = self.config.get('hours_between_runs', 24)
            for account_name, data in self.last_opening.items():
                last_opening_str = data.get('last_opening')
                if last_opening_str:
                    try:
                        last_opening = datetime.fromisoformat(last_opening_str)
                        hours_passed = (datetime.now() - last_opening).total_seconds() / 3600
                        remaining = hours_required - hours_passed
                        print(f"   {account_name}: {hours_passed:.1f}h trecut | {remaining:.1f}h rămas")
                    except:
                        pass
                else:
                    print(f"   {account_name}: Niciodată deschis (va rula la următoarea verificare)")
            
            return False
        
        print(f"✅ {len(ready_accounts)} conturi READY:")
        for acc in ready_accounts:
            print(f"   • {acc['name']}: {acc['reason']}")
        
        # 3. Verifică conexiunea la internet
        print(f"\n🌐 Verificare internet...")
        if not self.check_internet_connection():
            print("❌ NU EXISTĂ CONEXIUNE LA INTERNET!")
            print("   💡 Conectează-te la internet și încearcă din nou")
            print("   ⏳ Următoarea verificare în 5 minute...")
            return False
        print("✅ Internet conectat")
        
        # 4. Verifică Steam dacă este necesar
        require_steam = self.config.get('require_steam_login', True)
        if require_steam:
            accounts_with_steam = self.config.get('accounts_with_steam', [])
            # Verifică dacă măcar un cont ready folosește Steam
            ready_with_steam = [acc for acc in ready_accounts if acc['name'] in accounts_with_steam]
            
            if ready_with_steam:
                print(f"\n🔍 Verificare Steam...")
                if not self.is_steam_running_and_logged_in():
                    print("⚠️  STEAM NU ESTE PORNIT SAU NU EȘTI LOGAT")
                    print("   💡 Pornește Steam și loghează-te")
                    print("   🔄 Voi verifica din nou în 5 minute...")
                    return False
                else:
                    print("✅ Steam detectat și logat")
        
        # 4. Toate condițiile îndeplinite - RULEAZĂ BOTUL
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
        check_interval = self.config.get('check_interval_minutes', 5) * 60
        
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║      CASEHUGBOT SCHEDULER - PERIODIC MODE (CLASSIC)       ║
╚═══════════════════════════════════════════════════════════╝

📋 Configurație:
   🔄 Mode: PERIODIC (verifică constant)
   ⏱️  Interval verificare: {self.config.get('check_interval_minutes', 5)} minute
   ⏳ Interval deschideri: {self.config.get('hours_between_runs', 24)}h
   🎮 Steam necesar: {'DA' if self.config.get('require_steam_login') else 'NU'}
   📦 Conturi Steam: {', '.join(self.config.get('accounts_with_steam', [])) or 'Toate'}

💡 PERIODIC SYSTEM:
   • Verifică la fiecare {self.config.get('check_interval_minutes', 5)} minute dacă au trecut 24h
   • Rulează automat când conturile sunt ready
   • Se închide după procesare (Task Scheduler repornește)

📊 Status conturi:""")
        
        hours_required = self.config.get('hours_between_runs', 24)
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            if last_opening_str:
                try:
                    last_opening = datetime.fromisoformat(last_opening_str)
                    hours_passed = (datetime.now() - last_opening).total_seconds() / 3600
                    remaining = hours_required - hours_passed
                    
                    if remaining > 0:
                        print(f"   ⏳ {account_name}: {remaining:.1f}h până la următoarea deschidere")
                    else:
                        print(f"   ✅ {account_name}: READY (au trecut {hours_passed:.1f}h)")
                except:
                    print(f"   • {account_name}: Eroare timestamp - va fi resetat")
            else:
                print(f"   • {account_name}: Prima rulare - READY")
        
        print("\n" + "="*60 + "\n")
        
        # Loop periodic - verifică constant
        while True:
            try:
                success = await self.check_and_run()
                
                if success:
                    print("\n✅ Procesare completă - ÎNCHIDERE SCHEDULER")
                    print("   💡 Task Scheduler va reporni automat")
                    break  # Exit din loop - închide scheduler-ul
                
                # Așteaptă următoarea verificare
                print(f"\n⏰ Următoarea verificare în {self.config.get('check_interval_minutes', 5)} minute...")
                print(f"   (la ora {(datetime.now() + timedelta(seconds=check_interval)).strftime('%H:%M:%S')})")
                await asyncio.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Scheduler oprit manual (Ctrl+C)")
                break
    
    async def _run_smart_mode(self):
        """SMART MODE - Calculate exact time, run only when needed (new behavior)"""
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║      CASEHUGBOT SCHEDULER - SMART MODE (ZERO CHECKS)      ║
╚═══════════════════════════════════════════════════════════╝

📋 Configurație:
   🧠 Mode: SMART (calcul exact, zero verificări periodice)
   ⏱️  Interval: {self.config.get('hours_between_runs', 24)}h + 1min între deschideri
   🎮 Steam necesar: {'DA' if self.config.get('require_steam_login') else 'NU'}
   📦 Conturi Steam: {', '.join(self.config.get('accounts_with_steam', [])) or 'Toate'}

💡 SMART SYSTEM:
   • Calculează timpul EXACT al următoarei deschideri
   • Task Scheduler pornește DOAR când e timpul
   • Dacă PC pornește târziu → rulează IMEDIAT
   • ZERO verificări periodice = ZERO resurse consumate

📊 Status conturi:""")
        
        hours_required = self.config.get('hours_between_runs', 24)
        now = datetime.now()
        
        for account_name, data in self.last_opening.items():
            last_opening_str = data.get('last_opening')
            if last_opening_str:
                try:
                    last_opening = datetime.fromisoformat(last_opening_str)
                    next_run = last_opening + timedelta(hours=hours_required, minutes=1)
                    
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
        
        # Calculează timpul exact al următoarei rulări
        next_run_time = self.calculate_next_run_time()
        
        # Calculează diferența de timp (în secunde)
        time_until_seconds = (next_run_time - now).total_seconds()
        
        # Verifică dacă timpul a venit (sau a trecut) - toleranță 1 secundă
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
            # Timpul nu a venit încă - afișează când va fi
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
        """Pornește scheduler-ul"""
        # Verifică dacă deja rulează o altă instanță
        if self.is_already_running():
            print("❌ O altă instanță a scheduler-ului deja rulează!")
            print("   Nu pornesc o nouă instanță (previne procese multiple)")
            return False
        
        # Creează lock file
        if not self.create_lock():
            print("❌ Nu am putut crea lock file!")
            return False
        
        try:
            asyncio.run(self.run_scheduler_loop())
            return True
        except KeyboardInterrupt:
            print("\n\n⛔ Scheduler oprit de utilizator")
            return False
        except Exception as e:
            print(f"\n❌ Eroare critică scheduler: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Cleanup lock la final
            self.cleanup_lock()


if __name__ == "__main__":
    scheduler = CasehugScheduler()
    exit_code = 0 if scheduler.run() else 1
    sys.exit(exit_code)
