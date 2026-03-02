#!/usr/bin/env python3
"""
CasehugBot Scheduler - Rulare automată zilnică în background
Verifică: interval 24h, Steam login, oră programată
"""

import os
import json
import time
import asyncio
import psutil
import subprocess
from datetime import datetime, timedelta
from pathlib import Path

# Configurație
SCHEDULE_CONFIG_FILE = "schedule_config.json"
LAST_RUN_FILE = "last_run.txt"

class CasehugScheduler:
    def __init__(self):
        """Inițializează scheduler-ul"""
        self.config = self.load_schedule_config()
        
    def load_schedule_config(self):
        """Încarcă configurația scheduler-ului"""
        default_config = {
            "enabled": True,
            "run_time": "10:00",  # HH:MM format (24h)
            "check_interval_minutes": 5,  # Verifică la fiecare 5 minute
            "require_steam_login": True,  # Verifică dacă Steam e pornit și logat
            "run_on_startup": False,  # Rulează imediat la pornire (ignoră ora)
            "min_hours_between_runs": 23,  # Minim 23 ore între rulări
            "window_mode": "minimized",  # "minimized", "hidden", "normal"
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
            print(f"   📝 Editează ora dorită (run_time) și conturile Steam")
        
        return default_config
    
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
                print("   ⚠️  Steam nu este pornit")
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
                print("   ⚠️  Nu am găsit Steam instalat")
                return False
            
            loginusers_file = os.path.join(steam_path, 'config', 'loginusers.vdf')
            
            if not os.path.exists(loginusers_file):
                print("   ⚠️  Steam fără utilizatori salvați")
                return False
            
            # Citește fișierul și verifică dacă există utilizator recent
            with open(loginusers_file, 'r', encoding='utf-8', errors='ignore') as f:
                content = f.read()
                # Verifică dacă există cel puțin un user (conține structura "users")
                if '"users"' in content.lower() or '"76561' in content:
                    print("   ✅ Steam pornit și logat")
                    return True
            
            print("   ⚠️  Steam pornit dar nu este logat")
            return False
            
        except Exception as e:
            print(f"   ⚠️  Eroare verificare Steam: {e}")
            return False
    
    def get_last_run_time(self):
        """Obține timestamp-ul ultimei rulări"""
        if not os.path.exists(LAST_RUN_FILE):
            return None
        
        try:
            with open(LAST_RUN_FILE, 'r') as f:
                timestamp_str = f.read().strip()
                return datetime.fromisoformat(timestamp_str)
        except:
            return None
    
    def save_last_run_time(self):
        """Salvează timestamp-ul curent ca ultimă rulare"""
        with open(LAST_RUN_FILE, 'w') as f:
            f.write(datetime.now().isoformat())
        print(f"   ✅ Timestamp salvat: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    def should_run_now(self):
        """Verifică dacă botul ar trebui să ruleze acum"""
        
        # Verifică dacă scheduler-ul este activat
        if not self.config.get('enabled', True):
            print("❌ Scheduler dezactivat în configurație")
            return False
        
        # Verifică ultima rulare
        last_run = self.get_last_run_time()
        if last_run:
            hours_since_last = (datetime.now() - last_run).total_seconds() / 3600
            min_hours = self.config.get('min_hours_between_runs', 23)
            
            if hours_since_last < min_hours:
                remaining = min_hours - hours_since_last
                print(f"⏳ Última rulare: {last_run.strftime('%Y-%m-%d %H:%M:%S')}")
                print(f"   ⏱️  Timp până la următoare rulare: {remaining:.1f}h")
                return False
        
        # Run on startup - ignoră ora
        if self.config.get('run_on_startup', False) and last_run is None:
            print("✅ Rulare la pornire activată (prima rulare)")
            return True
        
        # Verifică ora programată
        target_time_str = self.config.get('run_time', '10:00')
        target_hour, target_minute = map(int, target_time_str.split(':'))
        
        now = datetime.now()
        target_time = now.replace(hour=target_hour, minute=target_minute, second=0, microsecond=0)
        
        # Interval de ±2 minute pentru a prinde ora
        time_diff = abs((now - target_time).total_seconds()) / 60
        
        if time_diff <= 2:
            print(f"✅ Ora programată atinsă: {target_time_str}")
            return True
        else:
            next_run = target_time if now < target_time else target_time + timedelta(days=1)
            print(f"⏱️  Următoarea rulare: {next_run.strftime('%Y-%m-%d %H:%M:%S')}")
            return False
    
    def check_steam_requirement(self):
        """Verifică requirement-ul Steam dacă este activat"""
        if not self.config.get('require_steam_login', True):
            print("   ℹ️  Verificare Steam dezactivată")
            return True
        
        # Verifică dacă există conturi cu Steam
        accounts_with_steam = self.config.get('accounts_with_steam', [])
        if not accounts_with_steam:
            print("   ℹ️  Niciun cont nu folosește Steam - skip verificare")
            return True
        
        print(f"   🔍 Verificare Steam pentru {len(accounts_with_steam)} conturi...")
        return self.is_steam_running_and_logged_in()
    
    async def run_bot(self):
        """Rulează botul principal"""
        try:
            print("\n" + "="*60)
            print("🚀 PORNIRE CASEHUGBOT")
            print("="*60)
            
            # Importă și rulează main.py
            from main import CasehugBotNodriver
            
            bot = CasehugBotNodriver()
            await bot.run()
            
            print("\n" + "="*60)
            print("✅ CASEHUGBOT FINALIZAT CU SUCCES")
            print("="*60)
            
            # Salvează timestamp
            self.save_last_run_time()
            return True
            
        except Exception as e:
            print(f"\n❌ EROARE RULARE BOT: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    async def check_and_run(self):
        """Verifică condițiile și rulează botul dacă sunt îndeplinite"""
        print("\n" + "="*60)
        print(f"🔍 VERIFICARE CONDIȚIȚ - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("="*60)
        
        # 1. Verifică dacă trebuie să ruleze (interval 24h + oră)
        if not self.should_run_now():
            return False
        
        # 2. Verifică Steam dacă este necesar
        if not self.check_steam_requirement():
            print("\n⚠️  AȘTEPT AUTENTIFICARE STEAM")
            print("   💡 Te rog să pornești Steam și să te loghezi")
            print("   🔄 Voi verifica din nou în 5 minute...")
            return False
        
        # 3. Toate condițiile îndeplinite - RULEAZĂ BOTUL
        print("\n✅ TOATE CONDIȚIILE ÎNDEPLINITE - PORNESC BOTUL\n")
        success = await self.run_bot()
        return success
    
    async def run_scheduler_loop(self):
        """Loop principal scheduler - verifică periodic"""
        check_interval = self.config.get('check_interval_minutes', 5) * 60
        
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║           CASEHUGBOT SCHEDULER - PORNIT                   ║
╚═══════════════════════════════════════════════════════════╝

📋 Configurație:
   ⏰ Oră programată: {self.config.get('run_time', '10:00')}
   🔄 Verificare la fiecare: {self.config.get('check_interval_minutes', 5)} minute
   🎮 Steam necesar: {'DA' if self.config.get('require_steam_login') else 'NU'}
   📦 Conturi Steam: {', '.join(self.config.get('accounts_with_steam', [])) or 'Niciunul'}
   ⏱️  Interval minim: {self.config.get('min_hours_between_runs', 23)}h

💡 Scheduler rulează în background - minimizează fereastra
""")
        
        while True:
            try:
                await self.check_and_run()
            except Exception as e:
                print(f"\n❌ Eroare în scheduler loop: {e}")
                import traceback
                traceback.print_exc()
            
            # Așteaptă până la următoarea verificare
            print(f"\n💤 Aștept {self.config.get('check_interval_minutes', 5)} minute până la următoarea verificare...")
            print(f"   🕐 Următoarea verificare: {(datetime.now() + timedelta(seconds=check_interval)).strftime('%Y-%m-%d %H:%M:%S')}\n")
            
            await asyncio.sleep(check_interval)
    
    def run(self):
        """Pornește scheduler-ul"""
        try:
            asyncio.run(self.run_scheduler_loop())
        except KeyboardInterrupt:
            print("\n\n⛔ Scheduler oprit de utilizator")
        except Exception as e:
            print(f"\n❌ Eroare critică scheduler: {e}")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    scheduler = CasehugScheduler()
    scheduler.run()
