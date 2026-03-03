#!/usr/bin/env python3
"""
CasehugBot Scheduler - Rulare automată cu tracking individual per cont
Verifică la fiecare 5 minute dacă au trecut 24h de la ultima deschidere
Se închide automat după procesare pentru a economisi resurse
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
LAST_OPENING_FILE = "last_opening.json"
SCHEDULE_CONFIG_FILE = "schedule_config.json"

class CasehugScheduler:
    def __init__(self):
        """Inițializează scheduler-ul"""
        self.config = self.load_schedule_config()
        self.last_opening = self.load_last_opening()
    
    def load_schedule_config(self):
        """Încarcă configurația scheduler-ului"""
        default_config = {
            "enabled": True,
            "check_interval_minutes": 5,  # Verifică la fiecare 5 minute
            "require_steam_login": True,  # Verifică dacă Steam e pornit și logat
            "hours_between_runs": 24,  # 24 ore între rulări (standard pentru case-uri)
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
        
        # 3. Verifică Steam dacă este necesar
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
        """Loop principal scheduler - verifică periodic și se închide după procesare"""
        check_interval = self.config.get('check_interval_minutes', 5) * 60
        
        print(f"""
╔═══════════════════════════════════════════════════════════╗
║         CASEHUGBOT SCHEDULER - TRACKING INDIVIDUAL        ║
╚═══════════════════════════════════════════════════════════╝

📋 Configurație:
   🔄 Verificare: la fiecare {self.config.get('check_interval_minutes', 5)} minute
   ⏱️  Interval: {self.config.get('hours_between_runs', 24)}h între deschideri
   🎮 Steam necesar: {'DA' if self.config.get('require_steam_login') else 'NU'}
   📦 Conturi Steam: {', '.join(self.config.get('accounts_with_steam', [])) or 'Toate'}

💡 Sistem inteligent:
   • Salvează ora exactă pentru fiecare cont
   • Deschide după 24h de la ultima deschidere
   • Se închide automat după procesare (economie resurse)
   • Flexibil: deschizi când vrei, botul ține cont de intervale

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
        
        while True:
            try:
                success = await self.check_and_run()
                
                if success:
                    print("\n✅ Procesare completă - ÎNCHIDERE SCHEDULER")
                    print("   💡 Task Scheduler va reporni automat peste 5 minute")
                    break  # Ieșire din loop - închide scheduler-ul
                
                # Așteaptă următoarea verificare
                print(f"\n⏰ Următoarea verificare în {self.config.get('check_interval_minutes', 5)} minute...")
                print(f"   (la ora {(datetime.now() + timedelta(seconds=check_interval)).strftime('%H:%M:%S')})")
                await asyncio.sleep(check_interval)
                
            except KeyboardInterrupt:
                print("\n\n⚠️  Scheduler oprit manual (Ctrl+C)")
                break
            except Exception as e:
                print(f"\n❌ EROARE SCHEDULER: {e}")
                import traceback
                traceback.print_exc()
                print(f"\n🔄 Reîncerc în {self.config.get('check_interval_minutes', 5)} minute...")
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
