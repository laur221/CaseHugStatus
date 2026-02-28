import os
import json
import time
import asyncio
from datetime import datetime
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
from threading import Thread
from selenium_stealth import stealth

# Configurație
CONFIG_FILE = "config.json"

class CasehugBot:
    def __init__(self, config_file=CONFIG_FILE):
        """Inițializează botul cu configurația din fișier"""
        with open(config_file, 'r', encoding='utf-8') as f:
            self.config = json.load(f)
        
        self.telegram_token = self.config.get('telegram_bot_token', '')
        self.telegram_chat_id = self.config.get('telegram_chat_id', '')
        self.accounts = self.config.get('accounts', [])
        self.browsers = []
        
    def setup_browser(self, account_name, profile_dir):
        """Configurează un browser Chrome cu profil persistent și bypass Cloudflare"""
        # Detectăm dacă suntem în Docker
        chrome_bin = os.environ.get('CHROME_BIN')
        is_docker = chrome_bin and os.path.exists(chrome_bin)
        
        # Detectăm dacă Xvfb este disponibil (DISPLAY setat)
        has_xvfb = os.environ.get('DISPLAY') is not None
        
        if is_docker:
            print(f"   🐳 Folosesc Chromium din Docker: {chrome_bin}")
        if has_xvfb:
            print(f"   🖥️  Xvfb detectat: DISPLAY={os.environ.get('DISPLAY')} - Folosesc browser VIZIBIL pentru bypass Cloudflare")
        
        # Configurare Chrome Options cu stealth maxim
        chrome_options = Options()
        
        # Setări profil - DOAR pentru non-Docker (profile-urile cauzează probleme în Docker)
        if not is_docker:
            profile_path = os.path.join(os.getcwd(), "profiles", profile_dir)
            os.makedirs(profile_path, exist_ok=True)
            chrome_options.add_argument(f"--user-data-dir={profile_path}")
            chrome_options.add_argument("--profile-directory=Default")
        
        # HEADLESS DOAR dacă NU avem Xvfb (dacă avem Xvfb, browser-ul va fi vizibil în display virtual)
        if not has_xvfb:
            print("   ⚠️  Folosesc headless mode (fără Xvfb) - Cloudflare poate bloca")
            chrome_options.add_argument("--headless=new")
        
        # Argumente esențiale pentru Docker
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-setuid-sandbox")
        chrome_options.add_argument("--remote-debugging-port=9222")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--start-maximized")
        
        # Anti-detection avansate
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation", "enable-logging"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-infobars")
        chrome_options.add_argument("--disable-plugins-discovery")
        
        # Log level minimal
        chrome_options.add_argument("--log-level=3")
        chrome_options.add_argument("--silent")
        chrome_options.add_argument("--disable-logging")
        
        # User agent realist (important pentru Cloudflare)
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        # Preferințe browser pentru bypass detection
        prefs = {
            "credentials_enable_service": False,
            "profile.password_manager_enabled": False,
            "profile.default_content_setting_values.notifications": 2,
            "profile.default_content_settings.popups": 0,
        }
        chrome_options.add_experimental_option("prefs", prefs)
        
        # Path-uri pentru Docker
        if is_docker:
            chrome_options.binary_location = chrome_bin
        
        try:
            # Creează service pentru chromedriver
            if is_docker:
                service = Service(
                    executable_path='/usr/bin/chromedriver',
                    log_path='/dev/null'  # Suppress verbose logs
                )
            else:
                service = Service()  # Auto-detect
            
            # Inițializează driver
            driver = webdriver.Chrome(service=service, options=chrome_options)
            
            # Aplică selenium-stealth pentru bypass Cloudflare
            stealth(driver,
                languages=["en-US", "en"],
                vendor="Google Inc.",
                platform="Win32",
                webgl_vendor="Intel Inc.",
                renderer="Intel Iris OpenGL Engine",
                fix_hairline=True,
                run_on_insecure_origins=False,
            )
            
            # Script-uri adiționale anti-detection
            driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
                "source": """
                    Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
                    Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
                    Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
                    window.chrome = {runtime: {}};
                """
            })
            
            # Timeout-uri
            driver.set_page_load_timeout(60)
            driver.implicitly_wait(5)
            
            mode = "VIZIBIL (Xvfb)" if has_xvfb else "headless"
            print(f"   ✅ Browser configurat în mod {mode} pentru {account_name}")
            return driver
            
        except Exception as e:
            print(f"   ❌ Eroare critică la crearea browser-ului: {e}")
            import traceback
            traceback.print_exc()
            raise
    
    def send_telegram_message(self, message):
        """Trimite mesaj pe Telegram"""
        if not self.telegram_token or not self.telegram_chat_id:
            print("Telegram nu este configurat. Mesaj:", message)
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
            print(f"❌ Eroare la trimitere Telegram: {e}")
    
    def close_popups(self, driver):
        """Închide popup-uri, cookie banners, etc."""
        try:
            # Încearcă să închidă diverse tipuri de popup-uri
            popup_selectors = [
                "button[class*='close']",
                "button[class*='dismiss']",
                ".modal-close",
                ".popup-close",
                "[aria-label='Close']",
                "button:contains('Accept')",
                "button:contains('OK')",
                ".cookie-accept",
                ".cookie-close"
            ]
            
            for selector in popup_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector.split(':')[0])
                    for elem in elements:
                        if elem.is_displayed():
                            elem.click()
                            time.sleep(0.5)
                            print("   ✓ Popup închis")
                except:
                    pass
        except:
            pass
    
    def save_page_debug_info(self, driver, account_name, page_name):
        """Salvează HTML și screenshot pentru debugging"""
        try:
            # Creăm directorul de debug dacă nu există
            debug_dir = "debug_output"
            os.makedirs(debug_dir, exist_ok=True)
            
            # Salvează HTML
            html_filename = os.path.join(debug_dir, f"debug_{account_name}_{page_name}.html")
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            # Salvează screenshot
            screenshot_filename = os.path.join(debug_dir, f"debug_{account_name}_{page_name}.png")
            driver.save_screenshot(screenshot_filename)
            
            print(f"   📄 Debug salvat: {os.path.basename(html_filename)}, {os.path.basename(screenshot_filename)}")
        except Exception as e:
            print(f"   ⚠️ Nu am putut salva debug info: {e}")
    
    def parse_page_structure(self, driver, page_name="unknown"):
        """Analizează structura paginii și afișează informații utile"""
        try:
            print(f"\n🔍 Analizez structura paginii: {page_name}")
            
            # Găsește toate elementele cu text vizibil
            all_elements = driver.find_elements(By.XPATH, "//*[normalize-space(text())]")
            
            print(f"   📊 Total elemente cu text: {len(all_elements)}")
            
            # Găsește toate link-urile
            links = driver.find_elements(By.TAG_NAME, "a")
            visible_links = [link for link in links if link.is_displayed()]
            print(f"   🔗 Link-uri vizibile: {len(visible_links)}")
            
            # Găsește toate butoanele
            buttons = driver.find_elements(By.TAG_NAME, "button")
            visible_buttons = [btn for btn in buttons if btn.is_displayed()]
            print(f"   🔘 Butoane vizibile: {len(visible_buttons)}")
            
            # Afișează primele 5 butoane și link-uri pentru debugging
            print(f"\n   📋 Primele butoane găsite:")
            for i, btn in enumerate(visible_buttons[:5]):
                text = btn.text.strip()[:50]
                classes = btn.get_attribute('class')
                print(f"      {i+1}. [{text}] - class: {classes}")
            
            print(f"\n   📋 Primele link-uri găsite:")
            for i, link in enumerate(visible_links[:5]):
                text = link.text.strip()[:50]
                href = link.get_attribute('href')
                print(f"      {i+1}. [{text}] - href: {href}")
            
        except Exception as e:
            print(f"   ⚠️ Eroare la parsare: {e}")
    
    def load_cookies(self, driver, account_name, cookies_file=None):
        """Încarcă cookie-uri salvate pentru bypass Cloudflare și login"""
        try:
            # Detectează numărul contului din nume (ex: "Cont 1" -> 1)
            if cookies_file is None:
                # Extrage numărul din numele contului
                import re
                match = re.search(r'(\d+)', account_name)
                if match:
                    cont_nr = match.group(1)
                    cookies_file = f"cookies_cont{cont_nr}.json"
                else:
                    # Fallback la cookies.json generic
                    cookies_file = "cookies.json"
            
            if not os.path.exists(cookies_file):
                print(f"   ⚠️  Fișier cookie lipsă: {cookies_file}")
                print(f"   💡 Rulează: python save_cookies.py pentru a salva cookie-uri pentru {account_name}")
                return False
            
            print(f"   🍪 Găsit fișier cookies: {cookies_file}")
            
            # Deschide site-ul o dată pentru a seta domeniul
            driver.get("https://casehug.com")
            time.sleep(1)
            
            # Încarcă cookie-urile
            with open(cookies_file, 'r', encoding='utf-8') as f:
                cookies = json.load(f)
            
            if not cookies or len(cookies) == 0:
                print(f"   ⚠️  Fișier cookie gol: {cookies_file}")
                return False
            
            # Adaugă fiecare cookie
            cookies_added = 0
            for cookie in cookies:
                try:
                    # Unele cookie-uri pot avea câmpuri incompatibile
                    if 'sameSite' in cookie and cookie['sameSite'] not in ['Strict', 'Lax', 'None']:
                        cookie['sameSite'] = 'Lax'
                    driver.add_cookie(cookie)
                    cookies_added += 1
                except Exception as e:
                    # Ignoră cookie-urile care nu pot fi adăugate
                    pass
            
            print(f"   ✅ Cookie-uri încărcate pentru {account_name}: {cookies_added}/{len(cookies)} adăugate")
            return True
            
        except Exception as e:
            print(f"   ⚠️ Eroare la încărcare cookies: {e}")
            return False
    
    def login_steam(self, driver, account_name):
        """Verifică dacă este logat sau redirecționează spre login Steam"""
        print(f"\n🔑 Verificare login pentru contul: {account_name}")
        
        try:
            # ÎNCARCĂ COOKIE-URI DACĂ EXISTĂ (bypass Cloudflare + login automat)
            cookies_loaded = self.load_cookies(driver, account_name)
            
            if cookies_loaded:
                # Refresh pagina cu cookie-urile încărcate
                print("   🔄 Refresh pagină cu cookie-uri...")
                driver.refresh()
                time.sleep(3)
            else:
                # Deschide casehug.com normal
                driver.get("https://casehug.com")
                time.sleep(3)
            
            # Detectăm Cloudflare challenge
            cloudflare_detected = False
            try:
                # Caută indicatori Cloudflare
                page_source = driver.page_source.lower()
                if any(indicator in page_source for indicator in ['cloudflare', 'checking your browser', 'just a moment', 'ddos protection']):
                    cloudflare_detected = True
                    print("   ⚠️ Cloudflare challenge detectat! Aștept 15 secunde...")
                    time.sleep(15)  # Așteptăm să treacă challenge-ul
                    # Re-check daca a trecut
                    page_source = driver.page_source.lower()
                    if any(indicator in page_source for indicator in ['cloudflare', 'checking your browser']):
                        print("   ❌ Cloudflare challenge nu a fost trecut automat!")
                        print("   💡 Site-ul folosește protecție anti-bot puternică.")
                    else:
                        print("   ✅ Cloudflare challenge trecut!")
            except:
                pass
            
            time.sleep(2)
            
            # Închide popup-uri/cookie banners
            self.close_popups(driver)
            time.sleep(1)
            
            # Salvează pagina pentru debugging
            self.save_page_debug_info(driver, account_name, "homepage")
            
            # Analizează structura paginii
            self.parse_page_structure(driver, "casehug.com homepage")
            
            # Verifică dacă utilizatorul este deja logat
            # Căutăm mai multe indicii că utilizatorul e logat
            login_indicators = [
                ".user-profile",
                ".username",
                ".profile-btn",
                ".user-info",
                ".user-avatar",
                "[class*='user']",
                "[class*='profile']",
                "img[alt*='avatar']",
                ".balance",
                ".wallet"
            ]
            
            print(f"\n   🔍 Caut indicii de login...")
            for selector in login_indicators:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    # Verifică dacă elementul există și conține text relevant
                    for elem in elements:
                        if elem.is_displayed():
                            text = elem.text.lower()
                            # Dacă găsim indicii clare că e logat
                            if any(word in text for word in ['$', 'balance', 'profile', 'logout', 'settings']) or elem.tag_name == 'img':
                                print(f"✅ {account_name} este deja logat! (găsit: {selector})")
                                return True
                except:
                    continue
            
            # Dacă nu găsim indicii de login, verificăm URL-ul
            if 'profile' in driver.current_url or 'user' in driver.current_url:
                print(f"✅ {account_name} este deja logat! (detectat din URL)")
                return True
            
            print(f"⚠️ {account_name} nu pare să fie logat. Căutăm butonul Steam login...")
            
            # Scroll în sus pentru a vedea header-ul
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Închide popup-uri din nou
            self.close_popups(driver)
            
            # Caută butonul Steam login cu mai multe strategii
            login_selectors = [
                "a[href*='steam']",
                "a[href*='auth']",
                "a[href*='login']",
                "button[class*='steam']",
                ".login-steam",
                ".steam-login",
                "button:contains('Login')",
                "button:contains('Sign in')",
                "[class*='login']",
                "[class*='auth']"
            ]
            
            print(f"\n   🔍 Caut buton login Steam...")
            login_button = None
            for selector in login_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector.split(':')[0])
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            # Verifică dacă textul sau href conține steam/login
                            text = elem.text.lower()
                            href = elem.get_attribute('href') or ''
                            if 'steam' in text or 'steam' in href.lower() or 'login' in text or 'sign' in text:
                                login_button = elem
                                print(f"   ✓ Găsit buton login: {selector} - text: '{text}' - href: '{href[:50]}'")
                                break
                    if login_button:
                        break
                except Exception as e:
                    continue
            
            if not login_button:
                # Ultimă încercare: caută orice link sau buton în header
                print("   ⚠️ Încercăm să găsim header-ul...")
                try:
                    header = driver.find_element(By.TAG_NAME, "header")
                    links = header.find_elements(By.TAG_NAME, "a")
                    buttons = header.find_elements(By.TAG_NAME, "button")
                    
                    for elem in links + buttons:
                        if elem.is_displayed():
                            text = elem.text.lower()
                            href = elem.get_attribute('href') or ''
                            if any(word in text + href.lower() for word in ['login', 'steam', 'sign', 'auth']):
                                login_button = elem
                                print(f"   ✓ Găsit în header: '{text}' - href: '{href[:50]}'")
                                break
                except:
                    pass
            
            if login_button:
                try:
                    # Scroll la element
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", login_button)
                    time.sleep(1)
                    
                    # Încearcă click normal
                    try:
                        login_button.click()
                    except:
                        # Dacă click normal nu merge, folosește JavaScript
                        driver.execute_script("arguments[0].click();", login_button)
                    
                    print(f"🔄 Click pe buton Steam login pentru {account_name}")
                    print("⏸️ Aștept 15 secunde pentru redirect Steam...")
                    time.sleep(15)
                    
                    # Salvează pagina după login pentru debugging
                    self.save_page_debug_info(driver, account_name, "after_login_attempt")
                    
                    # Verifică din nou dacă s-a logat
                    current_url = driver.current_url
                    print(f"   📍 URL curent: {current_url}")
                    
                    # Dacă suntem pe Steam, înseamnă că trebuie login manual
                    if 'steamcommunity.com' in current_url or 'steampowered.com' in current_url:
                        print(f"⚠️ {account_name} trebuie să se logheze pe Steam!")
                        print(f"💡 IMPORTANT: Deschide manual browser și loghează-te pe Steam pentru acest profil.")
                        print(f"⏸️ Aștept 60 secunde...")
                        time.sleep(60)
                        
                        # Revino la casehug
                        driver.get("https://casehug.com")
                        time.sleep(5)
                    
                    # Verifică dacă suntem înapoi pe casehug și logați
                    for selector in login_indicators:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            if elements and elements[0].is_displayed():
                                print(f"✅ Login detectat pentru {account_name}!")
                                return True
                        except:
                            pass
                    
                    # Presupunem că e OK și continuăm
                    print(f"⚠️ Nu am detectat login clar, dar continuăm...")
                    return True
                    
                except Exception as e:
                    print(f"❌ Eroare la click pe buton login: {e}")
                    self.save_page_debug_info(driver, account_name, "login_error")
                    return False
            else:
                print(f"❌ Nu am găsit butonul de login Steam pentru {account_name}")
                print("💡 Site-ul poate avea o structură diferită.")
                print("📄 Verifică fișierele debug_*.html și debug_*.png generate")
                print("⏸️ Aștept 20 secunde să te poți loga manual dacă e nevoie...")
                time.sleep(20)
                return True  # Returnăm True pentru a continua
                    
        except Exception as e:
            print(f"❌ Eroare la login Steam pentru {account_name}: {e}")
            self.save_page_debug_info(driver, account_name, "exception")
            return False
    
    def open_free_cases(self, driver, account_name, available_cases):
        """Deschide casele gratuite direct folosind link-uri specifice"""
        results = []
        
        # Mapping pentru link-uri directe (BYPASS homepage Cloudflare!)
        case_urls = {
            "discord": "https://casehug.com/free-cases/discord",
            "steam": "https://casehug.com/free-cases/steam",
            "wood": "https://casehug.com/free-cases/wood"
        }
        
        for case_type in available_cases:
            try:
                # Verifică dacă există URL pentru acest tip de case
                if case_type.lower() not in case_urls:
                    print(f"\n⚠️  Case type '{case_type}' necunoscut - skip")
                    continue
                
                case_url = case_urls[case_type.lower()]
                print(f"\n📦 Deschid {case_type} pentru {account_name}...")
                print(f"   🌐 Navighez direct la: {case_url}")
                
                # NAVIGARE DIRECTĂ - bypass homepage!
                driver.get(case_url)
                time.sleep(3)
                
                # Detectăm Cloudflare challenge (și pe paginile interne poate fi)
                cloudflare_detected = False
                try:
                    page_source = driver.page_source.lower()
                    if any(indicator in page_source for indicator in ['cloudflare', 'checking your browser', 'just a moment']):
                        cloudflare_detected = True
                        print("   ⚠️ Cloudflare challenge detectat! Aștept 15 secunde...")
                        time.sleep(15)
                        # Re-check
                        page_source = driver.page_source.lower()
                        if 'cloudflare' not in page_source and 'checking your browser' not in page_source:
                            print("   ✅ Cloudflare challenge trecut!")
                        else:
                            print("   ⚠️ Cloudflare încă activ...")
                except:
                    pass
                
                # Închide popup-uri
                self.close_popups(driver)
                time.sleep(1)
                
                # Salvează pagina pentru debugging
                self.save_page_debug_info(driver, account_name, f"free_case_{case_type}")
                
                # Analizează structura paginii
                self.parse_page_structure(driver, f"free case page - {case_type}")
                
                # Scroll pentru a vedea butonul
                driver.execute_script("window.scrollTo(0, 400);")
                time.sleep(1)
                
                # Găsește butonul de OPEN/CLAIM cu mai multe strategii
                open_button = None
                
                print(f"\n   🔍 Caut butonul OPEN/CLAIM pentru '{case_type}'...")
                
                # Strategia 1: Caută după text în butoane
                button_texts = ['open', 'claim', 'получить', 'открыть', 'free', 'deschide', 'ia']
                try:
                    all_buttons = driver.find_elements(By.CSS_SELECTOR, "button, a[role='button'], div[role='button'], [onclick], .btn, .button")
                    for elem in all_buttons:
                        if elem.is_displayed():
                            text = elem.text.lower()
                            classes = (elem.get_attribute('class') or '').lower()
                            
                            # Caută cuvintele cheie
                            if any(keyword in text or keyword in classes for keyword in button_texts):
                                open_button = elem
                                print(f"   ✓ Găsit buton prin text: '{text[:50]}' - class: '{classes[:50]}'")
                                break
                except Exception as e:
                    print(f"   ⚠️ Eroare la căutare buton: {e}")
                
                # Strategia 2: Caută după clase CSS specifice buton
                if not open_button:
                    button_selectors = [
                        "button.open", "button.claim", ".btn-open", ".btn-claim",
                        "[class*='open'][class*='btn']",
                        "[class*='claim'][class*='btn']",
                        "button[class*='primary']",
                        "button[class*='action']",
                        ".primary-button", ".action-button"
                    ]
                    
                    for selector in button_selectors:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector)
                            for elem in elements:
                                if elem.is_displayed() and elem.is_enabled():
                                    open_button = elem
                                    print(f"   ✓ Găsit buton prin selector: {selector}")
                                    break
                            if open_button:
                                break
                        except:
                            continue
                
                # Dacă am găsit butonul, dă click
                if open_button:
                    try:
                        # Scroll la element
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", open_button)
                        time.sleep(1)
                        
                        # Click
                        try:
                            open_button.click()
                        except:
                            driver.execute_script("arguments[0].click();", open_button)
                        
                        print(f"   ✓ Click pe butonul OPEN pentru {case_type}")
                        time.sleep(5)
                        
                        # Salvează pagina după click pentru debugging
                        self.save_page_debug_info(driver, account_name, f"after_open_{case_type}")
                        
                        # Așteaptă să apară skinul câștigat
                        skin_name = "Necunoscut"
                        price = "N/A"
                        
                        print(f"\n   🔍 Caut rezultatul (skin și preț)...")
                        
                        # Caută skinul cu mai multe strategii
                        skin_selectors = [
                            ".item-name", ".skin-name", ".reward-name",
                            ".item-title", ".skin-title", ".reward-title",
                            "[class*='item'][class*='name']",
                            "[class*='skin'][class*='name']",
                            "[class*='reward'][class*='name']",
                            ".name", ".title", "h3", "h4", "h2"
                        ]
                        
                        for selector in skin_selectors:
                            try:
                                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                for elem in elements:
                                    if elem.is_displayed():
                                        text = elem.text.strip()
                                        # Verifică că textul e relevant (nu e "Free", case_type, etc.)
                                        if text and len(text) > 3 and text not in ['Free', case_type, 'Open', 'Claim', 'Collect']:
                                            # Verifică dacă pare un nume de skin (conține - sau |)
                                            if '-' in text or '|' in text or '(' in text:
                                                skin_name = text
                                                print(f"   ✓ Skin găsit: {skin_name}")
                                                break
                                if skin_name != "Necunoscut":
                                    break
                            except:
                                continue
                        
                        # Dacă nu am găsit skin cu -, caută orice text lung
                        if skin_name == "Necunoscut":
                            for selector in skin_selectors:
                                try:
                                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                    for elem in elements:
                                        if elem.is_displayed():
                                            text = elem.text.strip()
                                            if text and len(text) > 5 and text not in ['Free', case_type, 'Open', 'Claim', 'Collect']:
                                                skin_name = text
                                                print(f"   ✓ Skin găsit (alternativ): {skin_name}")
                                                break
                                    if skin_name != "Necunoscut":
                                        break
                                except:
                                    continue
                        
                        # Caută prețul
                        price_selectors = [
                            ".item-price", ".skin-price", ".reward-price",
                            ".price", ".value", ".amount", ".cost",
                            "[class*='price']", "[class*='value']", "[class*='amount']"
                        ]
                        
                        for selector in price_selectors:
                            try:
                                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                for elem in elements:
                                    if elem.is_displayed():
                                        text = elem.text.strip()
                                        if text and ('$' in text or '€' in text or '£' in text or any(c.isdigit() for c in text)):
                                            price = text
                                            print(f"   ✓ Preț găsit: {price}")
                                            break
                                if price != "N/A":
                                    break
                            except:
                                continue
                        
                        results.append({
                            "case": case_type,
                            "skin": skin_name,
                            "price": price
                        })
                        
                        print(f"✅ {case_type}: {skin_name} - {price}")
                        
                    except Exception as e:
                        print(f"⚠️ Eroare la procesare rezultat {case_type}: {e}")
                        results.append({
                            "case": case_type,
                            "skin": "Eroare",
                            "price": "N/A"
                        })
                else:
                    print(f"❌ Nu am găsit butonul OPEN pentru {case_type}")
                    print(f"💡 Verifică fișierele debug pentru a vedea structura paginii")
                    print(f"💡 Butonul OPEN nu este disponibil sau nu a fost găsit pe pagină")
                    results.append({
                        "case": case_type,
                        "skin": "Buton lipsă",
                        "price": "N/A"
                    })
                    
            except Exception as e:
                print(f"❌ Eroare la deschidere {case_type}: {e}")
        
        return results
    
    def get_balance(self, driver):
        """Extrage balanța contului"""
        try:
            # Navighează la home pentru a vedea balanța
            driver.get("https://casehug.com")
            time.sleep(2)
            
            # Caută balanța cu mai multe strategii
            balance_selectors = [
                ".balance", ".wallet-balance", ".user-balance",
                "[class*='balance']", "[class*='wallet']", "[class*='money']",
                ".coins", ".credits", "[class*='coin']", "[class*='credit']"
            ]
            
            for selector in balance_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed():
                            text = elem.text.strip()
                            # Verifică dacă textul conține $ sau cifre
                            if text and ('$' in text or '€' in text or any(c.isdigit() for c in text)):
                                print(f"   ✓ Balanță găsită: {text}")
                                return text
                except:
                    continue
            
            # Dacă nu găsim nimic, returnăm N/A
            return "N/A"
        except Exception as e:
            print(f"   ⚠️ Nu am putut obține balanța: {e}")
            return "N/A"
    
    def process_account(self, account):
        """Procesează un singur cont"""
        account_name = account['name']
        profile_dir = account['profile_dir']
        available_cases = account['available_cases']
        
        print(f"\n{'='*50}")
        print(f"🎮 Procesez contul: {account_name}")
        print(f"{'='*50}")
        
        driver = self.setup_browser(account_name, profile_dir)
        
        try:
            # DIRECT LA FREE CASES - NU MAI ACCESĂM HOMEPAGE (bypass Cloudflare!)
            print(f"\n💡 Merg direct la free-cases URLs (bypass homepage Cloudflare)")
            
            # Deschide casele gratuite (direct la URL-uri specifice)
            results = self.open_free_cases(driver, account_name, available_cases)
            
            # Obține balanța (dacă site-ul permite)
            # Comentat deocamdată pentru a evita accesarea homepage-ului
            # balance = self.get_balance(driver)
            balance = "N/A (skip homepage)"
            
            return {
                "account": account_name,
                "results": results,
                "balance": balance
            }
            
        except Exception as e:
            print(f"❌ Eroare la procesare {account_name}: {e}")
            import traceback
            traceback.print_exc()
            return None
        
        finally:
            # Păstrează browserul deschis sau închide-l
            # driver.quit()  # Decomentează dacă vrei să închizi browserul
            self.browsers.append(driver)
    
    def format_telegram_report(self, all_results):
        """Formatează raportul pentru Telegram"""
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        
        message = f"🎰 <b>Casehug Daily Report</b>\n"
        message += f"📅 {now}\n"
        message += f"{'─'*30}\n\n"
        
        for account_data in all_results:
            if account_data is None:
                continue
                
            message += f"👤 <b>{account_data['account']}</b>\n"
            message += f"💰 Balanță: {account_data['balance']}\n\n"
            
            for result in account_data['results']:
                message += f"  📦 {result['case']}:\n"
                message += f"     🎁 {result['skin']}\n"
                message += f"     💵 {result['price']}\n\n"
            
            message += f"{'─'*30}\n\n"
        
        return message
    
    def run(self):
        """Rulează botul pentru toate conturile"""
        print("🚀 Pornire CasehugBot...")
        print(f"📊 Număr conturi: {len(self.accounts)}\n")
        
        all_results = []
        
        # Procesează fiecare cont
        for account in self.accounts:
            result = self.process_account(account)
            all_results.append(result)
            time.sleep(2)  # Pauză între conturi
        
        # Trimite raport pe Telegram
        report = self.format_telegram_report(all_results)
        self.send_telegram_message(report)
        
        print("\n✅ Finalizat! Browserele rămân deschise.")
        print("💡 Apasă Ctrl+C pentru a închide programa.")
        
        # Așteaptă la infinit (sau până dai Ctrl+C)
        try:
            while True:
                time.sleep(60)
        except KeyboardInterrupt:
            print("\n👋 Închidere...")
            for driver in self.browsers:
                driver.quit()

def main():
    """Funcția principală"""
    if not os.path.exists(CONFIG_FILE):
        print(f"❌ Fișierul {CONFIG_FILE} nu există!")
        print("💡 Creează fișierul config.json cu configurația ta.")
        return
    
    bot = CasehugBot(CONFIG_FILE)
    bot.run()

if __name__ == "__main__":
    main()
