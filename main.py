import os
import json
import time
import asyncio
from datetime import datetime
import nodriver as uc
from nodriver import cdp  # Chrome DevTools Protocol pentru cookies
import requests
# from twocaptcha import TwoCaptcha  # Commented - not used
import ctypes  # Pentru Windows API - minimizare ferestre

# Configurație
CONFIG_FILE = "config.json"
LAST_OPENING_FILE = "last_opening.json"

class CasehugBotNodriver:
    def __init__(self, config_file=CONFIG_FILE):
        """Inițializează botul cu configurația din fișier"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.telegram_token = self.config.get('telegram_bot_token', '')
        self.telegram_chat_id = self.config.get('telegram_chat_id', '')
        self.accounts = self.config.get('accounts', [])
        self.captcha_api_key = self.config.get('2captcha_api_key', '')
        
        # FlareSolverr URL: Environment variable are prioritate (pentru Docker)
        self.flaresolverr_url = os.environ.get('FLARESOLVERR_URL', 
                                               self.config.get('flaresolverr_url', 'http://localhost:8191/v1'))
        
        # Sesiuni FlareSolverr pentru fiecare cont (păstrează cookies în Docker)
        self.flare_sessions = {}  # {account_name: session_id}
        
        # Detectare Docker
        is_docker = os.environ.get('DISPLAY') == ':99' or os.environ.get('CHROME_BIN') is not None
        
        # În Docker: FlareSolverr PRIMARY (headless Nodriver nu trece Cloudflare)
        # Pe Windows: Nodriver PRIMARY (11.22s, mai rapid)
        if is_docker:
            print(f"   🐳 Docker detectat - folosesc FlareSolverr ca PRIMARY bypass")
            self.use_flaresolverr = True
            self.flaresolverr_primary = True  # Folosește FlareSolverr întâi, nu ca fallback
            print(f"   🛡️  FlareSolverr URL: {self.flaresolverr_url}")
        else:
            print(f"   💻 Windows detectat - folosesc Nodriver PRIMARY (11.22s avg)")
            self.flaresolverr_primary = False
            # Verifică dacă FlareSolverr disponibil ca fallback
            try:
                flaresolverr_check = requests.get(self.flaresolverr_url.replace('/v1', ''), timeout=3)
                if flaresolverr_check.status_code == 200:
                    print(f"   🛡️  FlareSolverr disponibil ca fallback (16.57s)")
                    self.use_flaresolverr = True
                else:
                    self.use_flaresolverr = False
            except:
                self.use_flaresolverr = False
    
    async def setup_browser(self):
        """Nodriver nu necesită setup explicit - fiecare cont își va crea browser-ul"""
        print("   🚀 Nodriver gata - fiecare cont va lansa browser automat")
        return True
    
    def load_last_opening(self):
        """Încarcă tracking-ul ultimelor deschideri"""
        if not os.path.exists(LAST_OPENING_FILE):
            # Creează fișier nou cu toate conturile
            default_data = {}
            for account in self.accounts:
                account_name = account.get('name', '')
                if account_name:
                    default_data[account_name] = {
                        "last_opening": None,
                        "last_check": None
                    }
            
            with open(LAST_OPENING_FILE, 'w', encoding='utf-8') as f:
                json.dump(default_data, f, indent=2, ensure_ascii=False)
            
            return default_data
        
        try:
            with open(LAST_OPENING_FILE, 'r', encoding='utf-8') as f:
                return json.load(f)
        except:
            return {}
    
    def save_account_timestamp(self, account_name, had_success=True):
        """Salvează timestamp pentru un cont după procesare"""
        last_opening = self.load_last_opening()
        
        if account_name not in last_opening:
            last_opening[account_name] = {}
        
        timestamp = datetime.now().isoformat()
        
        # Dacă a deschis case cu succes, salvează ca last_opening
        # Altfel, doar actualizează last_check (pentru tracking)
        if had_success:
            last_opening[account_name]['last_opening'] = timestamp
            print(f"   ✅ Timestamp salvat pentru {account_name}: {timestamp}")
        
        last_opening[account_name]['last_check'] = timestamp
        
        with open(LAST_OPENING_FILE, 'w', encoding='utf-8') as f:
            json.dump(last_opening, f, indent=2, ensure_ascii=False)
    
    async def create_flaresolverr_session(self, account_name):
        """Creează sesiune FlareSolverr pentru un cont (păstrează cookies între requests)"""
        try:
            session_id = f"session_{account_name.replace(' ', '_')}"
            
            payload = {
                "cmd": "sessions.create",
                "session": session_id
            }
            
            response = requests.post(self.flaresolverr_url, json=payload, timeout=10)
            
            if response.status_code == 200:
                result = response.json()
                if result.get('status') == 'ok':
                    self.flare_sessions[account_name] = session_id
                    print(f"   ✅ Sesiune FlareSolverr creată: {session_id}")
                    return session_id
            
            print(f"   ⚠️  Nu am putut crea sesiune FlareSolverr pentru {account_name}")
            return None
        except Exception as e:
            print(f"   ⚠️  Eroare creare sesiune FlareSolverr: {e}")
            return None
    
    async def destroy_flaresolverr_session(self, account_name):
        """Șterge sesiune FlareSolverr după procesare cont"""
        if account_name not in self.flare_sessions:
            return
        
        try:
            session_id = self.flare_sessions[account_name]
            payload = {
                "cmd": "sessions.destroy",
                "session": session_id
            }
            
            requests.post(self.flaresolverr_url, json=payload, timeout=5)
            del self.flare_sessions[account_name]
            print(f"   🗑️  Sesiune FlareSolverr închisă: {session_id}")
        except:
            pass
    
    async def create_page_with_stealth(self, account_name):
        """Creează browser Nodriver cu profil persistent - bypass Cloudflare automat"""
        # Creează folder persistent pentru acest cont
        profile_dir = f'profiles/{account_name.replace(" ", "_")}'
        os.makedirs(profile_dir, exist_ok=True)
        
        print(f"   📁 Profil persistent: {profile_dir}")
        print(f"   🚀 Lansez Nodriver (bypass Cloudflare automat)...")
        
        # Detectează dacă rulează în Docker
        is_docker = os.environ.get('DISPLAY') == ':99' or os.environ.get('CHROME_BIN') is not None
        headless_mode = is_docker  # Headless în Docker, vizibil pe Windows
        
        if is_docker:
            print(f"   🐳 Docker detectat - rulare headless mode")
        
        # Lansează browser Nodriver cu profil persistent
        # Nodriver rezolvă Cloudflare automat prin DevTools Protocol
        browser = await uc.start(
            user_data_dir=os.path.abspath(profile_dir),
            headless=headless_mode,
            browser_args=[
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-infobars',
                '--mute-audio',  # Dezactivează sunetul
            ]
        )
        
        # Prima tab deschisă automat
        page = browser.main_tab
        
        # Minimizează fereastra Chrome (doar pe Windows, nu în Docker)
        if not is_docker:
            await asyncio.sleep(1)  # Așteaptă ca fereastra să apară
            try:
                user32 = ctypes.windll.user32
                
                # Găsește și minimizează toate ferestrele Chrome
                def enum_callback(hwnd, _):
                    if user32.IsWindowVisible(hwnd):
                        length = user32.GetWindowTextLengthW(hwnd)
                        if length > 0:
                            buffer = ctypes.create_unicode_buffer(length + 1)
                            user32.GetWindowTextW(hwnd, buffer, length + 1)
                            title = buffer.value
                            
                            # Minimizează dacă e Chrome
                            if 'Chrome' in title or 'casehug.com' in title.lower():
                                user32.ShowWindow(hwnd, 6)  # SW_MINIMIZE = 6
                    return True
                
                EnumWindowsProc = ctypes.WINFUNCTYPE(ctypes.c_bool, ctypes.c_void_p, ctypes.c_void_p)
                user32.EnumWindows(EnumWindowsProc(enum_callback), 0)
                print(f"   🪟 Fereastră Chrome minimizată în taskbar")
            except Exception as e:
                print(f"   ⚠️ Nu s-a putut minimiza: {e}")
        
        print(f"   ✅ Browser Nodriver gata pentru {account_name}")
        print(f"   🛡️  Cloudflare va fi trecut automat (avg 11.22s)")
        
        # Așteaptă stabilizarea conexiunii browser/WebSocket
        await asyncio.sleep(2)
        
        return page, browser
    
    async def solve_cloudflare_with_flaresolverr(self, url: str, account_name=None):
        """Rezolvă Cloudflare folosind FlareSolverr (GRATUIT, 99% success rate)"""
        try:
            print(f"   🛡️  Trimit request la FlareSolverr...")
            print(f"      URL: {url}")
            
            # Trimite request la FlareSolverr
            payload = {
                "cmd": "request.get",
                "url": url,
                "maxTimeout": 60000  # 60 secunde timeout
            }
            
            # Folosește sesiune dacă există (păstrează cookies)
            if account_name and account_name in self.flare_sessions:
                payload["session"] = self.flare_sessions[account_name]
                print(f"      📎 Folosesc sesiune: {self.flare_sessions[account_name]}")
            
            response = requests.post(
                self.flaresolverr_url,
                json=payload,
                timeout=65  # Puțin mai mult decât maxTimeout
            )
            
            if response.status_code != 200:
                print(f"   ❌ FlareSolverr eroare HTTP {response.status_code}")
                return None
            
            result = response.json()
            
            if result.get('status') != 'ok':
                print(f"   ❌ FlareSolverr eroare: {result.get('message', 'Unknown error')}")
                return None
            
            solution = result.get('solution', {})
            cookies = solution.get('cookies', [])
            user_agent = solution.get('userAgent', '')
            response_body = solution.get('response', '')  # HTML-ul paginii
            
            if not cookies:
                print(f"   ⚠️  FlareSolverr nu a returnat cookies")
                return None
            
            print(f"   ✅ FlareSolverr SUCCESS! Primite {len(cookies)} cookies")
            print(f"   🍪 Cookies: {', '.join([c['name'] for c in cookies[:5]])}...")
            
            return {
                'cookies': cookies,
                'user_agent': user_agent,
                'html': response_body  # HTML-ul paginii fără Cloudflare
            }
            
        except requests.exceptions.Timeout:
            print(f"   ❌ FlareSolverr timeout (>60s) - site-ul e prea lent sau FlareSolverr blocat")
            return None
        except Exception as e:
            print(f"   ❌ Eroare FlareSolverr: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def solve_turnstile_with_2captcha(self, page, sitekey: str, url: str):
        """Rezolvă Cloudflare Turnstile folosind 2Captcha API (FALLBACK)"""
        try:
            print(f"   🔐 Trimit challenge la 2Captcha (FALLBACK)...")
            print(f"      Sitekey: {sitekey[:20]}...")
            print(f"      URL: {url}")
            
            # Trimite challenge la 2Captcha
            result = self.captcha_solver.turnstile(
                sitekey=sitekey,
                url=url
            )
            
            token = result.get('code')
            if not token:
                print(f"   ❌ 2Captcha nu a returnat token")
                return None
            
            print(f"   ✅ Token primit de la 2Captcha: {token[:50]}...")
            return token
            
        except Exception as e:
            print(f"   ❌ Eroare 2Captcha: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    async def check_cloudflare(self, page):
        """Verifică dacă Cloudflare a fost trecut cu succes (cookies deja injectate în Docker)"""
        try:
            # În Docker: Cookies deja injectate în open_free_case(), doar verificăm
            # Pe Windows: Nodriver rezolvă automat
            is_docker = os.environ.get('DISPLAY') == ':99'
            
            if is_docker and hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
                print(f"   🐳 Verific dacă Cloudflare a fost trecut cu FlareSolverr cookies...")
                await asyncio.sleep(2)  # Așteaptă scurt ca pagina să se încarce complet
                
                content = await page.get_content()
                has_cloudflare = 'cloudflare' in content.lower() or 'checking your browser' in content.lower()
                
                if has_cloudflare:
                    print("   ❌ Cloudflare ÎNCĂ prezent după injectare cookies FlareSolverr")
                    return False
                else:
                    print("   ✅ Cloudflare trecut cu FlareSolverr cookies!")
                    return True
            
            # Pe Windows: Nodriver rezolvă automat - așteaptă mai mult
            first_wait = 15 if is_docker else 10
            second_wait = 15 if is_docker else 10
            
            print(f"   🛡️  Aștept rezolvare automată Cloudflare (Nodriver - {first_wait}s)...")
            await asyncio.sleep(first_wait)
            
            # Verifică dacă Cloudflare încă există
            content = await page.get_content()
            content_lower = content.lower()
            
            has_cloudflare = any(indicator in content_lower for indicator in [
                'cloudflare', 'checking your browser', 'just a moment', 
                'turnstile', 'performing security verification'
            ])
            
            if has_cloudflare:
                print(f"   ⚠️  Cloudflare încă prezent - aștept încă {second_wait}s...")
                await asyncio.sleep(second_wait)
                
                content = await page.get_content()
                has_cloudflare = 'cloudflare' in content.lower()
                
                if has_cloudflare:
                    print("   ⚠️  Cloudflare NU trecut automat - verificare manuală")
                    return False
            
            print("   ✅ Cloudflare trecut cu succes!")
            return True
            
        except Exception as e:
            print(f"   ⚠️  Eroare verificare Cloudflare: {e}")
            import traceback
            traceback.print_exc()
            return True  # Continuăm oricum
    
    async def check_steam_login(self, page, account_name):
        """Verifică dacă utilizatorul este logat cu Steam (verifică balanta în header)"""
        try:
            content = await page.get_content()
            
            # Verifică dacă există balanta în header (indicator sigur că e logat)
            has_balance = 'data-testid="header-account-balance"' in content
            
            if has_balance:
                # Extrage balanta DOAR din secțiunea header-account-balance
                import re
                # Caută secțiunea header-account-balance și extrage balanța de acolo
                header_match = re.search(r'data-testid="header-account-balance"[^>]*>.*?<span\s+data-testid="format-price"[^>]*>(\$[\d.]+)</span>', content, re.DOTALL)
                if header_match:
                    balance = header_match.group(1)
                    print(f"   ✅ {account_name} este logat cu Steam (Balanță: {balance})")
                else:
                    print(f"   ✅ {account_name} este logat cu Steam")
                return True
            else:
                # Nu există balanță → nu e logat, încearcă auto-login
                print(f"\n⚠️  {account_name} NU este logat cu Steam!")
                print(f"   🔄 Încerc auto-login cu Steam...")
                
                try:
                    # PASUL 1: Caută și click pe butonul "steam login"
                    login_button = None
                    
                    # Caută buton care conține label cu textul "steam login"
                    buttons = await page.select_all('button')
                    for btn in buttons:
                        try:
                            btn_html = await btn.get_html()
                            
                            # Verifică dacă HTML-ul conține exact label cu "steam login"
                            if 'ri-steam-fill' in btn_html and 'steam login' in btn_html.lower():
                                login_button = btn
                                print(f"   ✓ Găsit buton 'steam login'")
                                break
                        except:
                            continue
                    
                    if not login_button:
                        print(f"   ❌ Nu am găsit butonul 'steam login'")
                        return False
                    
                    # Click pe butonul de login
                    await login_button.scroll_into_view()
                    await asyncio.sleep(1)
                    await login_button.click()
                    print(f"   ✓ Click pe 'steam login'")
                    
                    # Așteaptă să apară modal-ul cu checkbox-uri
                    await asyncio.sleep(3)
                    
                    # PASUL 2: Bifează checkbox-urile
                    print(f"   🔄 Bifez checkbox-urile...")
                    
                    # Checkbox 1: Terms and Privacy Policy
                    try:
                        checkbox1 = await page.query_selector('input[data-testid="terms-and-age-verification-terms-privacy"]')
                        if checkbox1:
                            await checkbox1.click()
                            print(f"   ✓ Bifat: Terms and Privacy Policy")
                            await asyncio.sleep(0.5)
                        else:
                            print(f"   ⚠️  Nu am găsit checkbox Terms")
                    except Exception as e:
                        print(f"   ⚠️  Eroare checkbox1: {e}")
                    
                    # Checkbox 2: 18 years or older
                    try:
                        checkbox2 = await page.query_selector('input[data-testid="terms-and-age-verification-is-adult"]')
                        if checkbox2:
                            await checkbox2.click()
                            print(f"   ✓ Bifat: 18 years or older")
                            await asyncio.sleep(0.5)
                        else:
                            print(f"   ⚠️  Nu am găsit checkbox Age")
                    except Exception as e:
                        print(f"   ⚠️  Eroare checkbox2: {e}")
                    
                    # PASUL 3: Click pe butonul "log with steam"
                    try:
                        submit_button = await page.query_selector('button[data-testid="sign-in-button"]')
                        if submit_button:
                            await asyncio.sleep(1)
                            await submit_button.click()
                            print(f"   ✓ Click pe 'log with steam'")
                        else:
                            print(f"   ❌ Nu am găsit butonul 'log with steam'")
                            return False
                    except Exception as e:
                        print(f"   ❌ Eroare click submit: {e}")
                        return False
                    
                    # PASUL 4: Switch la tab-ul Steam și click pe "Sign In"
                    print(f"   ⏳ Aștept deschidere popup Steam (5s)...")
                    await asyncio.sleep(5)
                    
                    try:
                        # Găsește toate tab-urile deschise
                        all_tabs = page.browser.tabs
                        print(f"   📑 Găsite {len(all_tabs)} tab-uri deschise")
                        
                        steam_tab = None
                        # Caută tab-ul cu Steam
                        for tab in all_tabs:
                            try:
                                if 'steam' in tab.url.lower():
                                    steam_tab = tab
                                    print(f"   ✓ Găsit tab Steam: {tab.url[:50]}...")
                                    break
                            except:
                                continue
                        
                        if steam_tab:
                            # Switch la tab-ul Steam
                            await steam_tab.activate()
                            await asyncio.sleep(2)
                            
                            # Caută butonul "Sign In"
                            signin_button = await steam_tab.query_selector('input#imageLogin')
                            
                            if signin_button:
                                await signin_button.click()
                                print(f"   ✓ Click pe 'Sign In' în popup Steam")
                                await asyncio.sleep(5)
                            else:
                                print(f"   ⏳ Nu am găsit butonul Sign In, aștept autentificare automată...")
                                await asyncio.sleep(10)
                        else:
                            print(f"   ⏳ Nu am găsit tab-ul Steam, aștept autentificare automată...")
                            await asyncio.sleep(15)
                    except Exception as e:
                        print(f"   ⚠️  Eroare switch tab Steam: {e}")
                        await asyncio.sleep(15)
                    
                    # Așteaptă redirect înapoi la CaseHug
                    print(f"   ⏳ Aștept redirect la CaseHug (15s)...")
                    await asyncio.sleep(15)
                    
                    # Verifică dacă suntem pe casehug.com
                    current_url = page.url
                    if 'casehug.com' not in current_url:
                        print(f"   🔄 Navighez înapoi la /free-cases...")
                        await page.get('https://casehug.com/free-cases')
                        await asyncio.sleep(3)
                    
                except Exception as e:
                    print(f"   ❌ Eroare la auto-login: {e}")
                    import traceback
                    traceback.print_exc()
                    return False
                
                # Verifică din nou după login
                await asyncio.sleep(2)
                content = await page.get_content()
                has_balance_after = 'data-testid="header-account-balance"' in content
                
                if not has_balance_after:
                    print(f"   ❌ Auto-login nu a reușit. Contul va fi sărit.")
                    return False
                else:
                    # Extrage balanta
                    import re
                    header_match = re.search(r'data-testid="header-account-balance"[^>]*>.*?<span\s+data-testid="format-price"[^>]*>(\$[\d.]+)</span>', content, re.DOTALL)
                    if header_match:
                        balance = header_match.group(1)
                        print(f"   ✅ Auto-login reușit pentru {account_name}! (Balanță: {balance})")
                    else:
                        print(f"   ✅ Auto-login reușit pentru {account_name}!")
                    return True
                
        except Exception as e:
            print(f"   ⚠️  Eroare verificare login: {e}")
            return True  # Continuăm oricum
    
    async def check_available_cases(self, page, account_name):
        """Verifică ce case-uri sunt disponibile pe https://casehug.com/free-cases"""
        try:
            print(f"\n🔍 Verific case-uri disponibile pentru {account_name}...")
            
            # Navighează la pagina free-cases
            free_cases_url = "https://casehug.com/free-cases"
            print(f"   🌐 Accesez: {free_cases_url}")
            
            await page.get(free_cases_url)
            await asyncio.sleep(3)
            
            # Verifică dacă suntem pe site-ul corect
            current_url = page.url
            if "casehug.com/free-cases" in current_url:
                print(f"   ✅ Site încărcat corect: {current_url}")
            else:
                print(f"   ⚠️  WARNING: Site incorect! Așteptat 'casehug.com/free-cases', am ajuns pe: {current_url}")
                # Încearcă din nou
                await page.get(free_cases_url)
                await asyncio.sleep(3)
                current_url = page.url
                if "casehug.com/free-cases" in current_url:
                    print(f"   ✅ A doua încercare reușită: {current_url}")
                else:
                    print(f"   ❌ Nu am reușit să ajung pe free-cases, opresc verificarea")
                    return []
            
            # Verifică Cloudflare
            cloudflare_ok = await self.check_cloudflare(page)
            
            # Așteaptă ca pagina să se încarce complet
            await asyncio.sleep(2)
            
            # Verifică dacă utilizatorul este logat cu Steam
            is_logged_in = await self.check_steam_login(page, account_name)
            
            # Așteaptă după verificare login
            await asyncio.sleep(2)
            
            # Extrage HTML-ul paginii
            content = await page.get_content()
            
            available_cases = []
            
            # Definește case-urile în ordinea nivelului (pentru verificare inteligentă)
            # Format: (case_name, required_level)
            level_cases_order = [
                ("wood", 0),
                ("iron", 12),
                ("bronze", 24),
                ("silver", 32),
                ("gold", 41),
                ("platinum", 54),
                ("emerald", 64),
                ("diamond", 72),
                ("master", 87),
                ("challenger", 100),
                ("legend", 111),
                ("mythic", 119),
                ("immortal", 120)
            ]
            
            # Verifică fiecare case specific după link-ul său
            case_urls = {
                "discord": 'href="/free-cases/discord"',
                "steam": 'href="/free-cases/steam"',
                "wood": 'href="/free-cases/wood"',
                "iron": 'href="/free-cases/iron"',
                "bronze": 'href="/free-cases/bronze"',
                "silver": 'href="/free-cases/silver"',
                "gold": 'href="/free-cases/gold"',
                "platinum": 'href="/free-cases/platinum"',
                "emerald": 'href="/free-cases/emerald"',
                "diamond": 'href="/free-cases/diamond"',
                "master": 'href="/free-cases/master"',
                "challenger": 'href="/free-cases/challenger"',
                "legend": 'href="/free-cases/legend"',
                "mythic": 'href="/free-cases/mythic"',
                "immortal": 'href="/free-cases/immortal"'
            }
            
            # Verifică fiecare case
            # 1. Discord și Steam se verifică întotdeauna (nu depind de nivel)
            # 2. Level cases se verifică în ordine, cu STOP la primul locked din cauza nivelului
            
            # Verifică Discord și Steam (mereu disponibile, nu depind de nivel)
            for case_type in ["discord", "steam"]:
                if case_type not in case_urls:
                    continue
                    
                case_url_marker = case_urls[case_type]
                case_pos = content.find(case_url_marker)
                
                if case_pos == -1:
                    print(f"   ⚠️  {case_type.upper()} - nu a fost găsit pe pagină")
                    continue
                
                # Extrage secțiunea (500 înainte, 2000 după pentru context complet)
                section_start = max(0, case_pos - 500)
                section_end = min(len(content), case_pos + 2000)
                case_section = content[section_start:section_end]
                
                # Verifică dacă e pe cooldown
                has_timer = False
                if 'data-testid="badge"' in case_section and 'ri-timer-line' in case_section:
                    import re
                    time_pattern = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', case_section)
                    if time_pattern:
                        time_str = time_pattern.group(0)
                        print(f"   ⏰ {case_type.upper()} - pe cooldown (mai are {time_str})")
                        has_timer = True
                
                if has_timer:
                    continue  # Skip acest case
                
                # Verifică dacă e blocat din cauza task-urilor
                has_lock_icon = 'si-ch-lock' in case_section
                has_disabled_button = ('disabled=""' in case_section or '<button disabled' in case_section)
                is_case_locked = 'CASE LOCKED' in case_section or 'Case Locked' in case_section
                
                if has_lock_icon or (has_disabled_button and is_case_locked):
                    print(f"   🔒 {case_type.upper()} - blocat (task incomplete)")
                    continue
                
                if has_disabled_button and not has_timer:
                    print(f"   ⚠️  {case_type.upper()} - buton disabled")
                    continue
                
                # Verifică dacă are buton Open activ
                has_open_button = False
                if '>Open<' in case_section:
                    open_positions = []
                    search_pos = 0
                    while True:
                        pos = case_section.find('>Open<', search_pos)
                        if pos == -1:
                            break
                        open_positions.append(pos)
                        search_pos = pos + 1
                    
                    for open_pos in open_positions:
                        button_context = case_section[max(0, open_pos - 400):open_pos]
                        if '<button' in button_context:
                            last_button_start = button_context.rfind('<button')
                            button_tag = button_context[last_button_start:]
                            if 'disabled' not in button_tag:
                                has_open_button = True
                                break
                
                if has_open_button:
                    available_cases.append(case_type)
                    print(f"   ✅ {case_type.upper()} - disponibil")
                else:
                    print(f"   ⏳ {case_type.upper()} - status neclar")
            
            # Verifică level cases în ordine (wood → iron → bronze → etc.)
            # STOP la primul case care nu apare în pagină (locked din cauza nivelului)
            print(f"\\n   📊 Verificare case-uri bazate pe nivel...")
            for case_type, required_level in level_cases_order:
                if case_type not in case_urls:
                    continue
                    
                case_url_marker = case_urls[case_type]
                
                # Verifică dacă case-ul apare în pagină
                case_pos = content.find(case_url_marker)
                
                if case_pos == -1:
                    # Case-ul NU apare în pagină → LOCKED din cauza nivelului
                    # Toate case-urile următoare sunt și ele locked
                    print(f"   🔒 {case_type.upper()} (nivel {required_level}) - locked din cauza nivelului")
                    print(f"   🛑 STOP: Toate case-urile următoare sunt locked")
                    break  # STOP - nu mai verifica case-urile următoare
                
                # Case-ul apare în pagină → verifică statusul
                # IMPORTANT: Extrage secțiunea DOAR DUPĂ URL-ul case-ului 
                # (nu înainte, ca să nu prindem date de la case-ul anterior)
                section_start = case_pos  # Start exact de la URL
                section_end = min(len(content), case_pos + 2000)  # 2000 după URL
                case_section = content[section_start:section_end]
                
                # 1. Verifică indicatori de status
                has_lock_icon = 'si-ch-lock' in case_section
                has_disabled_button = ('disabled=""' in case_section or '<button disabled' in case_section)
                has_timer = False
                if 'data-testid="badge"' in case_section and 'ri-timer-line' in case_section:
                    import re
                    time_pattern = re.search(r'(\d{1,2}):(\d{2}):(\d{2})', case_section)
                    if time_pattern:
                        has_timer = True
                        time_str = time_pattern.group(0)
                
                # 2. LOGICĂ DE DECIZIE pentru case-uri bazate pe nivel:
                # - LOCK (cu sau fără timer) → NIVEL INSUFICIENT → BREAK
                # - Doar TIMER (fără lock) → PE COOLDOWN → CONTINUE
                
                # Dacă are LOCK (indiferent de timer) → NIVEL INSUFICIENT
                if has_lock_icon:
                    print(f"   🔒 {case_type.upper()} (nivel {required_level}) - nivel insuficient")
                    print(f"   🛑 STOP: Toate case-urile următoare necesită nivel mai mare")
                    break  # STOP verificarea
                
                # Dacă are doar TIMER (fără lock) → PE COOLDOWN
                if has_timer and not has_lock_icon:
                    print(f"   ⏰ {case_type.upper()} (nivel {required_level}) - pe cooldown ({time_str})")
                    continue  # Continuă verificarea - următoarele pot fi disponibile
                
                # Dacă are buton disabled dar fără lock și fără timer → neclar
                if has_disabled_button and not has_lock_icon and not has_timer:
                    print(f"   ⚠️  {case_type.upper()} (nivel {required_level}) - buton disabled (neclar)")
                    continue
                
                # 3. Verifică dacă are buton OPEN activ
                has_open_button = False
                if '>Open<' in case_section:
                    open_positions = []
                    search_pos = 0
                    while True:
                        pos = case_section.find('>Open<', search_pos)
                        if pos == -1:
                            break
                        open_positions.append(pos)
                        search_pos = pos + 1
                    
                    for open_pos in open_positions:
                        button_context = case_section[max(0, open_pos - 400):open_pos]
                        if '<button' in button_context:
                            last_button_start = button_context.rfind('<button')
                            button_tag = button_context[last_button_start:]
                            if 'disabled' not in button_tag:
                                has_open_button = True
                                break
                
                if has_open_button:
                    available_cases.append(case_type)
                    print(f"   ✅ {case_type.upper()} (nivel {required_level}) - disponibil")
                else:
                    print(f"   ⏳ {case_type.upper()} (nivel {required_level}) - status neclar")
            
            if not available_cases:
                print(f"   ⚠️  Niciun case disponibil pentru {account_name}")
            
            return available_cases
            
        except Exception as e:
            print(f"   ❌ Eroare verificare case-uri disponibile: {e}")
            import traceback
            traceback.print_exc()
            # Fallback: returnează toate case-urile din config
            return ["discord", "steam", "wood"]
    
    async def open_free_case(self, page, account_name, case_type):
        """Deschide un free case specific"""
        case_urls = {
            "discord": "https://casehug.com/free-cases/discord",
            "steam": "https://casehug.com/free-cases/steam",
            "wood": "https://casehug.com/free-cases/wood",
            "iron": "https://casehug.com/free-cases/iron",
            "bronze": "https://casehug.com/free-cases/bronze",
            "silver": "https://casehug.com/free-cases/silver",
            "gold": "https://casehug.com/free-cases/gold",
            "platinum": "https://casehug.com/free-cases/platinum",
            "emerald": "https://casehug.com/free-cases/emerald",
            "diamond": "https://casehug.com/free-cases/diamond",
            "master": "https://casehug.com/free-cases/master",
            "challenger": "https://casehug.com/free-cases/challenger",
            "legend": "https://casehug.com/free-cases/legend",
            "mythic": "https://casehug.com/free-cases/mythic",
            "immortal": "https://casehug.com/free-cases/immortal"
        }
        
        if case_type.lower() not in case_urls:
            print(f"   ⚠️ Case type '{case_type}' necunoscut")
            return None
        
        case_url = case_urls[case_type.lower()]
        print(f"\n📦 Deschid {case_type} pentru {account_name}...")
        print(f"   🌐 Navighez direct la: {case_url}")
        
        try:
            # În Docker: Obține cookies de la FlareSolverr ÎNAINTE de navigare
            if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary and self.use_flaresolverr:
                print(f"   🐳 Docker: Folosesc FlareSolverr pentru bypass Cloudflare...")
                flare_result = await self.solve_cloudflare_with_flaresolverr(case_url, account_name=account_name)
                
                if flare_result and flare_result.get('cookies'):
                    print(f"   🍪 Injectez {len(flare_result['cookies'])} cookies ÎNAINTE de navigare...")
                    
                    # Setează cookies în browser ÎNAINTE de navigare
                    for cookie in flare_result['cookies']:
                        try:
                            # Construiește cookie în format CDP
                            cookie_params = {
                                'name': cookie['name'],
                                'value': cookie['value'],
                                'domain': cookie.get('domain', '.casehug.com'),
                                'path': cookie.get('path', '/'),
                                'secure': cookie.get('secure', False),
                                'http_only': cookie.get('httpOnly', False)
                            }
                            
                            # Adaugă sameSite dacă există
                            if 'sameSite' in cookie:
                                cookie_params['same_site'] = cookie['sameSite']
                            
                            await page.send(cdp.network.set_cookie(**cookie_params))
                        except Exception as cookie_err:
                            # Ignoră erori pentru cookies individuale (unele pot fi invalide)
                            pass
                    
                    print(f"   ✅ Cookies injectate - navighez la pagină...")
                    await asyncio.sleep(1)
                else:
                    print("   ⚠️  FlareSolverr nu a putut rezolva - continui fără cookies")
            
            # Navigare directă cu Nodriver (acum cu cookies deja setate în Docker)
            await page.get(case_url)
            await asyncio.sleep(3)
            
            # Check Cloudflare (Nodriver rezolvă automat)
            cloudflare_ok = await self.check_cloudflare(page)
            
            # Scroll
            await page.evaluate("window.scrollTo(0, 400)")
            await asyncio.sleep(1)
            
            # Caută butonul OPEN/CLAIM
            print(f"   🔍 Caut butonul 'Open for Free'...")
            
            button = None
            
            # Metoda 1: Caută direct după data-testid (cel mai sigur)
            try:
                button = await page.query_selector('button[data-testid="open-button"]')
                if button:
                    print(f"   ✓ Găsit buton cu data-testid='open-button'")
            except:
                pass
            
            # Metoda 2: Fallback - caută toate butoanele
            if not button:
                button_texts = ["Open for Free", "Open", "Claim", "Free", "Get"]
                buttons = await page.select_all("button")
                
                for btn in buttons:
                    try:
                        # Skip butoane disabled (locked)
                        is_disabled = await btn.get_attribute('disabled')
                        if is_disabled is not None:
                            btn_text = await btn.text
                            print(f"   🔒 Buton ignore (disabled): {btn_text}")
                            continue
                        
                        # Verifică textul
                        btn_text = await btn.text
                        if btn_text:
                            for text in button_texts:
                                if text.lower() in btn_text.lower():
                                    button = btn
                                    print(f"   ✓ Găsit buton cu text: {btn_text}")
                                    break
                        
                        if button:
                            break
                    except:
                        continue
            
            if not button:
                print(f"   ❌ Nu am găsit butonul OPEN (case blocat sau pe cooldown)")
                return {
                    "case": case_type,
                    "skin": "Buton lipsă",
                    "price": "N/A"
                }
            
            # Verifică dacă butonul este disabled (ultimă verificare)
            try:
                is_disabled = await button.get_attribute('disabled')
                if is_disabled is not None:
                    print(f"   🔒 Butonul este LOCKED (disabled)")
                    return {
                        "case": case_type,
                        "skin": "Blocat",
                        "price": "N/A"
                    }
            except:
                pass
            
            # Click pe buton
            await button.scroll_into_view()
            await asyncio.sleep(0.5)
            await button.click()
            print(f"   ✓ Click pe butonul OPEN")
            
            # Așteaptă rezultatul
            await asyncio.sleep(5)
            
            # Verifică dacă există mesaj de eroare (playtime insuficient)
            content = await page.get_content()
            if 'Insufficient CS:GO/CS2 playtime' in content or 'Insufficient CS' in content:
                print(f"   ❌ EROARE: Playtime CS:GO/CS2 insuficient pentru acest cont!")
                print(f"   ⚠️  Acest cont nu poate deschide free cases (necesită mai multe ore jucate)")
                return {
                    "case": case_type,
                    "skin": "Playtime insuficient",
                    "price": "N/A"
                }
            
            # Caută skinul și prețul
            print(f"   🔍 Caut rezultatul...")
            
            skin_name = "Necunoscut"
            price = "N/A"
            
            # Caută skin prin selectors comuni
            skin_selectors = [
                '.item-name', '.skin-name', '.reward-name',
                '.item-title', '.skin-title', '.reward-title'
            ]
            
            for selector in skin_selectors:
                try:
                    elements = await page.select_all(selector)
                    for elem in elements:
                        try:
                            text = await elem.text
                            if text and len(text) > 3 and ('-' in text or '|' in text or '(' in text):
                                skin_name = text.strip()
                                print(f"   ✓ Skin: {skin_name}")
                                break
                        except:
                            continue
                    if skin_name != "Necunoscut":
                        break
                except:
                    continue
            
            # Caută preț
            price_selectors = [
                '.price', '.value', '.amount', '.cost'
            ]
            
            for selector in price_selectors:
                try:
                    elements = await page.select_all(selector)
                    for elem in elements:
                        try:
                            text = await elem.text
                            if text and ('$' in text or '€' in text or any(c.isdigit() for c in text)):
                                price = text.strip()
                                print(f"   ✓ Preț: {price}")
                                break
                        except:
                            continue
                    if price != "N/A":
                        break
                except:
                    continue
            
            print(f"✅ {case_type}: {skin_name} - {price}")
            
            return {
                "case": case_type,
                "skin": skin_name,
                "price": price
            }
            
        except Exception as e:
            print(f"   ❌ Eroare: {e}")
            import traceback
            traceback.print_exc()
            return {
                "case": case_type,
                "skin": "Eroare",
                "price": "N/A"
            }
    
    async def process_account(self, account):
        """Procesează un cont - lansează browser separat pentru fiecare case"""
        account_name = account['name']
        
        print(f"\n{'='*50}")
        print(f"🎮 Procesez contul: {account_name}")
        print(f"{'='*50}")
        
        # În Docker: Crează sesiune FlareSolverr pentru acest cont  
        if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
            await self.create_flaresolverr_session(account_name)
        
        browser = None
        try:
            # Lansează browser O SINGURĂ DATĂ pentru acest cont
            print(f"   🔍 Lansez browser...")
            page, browser = await self.create_page_with_stealth(account_name)
            
            # Verifică ce case-uri sunt disponibile (dynamic)
            available_cases = await self.check_available_cases(page, account_name)
            
            if not available_cases:
                print(f"⚠️  Niciun case disponibil pentru {account_name} astăzi")
                print(f"   ℹ️  Verific totuși pagina de profil pentru skin-uri noi...")
            else:
                # Procesează fiecare case FĂRĂ să închid browserul
                results = []
                for idx, case_type in enumerate(available_cases, 1):
                    print(f"\n   📦 Procesez case {idx}/{len(available_cases)}: {case_type.upper()}")
                    
                    try:
                        # Găsește și click butonul direct pe pagina /free-cases
                        result = await self.open_free_case_on_page(page, account_name, case_type)
                        # Nu mai salvăm rezultatul aici - vom extrage din profil
                        
                        # Revino la /free-cases pentru următorul case
                        if idx < len(available_cases):
                            print(f"   ↩️  Revin la /free-cases pentru următorul case...")
                            await page.get("https://casehug.com/free-cases")
                            await asyncio.sleep(3)
                            
                    except Exception as e:
                        print(f"   ❌ Eroare la procesare {case_type}: {e}")
                    
                    # Pauză între case-uri
                    if idx < len(available_cases):
                        await asyncio.sleep(2)
            
            # După ce am deschis toate case-urile, extrage skin-urile noi din profil
            print(f"\n   🔍 Extrag rezultatele din pagina de profil...")
            results = await self.extract_new_skins_from_profile(page, account_name)
            
            return {
                "account": account_name,
                "results": results,
                "balance": "N/A"
            }
            
        except Exception as e:
            print(f"❌ Eroare la procesare {account_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
        finally:
            # Închide browserul la final cu forță
            if browser:
                try:
                    await browser.stop()
                    print(f"   ✅ Browser închis pentru {account_name}")
                    await asyncio.sleep(2)  # Așteaptă să se închidă complet
                except Exception as e:
                    print(f"   ⚠️  Eroare la închidere browser: {e}")
                
                # Forțează închiderea proceselor Chrome rămase
                try:
                    import subprocess
                    import platform
                    if platform.system() == 'Windows':
                        # Închide procesele Chrome cu forță pe Windows
                        subprocess.run(['taskkill', '/F', '/IM', 'chrome.exe'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        subprocess.run(['taskkill', '/F', '/IM', 'chromedriver.exe'], 
                                     stderr=subprocess.DEVNULL, stdout=subprocess.DEVNULL)
                        print(f"   🧹 Procese Chrome curățate pentru {account_name}")
                except:
                    pass
            
            # Închide sesiune FlareSolverr în Docker
            if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
                await self.destroy_flaresolverr_session(account_name)
    
    async def extract_new_skins_from_profile(self, page, account_name):
        """Extrage skin-urile noi din pagina de profil (https://casehug.com/user-account)"""
        print(f"\n   📊 Extrag skin-urile noi din pagina de profil...")
        
        try:
            # Navighează la pagina de profil
            await page.get("https://casehug.com/user-account")
            print(f"   🌐 Navigat la https://casehug.com/user-account")
            
            # Așteaptă încărcarea paginii
            await asyncio.sleep(4)
            
            # Obține HTML-ul paginii
            content = await page.get_content()
            
            # Caută toate skin-urile cu label "New"
            import re
            
            # Pattern: găsește toate div-urile cu data-testid="your-drop-card-label" care conțin "New"
            # Apoi extrage datele din același container
            new_skins = []
            
            # Split HTML în secțiuni pentru fiecare card de skin
            # Găsește toate aparițiile de "your-drop-card-label"
            pattern = r'<div data-testid="your-drop-card-label"[^>]*>([^<]+)</div>'
            labels = re.finditer(pattern, content)
            
            for label_match in labels:
                label_text = label_match.group(1).strip()
                
                # Verifică dacă label-ul este "New"
                if label_text.lower() == "new":
                    # Găsește începutul container-ului (urcă până la div-ul părinte mare)
                    # Caută backward până găsește div-ul care conține toate datele
                    start_pos = label_match.start()
                    
                    # Caută înapoi până găsește div-ul principal (class="sc-965b1227-6")
                    search_back = content[max(0, start_pos - 5000):start_pos]
                    container_match = re.search(r'<div class="sc-965b1227-6[^"]*">', search_back)
                    
                    if container_match:
                        container_start = start_pos - len(search_back) + container_match.start()
                        # Extrage secțiunea (următoarele 3000 caractere)
                        section = content[container_start:start_pos + 3000]
                        
                        # Extrage datele din această secțiune
                        name_match = re.search(r'<div data-testid="your-drop-name"[^>]*>([^<]+)</div>', section)
                        category_match = re.search(r'<div data-testid="your-drop-category"[^>]*>([^<]+)</div>', section)
                        price_match = re.search(r'<span data-testid="your-drop-price"[^>]*>([^<]+)</span>', section)
                        case_type_match = re.search(r'<div data-testid="your-drops-hover-date"[^>]*>([^<]+)</div>', section)
                        
                        if name_match and category_match and price_match:
                            weapon_name = name_match.group(1).strip()
                            skin_category = category_match.group(1).strip()
                            price = price_match.group(1).strip()
                            case_type = case_type_match.group(1).strip().lower() if case_type_match else "unknown"
                            
                            # Extrage culoarea (raritatea) din gradient SVG
                            color_match = re.search(r'stop-color="([^"]+)"', section)
                            rarity_color = color_match.group(1).upper() if color_match else "#FFFFFF"
                            
                            # Mapează culoarea la raritate și emoji
                            rarity_map = {
                                "#A3A7BB": ("⚪", "Consumer/Industrial"),
                                "#5E98D9": ("🔵", "Mil-Spec"),
                                "#8847FF": ("🟣", "Restricted"),
                                "#D32CE6": ("🟣", "Restricted"),  # Purple variations
                                "#EB4B4B": ("🔴", "Covert"),
                                "#E4AE39": ("🟡", "Classified"),
                                "#F93AA6": ("🩷", "Classified"),  # Pink
                                "#FFD700": ("🟡", "Contraband"),
                            }
                            
                            # Găsește cel mai apropiat match pentru culoare
                            rarity_emoji = "⚪"
                            for color_code, (emoji, name) in rarity_map.items():
                                if rarity_color.startswith(color_code[:4]):  # Match primele 4 caractere
                                    rarity_emoji = emoji
                                    break
                            
                            skin_full_name = f"{weapon_name} | {skin_category}"
                            
                            new_skins.append({
                                "case": case_type,
                                "skin": skin_full_name,
                                "price": price,
                                "rarity": rarity_emoji
                            })
                            
                            print(f"   🆕 Găsit skin nou: {rarity_emoji} {case_type.upper()} - {skin_full_name} - {price}")
            
            if not new_skins:
                print(f"   ℹ️  Niciun skin nou găsit pe pagina de profil")
            else:
                print(f"   ✅ Total {len(new_skins)} skin-uri noi extrase")
            
            return new_skins
            
        except Exception as e:
            print(f"   ❌ Eroare la extragere din profil: {e}")
            import traceback
            traceback.print_exc()
            return []
    
    async def open_free_case_on_page(self, page, account_name, case_type):
        """Deschide case direct de pe pagina /free-cases fără să navigheze"""
        print(f"📦 Deschid {case_type} direct de pe /free-cases...")
        
        try:
            # Așteaptă ca pagina să fie gata
            await asyncio.sleep(2)
            
            # Găsește link-ul către case (pentru a identifica secțiunea)
            case_link = f'/free-cases/{case_type}'
            
            # Caută butonul "Open" în HTML folosind selector
            # Strategia: găsește anchor-ul cu href=/free-cases/{case_type}, 
            # apoi caută butonul "Open" în div-ul părinte
            
            content = await page.get_content()
            
            # Verifică dacă case-ul este disponibil (nu pe cooldown, nu locked)
            case_pos = content.find(f'href="{case_link}"')
            if case_pos == -1:
                print(f"   ❌ Nu am găsit link-ul pentru {case_type}")
                return None
            
            # Extrage secțiunea (2000 caractere după link)
            section = content[case_pos:case_pos + 2000]
            
            # Verifică din nou dacă are timer sau e locked
            if 'ri-timer-line' in section:
                print(f"   ⏰ {case_type.upper()} este pe cooldown")
                return None
            
            if 'si-ch-lock' in section or 'disabled=""' in section:
                print(f"   🔒 {case_type.upper()} este blocat")
                return None
            
            # Caută butonul "Open" folosind click pe link-ul case-ului
            # Mai simplu: click pe anchor care duce la /free-cases/{case_type}
            try:
                # Găsește anchor-ul cu href="/free-cases/{case_type}"
                links = await page.select_all(f'a[href="{case_link}"]')
                
                if not links:
                    print(f"   ❌ Nu am găsit link-ul {case_link}")
                    return None
                
                # Click pe primul link (care duce la pagina case-ului)
                link = links[0]
                await link.scroll_into_view()
                await asyncio.sleep(0.5)
                await link.click()
                print(f"   ✓ Click pe case {case_type.upper()}")
                
                # Așteaptă să se încarce pagina case-ului
                await asyncio.sleep(3)
                
                # Acum suntem pe /free-cases/{case_type}
                # Caută butonul "Open for Free" pe această pagină
                button = None
                
                # Strategia 1: data-testid="open-button"
                try:
                    button = await page.query_selector('button[data-testid="open-button"]')
                    if button:
                        is_disabled = await button.get_attribute('disabled')
                        if is_disabled is not None:
                            print(f"   ⚠️  Buton disabled")
                            return None
                        print(f"   🔓 Buton găsit: open-button")
                except:
                    pass
                
                # Strategia 2: caută buton cu text "Open"
                if not button:
                    buttons = await page.select_all('button')
                    for btn in buttons:
                        try:
                            text = await btn.text
                            if text and 'open' in text.lower():
                                is_disabled = await btn.get_attribute('disabled')
                                if is_disabled is None:
                                    button = btn
                                    print(f"   🔓 Buton găsit cu text: {text}")
                                    break
                        except:
                            continue
                
                if not button:
                    print(f"   ❌ Nu am găsit butonul OPEN pentru {case_type}")
                    return None
                
                # Click pe butonul Open
                await button.scroll_into_view()
                await asyncio.sleep(0.5)
                await button.click()
                print(f"   ✓ Click pe butonul OPEN")
                
                # Așteaptă animația de deschidere
                print(f"   ⏳ Aștept animație (15s)...")
                await asyncio.sleep(15)
                
                # Verificăm doar dacă a apărut o eroare (playtime insuficient)
                content = await page.get_content()
                
                # Verifică erori (playtime insuficient)
                import re
                content_without_scripts = re.sub(r'<script[^>]*>.*?</script>', '', content, flags=re.DOTALL | re.IGNORECASE)
                
                error_patterns = [
                    r'<div[^>]*class="[^"]*notification[^"]*"[^>]*>.*?Insufficient.*?CS.*?playtime.*?</div>',
                    r'<div[^>]*class="[^"]*error[^"]*"[^>]*>.*?Insufficient.*?CS.*?playtime.*?</div>',
                    r'<p[^>]*class="[^"]*error[^"]*"[^>]*>.*?Insufficient.*?CS.*?playtime.*?</p>'
                ]
                
                has_error = False
                for pattern in error_patterns:
                    if re.search(pattern, content_without_scripts, re.IGNORECASE | re.DOTALL):
                        has_error = True
                        break
                
                if has_error:
                    print(f"   ❌ EROARE: Playtime CS:GO/CS2 insuficient!")
                    return False
                
                print(f"   ✅ Case {case_type.upper()} deschis cu succes")
                return True
                
            except Exception as e:
                print(f"   ❌ Eroare la click: {e}")
                return False
            
        except Exception as e:
            print(f"   ❌ Eroare: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def send_telegram_message(self, message):
        """Trimite mesaj pe Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("Telegram nu este configurat.")
            return
        
        url = f"https://api.telegram.org/bot{self.telegram_token}/sendMessage"
        data = {
            "chat_id": self.telegram_chat_id,
            "text": message,
            "parse_mode": "HTML"
        }
        
        try:
            response = requests.post(url, data=data)
            if response.status_code == 200:
                print("✅ Mesaj trimis pe Telegram")
            else:
                print(f"❌ Eroare Telegram: {response.text}")
        except Exception as e:
            print(f"❌ Eroare Telegram: {e}")
    
    def format_telegram_report(self, all_results):
        """Formatează raportul pentru Telegram"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"🎰 <b>Casehug Daily Report</b>\n"
        message += f"📅 {now}\n"
        message += f"{'─'*30}\n\n"
        
        for account_data in all_results:
            if account_data is None:
                continue
            
            message += f"<b>{account_data['account']}</b>\n"
            
            if account_data['results']:
                for result in account_data['results']:
                    case_name = result['case'].upper()
                    skin = result['skin']
                    price = result['price']
                    rarity = result.get('rarity', '⚪')  # Default la alb dacă nu există
                    message += f"{rarity} {case_name}: {skin} - {price}\n"
            else:
                message += "❌ Niciun skin nou\n"
            
            message += f"\n"
        
        message += f"{'─'*30}\n"
        
        return message
    
    async def run(self):
        """Rulează botul"""
        print("🚀 Pornire CasehugBot (Nodriver)...")
        print(f"📊 Număr conturi: {len(self.accounts)}")
        print("🛡️  Bypass Cloudflare: AUTOMAT (Nodriver - 11.22s avg)\n")
        
        try:
            # Setup browser (minimal pentru Nodriver)
            await self.setup_browser()
            
            # Procesează TOATE conturile
            all_results = []
            for account in self.accounts:
                print(f"\n🧪 Procesez: {account['name']}\n")
                result = await self.process_account(account)
                all_results.append(result)
                
                # Salvează timestamp dacă a procesat cu succes
                if result and result.get('results'):
                    # A deschis cel puțin un case cu succes
                    self.save_account_timestamp(account['name'], had_success=True)
                elif result:
                    # A fost procesat dar fără case-uri (cooldown, locked, etc)
                    self.save_account_timestamp(account['name'], had_success=False)
                
                # Pauză între conturi
                if account != self.accounts[-1]:  # Nu aștepta după ultimul cont
                    print("\n⏳ Pauză 10s până la următorul cont (cleanup browser)...")
                    await asyncio.sleep(10)
            
            # Trimite raport Telegram
            if any(r is not None for r in all_results):
                report = self.format_telegram_report(all_results)
                self.send_telegram_message(report)
            
            print("\n✅ Toate conturile procesate!")
            
        except Exception as e:
            print(f"❌ Eroare: {e}")
            import traceback
            traceback.print_exc()

async def main():
    bot = CasehugBotNodriver()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
