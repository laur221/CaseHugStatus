import os
import json
import time
import asyncio
from datetime import datetime
import nodriver as uc
from nodriver import cdp  # Chrome DevTools Protocol pentru cookies
import requests
from twocaptcha import TwoCaptcha

# Configurație
CONFIG_FILE = "config.json"

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
            ] + (['--start-maximized'] if not is_docker else [])
        )
        
        # Prima tab deschisă automat
        page = browser.main_tab
        
        print(f"   ✅ Browser Nodriver gata pentru {account_name}")
        print(f"   🛡️  Cloudflare va fi trecut automat (avg 11.22s)")
        
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
    
    async def save_page_debug_info(self, page, account_name, page_name):
        """Salvează HTML și screenshot pentru debugging"""
        try:
            debug_dir = "debug_output"
            os.makedirs(debug_dir, exist_ok=True)
            
            # Salvează HTML
            content = await page.get_content()
            html_file = os.path.join(debug_dir, f"debug_{account_name.replace(' ', '_')}_{page_name}.html")
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Salvează screenshot
            png_file = os.path.join(debug_dir, f"debug_{account_name.replace(' ', '_')}_{page_name}.png")
            await page.save_screenshot(png_file)
            
            print(f"   📄 Debug salvat: {os.path.basename(html_file)}, {os.path.basename(png_file)}")
            
        except Exception as e:
            print(f"   ⚠️ Eroare la salvare debug: {e}")
    
    async def open_free_case(self, page, account_name, case_type):
        """Deschide un free case specific"""
        case_urls = {
            "discord": "https://casehug.com/free-cases/discord",
            "steam": "https://casehug.com/free-cases/steam",
            "wood": "https://casehug.com/free-cases/wood"
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
            
            # Salvează debug
            await self.save_page_debug_info(page, account_name, f"free_case_{case_type}")
            
            # Scroll
            await page.evaluate("window.scrollTo(0, 400)")
            await asyncio.sleep(1)
            
            # Caută butonul OPEN/CLAIM
            print(f"   🔍 Caut butonul 'Open for Free'...")
            
            # Selectoare posibile - Nodriver foloseste CSS selectors
            button_texts = ["Open for Free", "Open", "Claim", "Free", "Get"]
            
            button = None
            for text in button_texts:
                try:
                    # Caută butoane cu text specific
                    buttons = await page.select_all("button")
                    for btn in buttons:
                        try:
                            btn_text = await btn.text
                            if btn_text and text.lower() in btn_text.lower():
                                button = btn
                                print(f"   ✓ Găsit buton cu text: {text}")
                                break
                        except:
                            continue
                    
                    if button:
                        break
                    
                    # Încearcă și cu link-uri
                    links = await page.select_all("a")
                    for link in links:
                        try:
                            link_text = await link.text
                            if link_text and text.lower() in link_text.lower():
                                button = link
                                print(f"   ✓ Găsit link cu text: {text}")
                                break
                        except:
                            continue
                    
                    if button:
                        break
                except Exception as e:
                    continue
            
            if not button:
                print(f"   ❌ Nu am găsit butonul OPEN")
                return {
                    "case": case_type,
                    "skin": "Buton lipsă",
                    "price": "N/A"
                }
            
            # Click pe buton
            await button.scroll_into_view()
            await asyncio.sleep(0.5)
            await button.click()
            print(f"   ✓ Click pe butonul OPEN")
            
            # Așteaptă rezultatul
            await asyncio.sleep(5)
            
            # Salvează debug după click
            await self.save_page_debug_info(page, account_name, f"after_open_{case_type}")
            
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
        """Procesează un cont"""
        account_name = account['name']
        available_cases = account['available_cases']
        
        print(f"\n{'='*50}")
        print(f"🎮 Procesez contul: {account_name}")
        print(f"{'='*50}")
        
        # În Docker: Crează sesiune FlareSolverr pentru acest cont  
        if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
            await self.create_flaresolverr_session(account_name)
        
        # Creează browser Nodriver cu profil persistent
        page, browser = await self.create_page_with_stealth(account_name)
        
        try:
            # Procesează fiecare case
            results = []
            for case_type in available_cases:
                result = await self.open_free_case(page, account_name, case_type)
                if result:
                    results.append(result)
                await asyncio.sleep(2)
            
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
            # Închide sesiune FlareSolverr în Docker
            if hasattr(self, 'flaresolverr_primary') and self.flaresolverr_primary:
                await self.destroy_flaresolverr_session(account_name)
            
            # Închide browser-ul
            try:
                await browser.stop()
                print(f"   ✅ Browser închis pentru {account_name}")
            except:
                pass
    
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
            
            message += f"👤 <b>{account_data['account']}</b>\n\n"
            
            for result in account_data['results']:
                message += f"  📦 {result['case']}:\n"
                message += f"     🎁 {result['skin']}\n"
                message += f"     💵 {result['price']}\n\n"
            
            message += f"{'─'*30}\n\n"
        
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
                print(f"\n🧪 Test cu: {account['name']}\n")
                result = await self.process_account(account)
                all_results.append(result)
                
                # Pauză între conturi
                if account != self.accounts[-1]:  # Nu aștepta după ultimul cont
                    print("\n⏳ Pauză 5s până la următorul cont...")
                    await asyncio.sleep(5)
            
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
