import os
import json
import time
import asyncio
from datetime import datetime
from playwright.async_api import async_playwright, Browser, Page
import requests

# Configurație
CONFIG_FILE = "config.json"

class CasehugBotPlaywright:
    def __init__(self, config_file=CONFIG_FILE):
        """Inițializează botul cu configurația din fișier"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.telegram_token = self.config.get('telegram_bot_token', '')
        self.telegram_chat_id = self.config.get('telegram_chat_id', '')
        self.accounts = self.config.get('accounts', [])
        self.playwright = None
        self.browser = None
        self.pages = []
    
    async def setup_browser(self):
        """Configurează Playwright browser cu stealth maxim"""
        print("   🎭 Inițializez Playwright...")
        
        # Detectăm dacă suntem în Docker
        chrome_bin = os.environ.get('CHROME_BIN')
        is_docker = chrome_bin and os.path.exists(chrome_bin)
        has_xvfb = os.environ.get('DISPLAY') is not None
        
        if is_docker:
            print(f"   🐳 Folosesc Chromium din Docker: {chrome_bin}")
        if has_xvfb:
            print(f"   🖥️  Xvfb detectat: DISPLAY={os.environ.get('DISPLAY')}")
        
        # Launch browser cu argumente anti-detection
        launch_options = {
            'headless': not has_xvfb,  # Vizibil dacă avem Xvfb
            'args': [
                '--no-sandbox',
                '--disable-setuid-sandbox',
                '--disable-dev-shm-usage',
                '--disable-blink-features=AutomationControlled',
                '--disable-infobars',
                '--window-size=1920,1080',
                '--start-maximized',
            ]
        }
        
        if is_docker and chrome_bin:
            launch_options['executable_path'] = chrome_bin
        
        self.playwright = await async_playwright().start()
        
        # Chromium browser (Playwright's built-in)
        self.browser = await self.playwright.chromium.launch(**launch_options)
        
        print(f"   ✅ Playwright browser pornit în mod {'VIZIBIL (Xvfb)' if has_xvfb else 'headless'}")
        return self.browser
    
    async def create_page_with_stealth(self, account_name):
        """Creează o pagină nouă cu stealth maxim"""
        # Context cu user agent real
        context = await self.browser.new_context(
            user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
            timezone_id='Europe/Bucharest',
            permissions=[],
            color_scheme='light',
            extra_http_headers={
                'Accept-Language': 'en-US,en;q=0.9',
                'Accept-Encoding': 'gzip, deflate, br',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            }
        )
        
        page = await context.new_page()
        
        # Anti-detection scripts
        await page.add_init_script("""
            // Overwrite the `navigator.webdriver` property
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined,
            });
            
            // Overwrite the `plugins` property
            Object.defineProperty(navigator, 'plugins', {
                get: () => [1, 2, 3, 4, 5],
            });
            
            // Overwrite the `languages` property
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en'],
            });
            
            // Pass the Chrome Test
            window.chrome = {
                runtime: {},
            };
            
            // Pass the Permissions Test
            const originalQuery = window.navigator.permissions.query;
            window.navigator.permissions.query = (parameters) => (
                parameters.name === 'notifications' ?
                    Promise.resolve({ state: Notification.permission }) :
                    originalQuery(parameters)
            );
        """)
        
        print(f"   ✅ Pagină creată cu stealth pentru {account_name}")
        return page
    
    async def load_cookies(self, page: Page, account_name):
        """Încarcă cookie-uri salvate"""
        try:
            # Detectează numărul contului
            import re
            match = re.search(r'(\d+)', account_name)
            if match:
                cont_nr = match.group(1)
                cookies_file = f"cookies_cont{cont_nr}.json"
            else:
                cookies_file = "cookies.json"
            
            if not os.path.exists(cookies_file):
                print(f"   ⚠️  Fișier cookie lipsă: {cookies_file}")
                return False
            
            print(f"   🍪 Găsit fișier cookies: {cookies_file}")
            
            # Încarcă cookie-urile
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            if not cookies or len(cookies) == 0:
                print(f"   ⚠️  Fișier cookie gol")
                return False
            
            # Deschide site-ul pentru a seta domeniul
            await page.goto("https://casehug.com")
            await page.wait_for_timeout(1000)
            
            # Convertește cookies din format Selenium la Playwright
            playwright_cookies = []
            for cookie in cookies:
                try:
                    playwright_cookie = {
                        'name': cookie['name'],
                        'value': cookie['value'],
                        'domain': cookie.get('domain', '.casehug.com'),
                        'path': cookie.get('path', '/'),
                    }
                    if 'expires' in cookie and cookie['expires']:
                        playwright_cookie['expires'] = float(cookie['expires'])
                    if 'httpOnly' in cookie:
                        playwright_cookie['httpOnly'] = cookie['httpOnly']
                    if 'secure' in cookie:
                        playwright_cookie['secure'] = cookie['secure']
                    if 'sameSite' in cookie:
                        playwright_cookie['sameSite'] = cookie['sameSite']
                    
                    playwright_cookies.append(playwright_cookie)
                except:
                    pass
            
            # Adaugă cookies
            await page.context.add_cookies(playwright_cookies)
            print(f"   ✅ Cookie-uri încărcate: {len(playwright_cookies)}/{len(cookies)}")
            
            # Refresh pentru a activa cookies
            await page.reload()
            await page.wait_for_timeout(2000)
            
            return True
            
        except Exception as e:
            print(f"   ⚠️ Eroare la încărcare cookies: {e}")
            return False
    
    async def check_cloudflare(self, page: Page):
        """Verifică dacă Cloudflare este activ"""
        try:
            content = await page.content()
            content_lower = content.lower()
            
            if any(indicator in content_lower for indicator in ['cloudflare', 'checking your browser', 'just a moment', 'ddos protection']):
                print("   ⚠️ Cloudflare challenge detectat!")
                
                # Așteaptă automat pentru Cloudflare challenge (Playwright e mai bun la asta)
                print("   🕐 Aștept Cloudflare challenge să se rezolve (max 30s)...")
                
                # Așteaptă ca Cloudflare să dispară
                try:
                    await page.wait_for_function(
                        "() => !document.body.textContent.includes('Cloudflare') && !document.body.textContent.includes('Just a moment')",
                        timeout=30000
                    )
                    print("   ✅ Cloudflare challenge trecut!")
                    return True
                except:
                    print("   ❌ Cloudflare challenge nu a fost trecut în 30s")
                    return False
            
            return True
            
        except Exception as e:
            print(f"   ⚠️ Eroare verificare Cloudflare: {e}")
            return True
    
    async def save_page_debug_info(self, page: Page, account_name, page_name):
        """Salvează HTML și screenshot pentru debugging"""
        try:
            debug_dir = "debug_output"
            os.makedirs(debug_dir, exist_ok=True)
            
            # Salvează HTML
            content = await page.content()
            html_file = os.path.join(debug_dir, f"debug_{account_name.replace(' ', '_')}_{page_name}.html")
            with open(html_file, 'w', encoding='utf-8') as f:
                f.write(content)
            
            # Salvează screenshot
            png_file = os.path.join(debug_dir, f"debug_{account_name.replace(' ', '_')}_{page_name}.png")
            await page.screenshot(path=png_file, full_page=True)
            
            print(f"   📄 Debug salvat: {os.path.basename(html_file)}, {os.path.basename(png_file)}")
            
        except Exception as e:
            print(f"   ⚠️ Eroare la salvare debug: {e}")
    
    async def open_free_case(self, page: Page, account_name, case_type):
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
            # Navigare directă
            await page.goto(case_url, wait_until='domcontentloaded', timeout=60000)
            await page.wait_for_timeout(3000)
            
            # Check Cloudflare
            cloudflare_ok = await self.check_cloudflare(page)
            
            # Salvează debug
            await self.save_page_debug_info(page, account_name, f"free_case_{case_type}")
            
            # Scroll
            await page.evaluate("window.scrollTo(0, 400)")
            await page.wait_for_timeout(1000)
            
            # Caută butonul OPEN/CLAIM
            print(f"   🔍 Caut butonul OPEN/CLAIM...")
            
            # Selectoare posibile
            button_selectors = [
                'button:has-text("Open")',
                'button:has-text("Claim")',
                'button:has-text("Free")',
                'button:has-text("Get")',
                'a:has-text("Open")',
                'a:has-text("Claim")',
                '.btn:has-text("Open")',
                '.btn:has-text("Claim")',
                'button[class*="open"]',
                'button[class*="claim"]',
                'button[class*="primary"]',
            ]
            
            button = None
            for selector in button_selectors:
                try:
                    button = await page.query_selector(selector)
                    if button and await button.is_visible():
                        print(f"   ✓ Găsit buton cu: {selector}")
                        break
                except:
                    continue
            
            if not button:
                print(f"   ❌ Nu am găsit butonul OPEN")
                return {
                    "case": case_type,
                    "skin": "Buton lipsă",
                    "price": "N/A"
                }
            
            # Click pe buton
            await button.scroll_into_view_if_needed()
            await page.wait_for_timeout(500)
            await button.click()
            print(f"   ✓ Click pe butonul OPEN")
            
            # Așteaptă rezultatul
            await page.wait_for_timeout(5000)
            
            # Salvează debug după click
            await self.save_page_debug_info(page, account_name, f"after_open_{case_type}")
            
            # Caută skinul și prețul
            print(f"   🔍 Caut rezultatul...")
            
            skin_name = "Necunoscut"
            price = "N/A"
            
            # Caută skin
            skin_selectors = [
                '.item-name', '.skin-name', '.reward-name',
                '.item-title', '.skin-title', '.reward-title',
                '[class*="item"][class*="name"]',
                '[class*="skin"][class*="name"]',
                'h2', 'h3', 'h4'
            ]
            
            for selector in skin_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for elem in elements:
                        if await elem.is_visible():
                            text = (await elem.text_content()).strip()
                            if text and len(text) > 3 and '-' in text or '|' in text or '(' in text:
                                skin_name = text
                                print(f"   ✓ Skin: {skin_name}")
                                break
                    if skin_name != "Necunoscut":
                        break
                except:
                    continue
            
            # Caută preț
            price_selectors = [
                '.price', '.value', '.amount', '.cost',
                '[class*="price"]', '[class*="value"]'
            ]
            
            for selector in price_selectors:
                try:
                    elements = await page.query_selector_all(selector)
                    for elem in elements:
                        if await elem.is_visible():
                            text = (await elem.text_content()).strip()
                            if text and ('$' in text or '€' in text or any(c.isdigit() for c in text)):
                                price = text
                                print(f"   ✓ Preț: {price}")
                                break
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
        
        # Creează pagină nouă pentru acest cont
        page = await self.create_page_with_stealth(account_name)
        
        try:
            # Încarcă cookies
            await self.load_cookies(page, account_name)
            
            # Procesează fiecare case
            results = []
            for case_type in available_cases:
                result = await self.open_free_case(page, account_name, case_type)
                if result:
                    results.append(result)
                await page.wait_for_timeout(2000)
            
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
            self.pages.append(page)
    
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
        print("🚀 Pornire CasehugBot (Playwright)...")
        print(f"📊 Număr conturi: {len(self.accounts)}\n")
        
        try:
            # Setup browser
            await self.setup_browser()
            
            # Procesează fiecare cont
            all_results = []
            for account in self.accounts:
                result = await self.process_account(account)
                all_results.append(result)
            
            # Trimite raport Telegram
            if any(r is not None for r in all_results):
                report = self.format_telegram_report(all_results)
                self.send_telegram_message(report)
            
            print("\n✅ Toate conturile procesate!")
            
        except Exception as e:
            print(f"❌ Eroare: {e}")
            import traceback
            traceback.print_exc()
        finally:
            # Cleanup
            if self.browser:
                await self.browser.close()
            if self.playwright:
                await self.playwright.stop()

async def main():
    bot = CasehugBotPlaywright()
    await bot.run()

if __name__ == "__main__":
    asyncio.run(main())
