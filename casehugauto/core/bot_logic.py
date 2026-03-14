"""
This module contains the core web automation logic using undetected-chromedriver
to bypass anti-bot measures like Cloudflare.
"""
import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from sqlalchemy.orm import Session
from ..database.crud import AccountCRUD, BotStatusCRUD, SkinCRUD
from ..models.models import Account
from .steam_client import steam_client
import time
import random
import logging
import threading
from typing import Callable

logger = logging.getLogger(__name__)

class AutomationLogic:
    def __init__(self, db_session: Session, account_id: int, stop_event: threading.Event, status_callback: Callable):
        self.db_session = db_session
        self.account_id = account_id
        self.account = AccountCRUD.get_by_id(self.db_session, self.account_id)
        self.stop_event = stop_event
        self.driver = None
        self._emit_status = status_callback

    def run(self):
        """Main execution method for the bot."""
        if not self.account:
            self._emit_status(self.account_id, f"Account with ID {self.account_id} not found.", "error")
            return

        try:
            self._emit_status(self.account_id, "Initializing browser...", "info")
            options = uc.ChromeOptions()
            # options.add_argument('--headless') # Can be enabled for production
            options.add_argument('--no-sandbox')
            options.add_argument('--disable-dev-shm-usage')
            self.driver = uc.Chrome(options=options, version_main=108) # Pin version for stability

            self._login()
            self._run_case_opening_loop()

        except Exception as e:
            self._emit_status(self.account_id, f"A critical error occurred: {e}", "error")
            logger.error(f"An error occurred in bot for {self.account.username}: {e}", exc_info=True)
        finally:
            self.stop()

    def _login(self):
        if not self.driver or self.stop_event.is_set():
            return

        self._emit_status(self.account_id, "Initializing Steam authentication...", "info")
        
        # Obține cookies Steam din cont
        if self.account.cookies:
            self._emit_status(self.account_id, "Using saved Steam cookies for login...", "info")
            try:
                # Convertim cookies din JSON
                cookies = self.account.cookies if isinstance(self.account.cookies, dict) else {}
                
                # Login la casehug cu Steam cookies
                casehug_cookies = steam_client.login_to_casehug_with_steam(cookies)
                
                if casehug_cookies:
                    # Adaugă cookies în browser
                    self.driver.get("https://www.casehug.com")
                    for cookie_name, cookie_value in casehug_cookies.items():
                        try:
                            self.driver.add_cookie({
                                "name": cookie_name,
                                "value": cookie_value,
                                "domain": ".casehug.com"
                            })
                        except Exception as e:
                            logger.debug(f"Could not set cookie {cookie_name}: {e}")
                    
                    # Refresh pagina ca să se aplice cookies
                    self.driver.refresh()
                    time.sleep(2)
                    
                    # Verifică dacă login a reușit
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/account')]"))
                    )
                    
                    self._emit_status(self.account_id, f"✓ Steam login successful for {self.account.steam_nickname}", "success")
                    return
            except Exception as e:
                logger.warning(f"Steam cookie login failed: {e}, attempting manual login...")
        
        # Fallback la manual login
        self._emit_status(self.account_id, "Navigating to login page...", "info")
        self.driver.get("https://www.casehug.com/login")

        try:
            WebDriverWait(self.driver, 30).until(
                EC.presence_of_element_located((By.NAME, "username"))
            )

            self._emit_status(self.account_id, "Entering credentials...", "info")
            username_field = self.driver.find_element(By.NAME, "username")
            password_field = self.driver.find_element(By.NAME, "password")

            username_field.send_keys(self.account.steam_username)
            time.sleep(random.uniform(0.5, 1.2))
            password_field.send_keys(self.account.get_password())
            time.sleep(random.uniform(0.5, 1.2))

            self._emit_status(self.account_id, "Submitting login form...", "info")
            login_button = self.driver.find_element(By.XPATH, "//button[@type='submit']")
            login_button.click()

            WebDriverWait(self.driver, 45).until(
                EC.presence_of_element_located((By.XPATH, "//a[contains(@href, '/account')]"))
            )
            self._emit_status(self.account_id, "✓ Login successful.", "success")
        except Exception as e:
            logger.error(f"Login failed for {self.account.steam_nickname}: {e}")
            self._emit_status(self.account_id, f"✗ Login failed: {e}", "error")
            raise

    def _run_case_opening_loop(self):
        if not self.driver:
            return

        # IMPORTANT: You need to find the correct URL for a case page
        self.driver.get("https://www.casehug.com/case/milspec") # EXAMPLE URL

        while not self.stop_event.is_set():
            try:
                self._emit_status(self.account_id, "Attempting to open a case...", "info")

                # 1. Find and click the open button
                open_button = WebDriverWait(self.driver, 20).until(
                    EC.element_to_be_clickable((By.XPATH, "//button[contains(text(), 'Open case')]"))
                )
                open_button.click()

                # 2. Wait for the result
                # This needs to be adapted to the actual site structure
                won_item_element = WebDriverWait(self.driver, 60).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, ".case-opening-item-name")) # Example selector
                )
                item_name = won_item_element.text

                item_value_element = self.driver.find_element(By.CSS_SELECTOR, ".case-opening-item-price") # Example
                item_value = float(item_value_element.text.replace('$', ''))

                self._emit_status(self.account_id, f"Won item: {item_name} (${item_value})", "success")

                # 3. Save to DB
                SkinCRUD.create(self.db_session, name=item_name, value=item_value, image_url="", account_id=self.account_id)
                BotStatusCRUD.increment_cases_opened(self.db_session, self.account_id)
                BotStatusCRUD.add_to_total_value(self.db_session, self.account_id, item_value)

                # Wait before next open
                sleep_time = random.uniform(10, 25)
                self._emit_status(self.account_id, f"Waiting for {sleep_time:.1f}s...", "info")
                self.stop_event.wait(sleep_time)

            except Exception as e:
                logger.error(f"Error in case opening loop for {self.account.username}: {e}")
                self._emit_status(self.account_id, f"Error opening case: {e}", "error")
                self.stop_event.wait(60) # Longer pause on error

    def stop(self):
        if self.driver:
            try:
                self.driver.quit()
            except Exception as e:
                logger.error(f"Error while quitting driver for {self.account.username}: {e}")
        self.driver = None
        self._emit_status(self.account_id, "Browser closed.", "info")