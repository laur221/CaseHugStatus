"""Interactive Steam login launcher with persistent per-account profiles."""

from __future__ import annotations

import base64
import logging
import os
import threading
import time
import urllib.parse
from typing import Dict, Optional, Tuple

from selenium.common.exceptions import TimeoutException, WebDriverException
from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait

logger = logging.getLogger(__name__)


class SteamLoginLauncher:
    """Manage browser instances used for interactive Steam login."""

    def __init__(self):
        self._drivers: Dict[str, webdriver.Chrome] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(ref: str | int) -> str:
        return str(ref)

    @staticmethod
    def _create_driver(options: ChromeOptions) -> webdriver.Chrome:
        service = ChromeService(log_output=os.devnull)
        return webdriver.Chrome(options=options, service=service)

    @staticmethod
    def _apply_common_chrome_options(options: ChromeOptions):
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--log-level=3")
        options.add_argument("--disable-logging")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-sync")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])

    def start(
        self,
        account_id: str | int,
        profile_path: str,
        steam_username: str = "",
        steam_password: str = "",
        prefer_qr: bool = False,
        run_in_background: bool = False,
    ) -> Tuple[bool, str]:
        if run_in_background and prefer_qr:
            return False, "QR login requires a visible browser window."

        key = self._key(account_id)
        with self._lock:
            existing = self._drivers.get(key)
            if existing:
                return True, "A login browser is already open for this account."

            try:
                options = ChromeOptions()
                options.add_argument(f"--user-data-dir={profile_path}")
                self._apply_common_chrome_options(options)
                if run_in_background:
                    options.add_argument("--headless=new")
                    options.add_argument("--window-size=1920,1080")
                else:
                    options.add_argument("--start-maximized")
                driver = self._create_driver(options)
                self._drivers[key] = driver
            except Exception as exc:
                logger.error("Could not launch Steam login browser: %s", exc, exc_info=True)
                return False, f"Could not launch browser: {exc}"

        try:
            self._open_casehug_steam_login(driver)
            steam_window = self._switch_to_steam_window(driver, timeout=20)
            if steam_window:
                driver.switch_to.window(steam_window)
            if steam_username and steam_password and not prefer_qr:
                self._autofill_steam_credentials(driver, steam_username, steam_password)
                if run_in_background:
                    return True, (
                        "Background login started and credentials autofilled. "
                        "Approve Steam Guard on phone if prompted, then press 'Session Completed'."
                    )
                return True, (
                    "Browser launched and credentials autofilled. "
                    "Approve Steam Guard on phone if requested, then press 'Session Completed'."
                )

            if prefer_qr:
                self._prepare_qr_login_view(driver)
                return True, (
                    "Browser launched in Steam login view. "
                    "Scan the QR code in the browser and then press 'Session Completed'."
                )

            return True, (
                "Browser launched. Complete Steam login manually and then press 'Session Completed'."
            )
        except Exception as exc:
            logger.warning("Login browser started but setup failed: %s", exc, exc_info=True)
            return True, (
                "Browser launched, but automatic setup did not fully complete. "
                "You can continue manually in the opened browser."
            )

    def start_steam_headless(self, session_ref: str | int, profile_path: str = "") -> Tuple[bool, str]:
        key = self._key(session_ref)
        with self._lock:
            if key in self._drivers:
                return True, "Headless Steam session is already running."
            try:
                logger.info(
                    "Launching headless Steam browser: session_ref=%s profile=%s",
                    key,
                    profile_path or "<none>",
                )
                options = ChromeOptions()
                if profile_path:
                    options.add_argument(f"--user-data-dir={profile_path}")
                self._apply_common_chrome_options(options)
                options.add_argument("--headless=new")
                options.add_argument("--window-size=1920,1080")
                driver = self._create_driver(options)
                self._drivers[key] = driver
            except Exception as exc:
                logger.error("Could not launch headless Steam browser: %s", exc, exc_info=True)
                return False, f"Could not launch browser: {exc}"

        try:
            driver.get("https://steamcommunity.com/login/home")
            logger.info("Steam login page opened in headless session: session_ref=%s", key)
            return True, "Headless Steam browser started."
        except Exception as exc:
            return False, f"Could not open Steam login page: {exc}"

    def get_qr_image_data(
        self,
        session_ref: str | int,
        timeout_seconds: int = 30,
    ) -> Tuple[bool, str, str]:
        driver = self._drivers.get(self._key(session_ref))
        if not driver:
            return False, "No active Steam session.", ""

        try:
            url = (driver.current_url or "").lower()
            if "steamcommunity.com/login/home" not in url:
                driver.get("https://steamcommunity.com/login/home")
                time.sleep(1.2)

            selectors = [
                "div._35Q-UW9L8wv2fkImoWScgQ img._5S5WqZhvbmRD1cHQT8P-l[src^='blob:']",
                "div._35Q-UW9L8wv2fkImoWScgQ img[src^='blob:']",
                "div._35Q-UW9L8wv2fkImoWScgQ img",
                "div[class*='qr'] img[src^='blob:']",
                "img[src*='qrcode']",
                "img[src*='qr']",
            ]
            deadline = time.time() + max(5, int(timeout_seconds))
            last_error = ""
            max_loading_bytes = 10000

            while time.time() < deadline:
                try:
                    marked = driver.execute_script(
                        """
                        const marker = "data-casehug-qr-target";
                        document.querySelectorAll("[" + marker + "]").forEach((el) => el.removeAttribute(marker));

                        const blocks = Array.from(document.querySelectorAll("div"));
                        const panel = blocks.find((el) => {
                          const txt = (el.textContent || "").toLowerCase();
                          return txt.includes("or sign in with qr") && txt.includes("steam mobile app");
                        });
                        if (!panel) return false;

                        const exact =
                          panel.querySelector("div._35Q-UW9L8wv2fkImoWScgQ img._5S5WqZhvbmRD1cHQT8P-l[src^='blob:']") ||
                          panel.querySelector("div._35Q-UW9L8wv2fkImoWScgQ img[src^='blob:']") ||
                          panel.querySelector("div._35Q-UW9L8wv2fkImoWScgQ img") ||
                          panel.querySelector("img[src^='blob:']") ||
                          panel.querySelector("img");
                        if (!exact) return false;

                        const r = exact.getBoundingClientRect();
                        if (r.width < 120 || r.height < 120 || r.width > 260 || r.height > 260) {
                          return false;
                        }

                        exact.setAttribute(marker, "1");
                        return true;
                        """
                    )
                    if marked:
                        qr_target = driver.find_element(By.CSS_SELECTOR, "[data-casehug-qr-target='1']")
                        image_bytes = qr_target.screenshot_as_png
                        if image_bytes:
                            if len(image_bytes) > max_loading_bytes:
                                # Steam often shows a temporary blurred QR with spinner.
                                time.sleep(0.5)
                                continue
                            encoded = base64.b64encode(image_bytes).decode("ascii")
                            logger.info(
                                "QR image data captured (context panel): session_ref=%s bytes=%s",
                                self._key(session_ref),
                                len(image_bytes),
                            )
                            return True, "QR captured.", encoded
                except Exception as exc:
                    last_error = str(exc)

                try:
                    data_url = driver.execute_script(
                        """
                        const img =
                          document.querySelector("img[src*='qrcode']") ||
                          document.querySelector("img[src*='qr']") ||
                          document.querySelector("div[class*='qr'] img");
                        if (img && img.src && img.src.startsWith("data:image")) {
                          return img.src;
                        }
                        return "";
                        """
                    ) or ""

                    if isinstance(data_url, str) and data_url.startswith("data:image"):
                        encoded = data_url.split(",", 1)[1] if "," in data_url else ""
                        if encoded:
                            logger.info(
                                "QR image data captured (data-url): session_ref=%s bytes_b64=%s",
                                self._key(session_ref),
                                len(encoded),
                            )
                            return True, "QR captured.", encoded
                except Exception as exc:
                    last_error = str(exc)

                for selector in selectors:
                    try:
                        elements = driver.find_elements(By.CSS_SELECTOR, selector)
                        if not elements:
                            continue
                        image_bytes = elements[0].screenshot_as_png
                        if not image_bytes:
                            continue
                        if len(image_bytes) > max_loading_bytes:
                            time.sleep(0.4)
                            continue
                        encoded = base64.b64encode(image_bytes).decode("ascii")
                        logger.info(
                            "QR image data captured (element): session_ref=%s selector=%s bytes=%s",
                            self._key(session_ref),
                            selector,
                            len(image_bytes),
                        )
                        return True, "QR captured.", encoded
                    except Exception as exc:
                        last_error = str(exc)
                        continue

                time.sleep(0.6)

            if last_error:
                return False, f"QR not available yet: {last_error}", ""
            return False, "QR not available yet on Steam page. Refresh and try again.", ""
        except Exception as exc:
            return False, f"Could not capture QR from Steam page: {exc}", ""

    def submit_credentials(
        self,
        session_ref: str | int,
        steam_username: str,
        steam_password: str,
    ) -> Tuple[bool, str]:
        driver = self._drivers.get(self._key(session_ref))
        if not driver:
            return False, "No active Steam session."

        try:
            current = (driver.current_url or "").lower()
            if "steamcommunity.com/login/home" not in current:
                driver.get("https://steamcommunity.com/login/home")
            self._autofill_steam_credentials(driver, steam_username, steam_password)
            logger.info(
                "Credentials submitted to Steam page: session_ref=%s username=%s",
                self._key(session_ref),
                (steam_username or "")[:3] + "***",
            )
            return True, "Credentials submitted. Approve Steam Guard on your phone if prompted."
        except Exception as exc:
            return False, f"Could not submit credentials: {exc}"

    def is_steam_authenticated(self, session_ref: str | int) -> Tuple[bool, str, dict]:
        driver = self._drivers.get(self._key(session_ref))
        if not driver:
            return False, "No active Steam session.", {}

        try:
            # Do not navigate away from login/home while waiting for QR approval.
            # Steam QR challenge is page/session-bound; forced navigation can break it.
            cookies = driver.get_cookies()
            parsed = {item["name"]: item.get("value", "") for item in cookies if item.get("name")}
            if "steamLoginSecure" in parsed:
                logger.info("Steam session authenticated: session_ref=%s", self._key(session_ref))
                return True, "Steam login is active.", parsed
            return False, "Steam login not confirmed yet.", parsed
        except Exception as exc:
            return False, f"Could not validate Steam session: {exc}", {}

    def get_steam_profile(self, session_ref: str | int) -> Tuple[bool, str, dict]:
        """Extract Steam profile identity from an authenticated browser session."""
        driver = self._drivers.get(self._key(session_ref))
        if not driver:
            return False, "No active Steam session.", {}

        try:
            driver.get("https://steamcommunity.com/my")
            time.sleep(1)

            current = (driver.current_url or "").lower()
            if "login" in current:
                return False, "Steam session is not authenticated yet.", {}

            cookies = driver.get_cookies()
            parsed_cookies = {
                item["name"]: item.get("value", "")
                for item in cookies
                if item.get("name")
            }

            steam_id = ""
            steam_cookie = parsed_cookies.get("steamLoginSecure", "")
            if steam_cookie:
                decoded = urllib.parse.unquote(steam_cookie)
                steam_id = decoded.split("||", 1)[0].strip()

            nickname = ""
            nickname_selectors = [
                (By.CSS_SELECTOR, "#account_pulldown"),
                (By.CSS_SELECTOR, ".persona_name_text_content"),
                (By.CSS_SELECTOR, ".actual_persona_name"),
            ]
            for by, selector in nickname_selectors:
                try:
                    text = driver.find_element(by, selector).text.strip()
                    if text:
                        nickname = text
                        break
                except Exception:
                    continue

            if not nickname:
                try:
                    nickname = (
                        driver.execute_script(
                            "return (window.g_AccountName || window.g_steamID || '').toString();"
                        )
                        or ""
                    ).strip()
                except Exception:
                    nickname = ""

            if not nickname and steam_id:
                nickname = f"steam_{steam_id}"

            if not nickname:
                return False, "Could not read Steam profile name from session.", {}

            logger.info(
                "Steam profile extracted: session_ref=%s steam_id=%s nickname=%s",
                self._key(session_ref),
                steam_id,
                nickname,
            )
            return True, "Steam profile detected.", {
                "steam_id": steam_id,
                "steam_nickname": nickname,
                "steam_username": nickname,
                "cookies": parsed_cookies,
            }
        except Exception as exc:
            return False, f"Could not extract Steam profile: {exc}", {}

    def complete(self, account_id: str | int, close_browser: bool = False) -> Tuple[bool, str, dict]:
        key = self._key(account_id)
        driver = self._drivers.get(key)
        if not driver:
            return False, "No active login browser found for this account.", {}

        cookies = self._extract_casehug_cookies(driver)
        if not cookies:
            msg = (
                "Could not detect CaseHug cookies yet. "
                "Make sure login finished in browser, then try again."
            )
            return False, msg, {}

        if close_browser:
            self.close(account_id)

        return True, "Login session detected and saved.", cookies

    def close(self, account_id: str | int):
        key = self._key(account_id)
        with self._lock:
            driver = self._drivers.pop(key, None)
        if not driver:
            return
        try:
            driver.quit()
        except Exception as exc:
            logger.debug("Error while closing login browser for account %s: %s", account_id, exc)

    def _open_casehug_steam_login(self, driver: webdriver.Chrome):
        driver.get("https://casehug.com/login")
        wait = WebDriverWait(driver, 20)

        steam_button_selectors = [
            (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'steam')]"),
            (By.XPATH, "//a[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'steam')]"),
            (By.CSS_SELECTOR, "a[href*='steam'], button[data-provider*='steam']"),
        ]

        for by, selector in steam_button_selectors:
            try:
                btn = wait.until(EC.element_to_be_clickable((by, selector)))
                btn.click()
                return
            except TimeoutException:
                continue
            except Exception:
                continue

        # Fallback: let user continue manually if auto-click was not possible.
        logger.info("Could not auto-click Steam button on CaseHug login page.")

    def _switch_to_steam_window(self, driver: webdriver.Chrome, timeout: int = 20) -> Optional[str]:
        deadline = time.time() + timeout
        while time.time() < deadline:
            for handle in driver.window_handles:
                try:
                    driver.switch_to.window(handle)
                    url = (driver.current_url or "").lower()
                    if "steamcommunity.com" in url or "steampowered.com" in url:
                        return handle
                except WebDriverException:
                    continue
            time.sleep(0.5)
        return None

    def _autofill_steam_credentials(self, driver: webdriver.Chrome, username: str, password: str):
        wait = WebDriverWait(driver, 25)
        username_selectors = [
            (By.CSS_SELECTOR, "input#input_username"),
            (By.CSS_SELECTOR, "input[name='username']"),
            (By.CSS_SELECTOR, "input[type='text']"),
        ]
        password_selectors = [
            (By.CSS_SELECTOR, "input#input_password"),
            (By.CSS_SELECTOR, "input[name='password']"),
            (By.CSS_SELECTOR, "input[type='password']"),
        ]

        user_input = self._find_first_available(wait, username_selectors)
        pwd_input = self._find_first_available(wait, password_selectors)
        if not user_input or not pwd_input:
            raise RuntimeError("Could not find Steam username/password fields.")

        user_input.clear()
        user_input.send_keys(username)
        pwd_input.clear()
        pwd_input.send_keys(password)

        submit_selectors = [
            (By.CSS_SELECTOR, "button[type='submit']"),
            (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'sign in')]"),
            (By.XPATH, "//button[contains(translate(., 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'login')]"),
        ]
        submit_btn = self._find_first_available(wait, submit_selectors, clickable=True)
        if submit_btn:
            submit_btn.click()

    def _prepare_qr_login_view(self, driver: webdriver.Chrome):
        try:
            current = (driver.current_url or "").lower()
            if "steamcommunity.com" not in current and "steampowered.com" not in current:
                driver.get("https://steamcommunity.com/login/home/")
        except Exception:
            pass

    def _find_first_available(self, wait: WebDriverWait, selectors, clickable: bool = False):
        for by, selector in selectors:
            try:
                if clickable:
                    return wait.until(EC.element_to_be_clickable((by, selector)))
                return wait.until(EC.presence_of_element_located((by, selector)))
            except TimeoutException:
                continue
            except Exception:
                continue
        return None

    def _extract_casehug_cookies(self, driver: webdriver.Chrome) -> dict:
        """Collect casehug cookies from any open tab."""
        for handle in driver.window_handles:
            try:
                driver.switch_to.window(handle)
                url = (driver.current_url or "").lower()
                if "casehug.com" not in url:
                    continue
                cookies = driver.get_cookies()
                parsed = {
                    item["name"]: item.get("value", "")
                    for item in cookies
                    if item.get("name")
                }
                if parsed:
                    return parsed
            except Exception:
                continue
        return {}


steam_login_launcher = SteamLoginLauncher()
