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
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import requests
from threading import Thread

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
        """Configurează un browser Chrome cu profil persistent"""
        chrome_options = Options()
        
        # Creează directorul de profil dacă nu există
        profile_path = os.path.join(os.getcwd(), "profiles", profile_dir)
        os.makedirs(profile_path, exist_ok=True)
        
        # Setări Chrome
        chrome_options.add_argument(f"--user-data-dir={profile_path}")
        chrome_options.add_argument("--profile-directory=Default")
        chrome_options.add_argument("--disable-blink-features=AutomationControlled")
        chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
        chrome_options.add_experimental_option('useAutomationExtension', False)
        
        # Pentru server fără GUI - ACTIVAT
        chrome_options.add_argument("--headless=new")  # Headless mode nou (mai stabil)
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")  # Rezoluție virtuală
        chrome_options.add_argument("--disable-software-rasterizer")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-logging")
        chrome_options.add_argument("--log-level=3")  # Reduce logging
        chrome_options.add_argument("--silent")
        
        # User agent pentru a părea browser normal
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
        
        driver = webdriver.Chrome(options=chrome_options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        # Setează implicit timeout-uri
        driver.set_page_load_timeout(30)
        driver.implicitly_wait(5)
        
        return driver
    
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
            # Salvează HTML
            html_filename = f"debug_{account_name}_{page_name}.html"
            with open(html_filename, "w", encoding="utf-8") as f:
                f.write(driver.page_source)
            
            # Salvează screenshot
            screenshot_filename = f"debug_{account_name}_{page_name}.png"
            driver.save_screenshot(screenshot_filename)
            
            print(f"   📄 Debug salvat: {html_filename}, {screenshot_filename}")
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
    
    def login_steam(self, driver, account_name):
        """Verifică dacă este logat sau redirecționează spre login Steam"""
        print(f"\n🔑 Verificare login pentru contul: {account_name}")
        
        try:
            # Deschide casehug.com
            driver.get("https://casehug.com")
            time.sleep(5)
            
            # Închide popup-uri/cookie banners
            self.close_popups(driver)
            time.sleep(1)
            
            # Salvează screenshot pentru debugging
            try:
                driver.save_screenshot(f"debug_{account_name}_page.png")
            except:
                pass
            
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
            
            print(f"⚠️ {account_name} nu este logat. Căutăm butonul Steam login...")
            
            # Scroll în sus pentru a vedea header-ul
            driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(1)
            
            # Închide popup-uri din nou
            self.close_popups(driver)
            
            # Caută butonul Steam login cu mai multe strategii
            login_selectors = [
                "a[href*='steam']",
                "button[class*='steam']",
                ".login-steam",
                ".steam-login",
                "a[href*='auth']",
                "button:contains('Login')",
                "button:contains('Sign in')",
                "[class*='login']",
                "[class*='auth']"
            ]
            
            login_button = None
            for selector in login_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for elem in elements:
                        if elem.is_displayed() and elem.is_enabled():
                            # Verifică dacă textul sau href conține steam/login
                            text = elem.text.lower()
                            href = elem.get_attribute('href') or ''
                            if 'steam' in text or 'steam' in href or 'login' in text or 'sign' in text:
                                login_button = elem
                                print(f"   ✓ Găsit buton login: {selector}")
                                break
                    if login_button:
                        break
                except:
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
                            if any(word in text + href for word in ['login', 'steam', 'sign', 'auth']):
                                login_button = elem
                                print(f"   ✓ Găsit în header: {text}")
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
                    print("⏸️ Te rog să te loghezi manual în browser (dacă e nevoie).")
                    print("💡 Dacă ești deja logat, browserul va continua automat.")
                    time.sleep(10)
                    
                    # Verifică din nou dacă s-a logat
                    for i in range(5):
                        if 'profile' in driver.current_url or 'user' in driver.current_url or 'casehug.com' in driver.current_url:
                            # Verifică indiciile de login
                            for selector in login_indicators:
                                try:
                                    if driver.find_elements(By.CSS_SELECTOR, selector):
                                        print(f"✅ Login detectat pentru {account_name}!")
                                        return True
                                except:
                                    pass
                        time.sleep(2)
                    
                    # Dacă după 10 secunde nu detectăm login, presupunem că e OK
                    print(f"⚠️ Nu am detectat login clar, dar continuăm...")
                    return True
                    
                except Exception as e:
                    print(f"❌ Eroare la click pe buton login: {e}")
                    # Salvează screenshot la eroare
                    try:
                        driver.save_screenshot(f"error_{account_name}_login.png")
                    except:
                        pass
                    return False
            else:
                print(f"❌ Nu am găsit butonul de login Steam pentru {account_name}")
                print("💡 Deschide manual site-ul în browser și loghează-te.")
                print("⏸️ Aștept 30 secunde să te loghezi...")
                time.sleep(30)
                return True  # Returnăm True pentru a continua
                    
        except Exception as e:
            print(f"❌ Eroare la login Steam pentru {account_name}: {e}")
            return False
    
    def open_free_cases(self, driver, account_name, available_cases):
        """Deschide casele gratuite disponibile pentru acest cont"""
        results = []
        
        for case_type in available_cases:
            try:
                print(f"\n📦 Deschid {case_type} pentru {account_name}...")
                
                # Navighează la secțiunea free cases
                driver.get("https://casehug.com/free")
                time.sleep(3)
                
                # Închide popup-uri
                self.close_popups(driver)
                time.sleep(1)
                
                # Scroll pentru a vedea casele
                driver.execute_script("window.scrollTo(0, 400);")
                time.sleep(1)
                
                # Salvează screenshot pentru debugging
                try:
                    driver.save_screenshot(f"debug_{account_name}_{case_type}.png")
                except:
                    pass
                
                # Găsește case-ul specific cu mai multe strategii
                case_button = None
                
                # Strategia 1: Caută după text în elemente clickabile
                try:
                    all_clickable = driver.find_elements(By.CSS_SELECTOR, "button, a, div[role='button'], [onclick]")
                    for elem in all_clickable:
                        if elem.is_displayed():
                            text = elem.text.lower()
                            if case_type.lower() in text or ('free' in text and case_type.lower() in elem.get_attribute('class').lower()):
                                case_button = elem
                                print(f"   ✓ Găsit case prin text: {text[:50]}")
                                break
                except:
                    pass
                
                # Strategia 2: Caută după clase CSS
                if not case_button:
                    case_selectors = [
                        f".case-{case_type.lower()}",
                        f"[data-case='{case_type.lower()}']",
                        f"[class*='{case_type.lower()}']",
                        f"button:contains('{case_type}')",
                        f".{case_type.lower()}-case",
                        f"#{case_type.lower()}-case"
                    ]
                    
                    for selector in case_selectors:
                        try:
                            elements = driver.find_elements(By.CSS_SELECTOR, selector.split(':')[0])
                            for elem in elements:
                                if elem.is_displayed() and elem.is_enabled():
                                    case_button = elem
                                    print(f"   ✓ Găsit case prin selector: {selector}")
                                    break
                            if case_button:
                                break
                        except:
                            continue
                
                if case_button:
                    try:
                        # Scroll la element
                        driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", case_button)
                        time.sleep(1)
                        
                        # Click
                        try:
                            case_button.click()
                        except:
                            driver.execute_script("arguments[0].click();", case_button)
                        
                        print(f"   ✓ Click pe case {case_type}")
                        time.sleep(5)
                        
                        # Așteaptă să apară skinul câștigat
                        skin_name = "Necunoscut"
                        price = "N/A"
                        
                        # Caută skinul cu mai multe strategii
                        skin_selectors = [
                            ".item-name", ".skin-name", ".reward-name",
                            ".item-title", ".skin-title", ".reward-title",
                            "[class*='item']", "[class*='skin']", "[class*='reward']",
                            ".name", ".title", "h3", "h4"
                        ]
                        
                        for selector in skin_selectors:
                            try:
                                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                for elem in elements:
                                    if elem.is_displayed():
                                        text = elem.text.strip()
                                        if text and len(text) > 3 and text not in ['Free', case_type]:
                                            skin_name = text
                                            print(f"   ✓ Skin găsit: {skin_name}")
                                            break
                                if skin_name != "Necunoscut":
                                    break
                            except:
                                continue
                        
                        # Caută prețul
                        price_selectors = [
                            ".item-price", ".skin-price", ".reward-price",
                            ".price", ".value", "[class*='price']", "[class*='value']"
                        ]
                        
                        for selector in price_selectors:
                            try:
                                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                                for elem in elements:
                                    if elem.is_displayed():
                                        text = elem.text.strip()
                                        if '$' in text or '€' in text or any(c.isdigit() for c in text):
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
                    print(f"❌ Nu am găsit case-ul {case_type}")
                    print(f"💡 Case-ul {case_type} nu este disponibil sau nu a fost găsit pe pagină")
                    
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
            # Login Steam (sau verifică dacă este deja logat)
            if not self.login_steam(driver, account_name):
                print(f"❌ Nu s-a putut loga cu {account_name}")
                return None
            
            # Deschide casele gratuite
            results = self.open_free_cases(driver, account_name, available_cases)
            
            # Obține balanța
            balance = self.get_balance(driver)
            
            return {
                "account": account_name,
                "results": results,
                "balance": balance
            }
            
        except Exception as e:
            print(f"❌ Eroare la procesare {account_name}: {e}")
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
