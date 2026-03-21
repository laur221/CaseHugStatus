"""Launch account-specific visible CaseHug browsers for manual operations."""

from __future__ import annotations

import logging
import os
import threading
from typing import Dict, Tuple

from selenium import webdriver
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.chrome.service import Service as ChromeService

logger = logging.getLogger(__name__)


class AccountBrowserLauncher:
    """Manage visible Chrome instances bound to an account browser profile."""

    def __init__(self):
        self._drivers: Dict[str, webdriver.Chrome] = {}
        self._lock = threading.Lock()

    @staticmethod
    def _key(account_id: int | str) -> str:
        return str(account_id)

    @staticmethod
    def _build_options(profile_path: str) -> ChromeOptions:
        options = ChromeOptions()
        options.add_argument(f"--user-data-dir={profile_path}")
        options.add_argument("--start-maximized")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-component-update")
        options.add_argument("--disable-sync")
        options.add_argument("--log-level=3")
        options.add_experimental_option("excludeSwitches", ["enable-logging"])
        return options

    def open_casehug(
        self,
        account_id: int | str,
        profile_path: str,
        *,
        url: str = "https://casehug.com/free-cases",
    ) -> Tuple[bool, str]:
        key = self._key(account_id)

        with self._lock:
            existing = self._drivers.get(key)

        if existing is not None:
            try:
                existing.get(url)
                return True, "Browser already open for this account. Reused existing window."
            except Exception:
                self.close_account_browser(account_id)

        normalized_profile = str(profile_path or "").strip()
        if not normalized_profile:
            return False, "Missing browser profile path for this account."

        os.makedirs(normalized_profile, exist_ok=True)

        try:
            driver = webdriver.Chrome(
                options=self._build_options(normalized_profile),
                service=ChromeService(log_output=os.devnull),
            )
            driver.get(url)
        except Exception as exc:
            logger.error("Could not launch manual CaseHug browser: %s", exc, exc_info=True)
            return False, f"Could not launch browser: {exc}"

        with self._lock:
            self._drivers[key] = driver

        return True, "Browser opened. You can now sell skins or open paid cases manually."

    def close_account_browser(self, account_id: int | str):
        key = self._key(account_id)
        with self._lock:
            driver = self._drivers.pop(key, None)
        if not driver:
            return
        try:
            driver.quit()
        except Exception:
            pass

    def close_all(self):
        with self._lock:
            keys = list(self._drivers.keys())
        for key in keys:
            self.close_account_browser(key)


casehug_browser_launcher = AccountBrowserLauncher()
