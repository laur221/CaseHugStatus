"""
bot_logic.py - Core automation using nodriver (replaces undetected_chromedriver)
Runs without GUI: window positioned off-screen (-32000, -32000)
"""
import asyncio
import base64
from datetime import datetime
import html
import json
import logging
import os
from pathlib import Path
import re
import threading
import time
from typing import Any, Callable, Mapping

import nodriver as uc
import requests
import psutil
from sqlalchemy.orm import Session

from ..database.crud import AccountCRUD, BotStatusCRUD, SkinCRUD
from .rarity import rarity_from_color
from .profile_store import ensure_profile_path as ensure_managed_profile_path

logger = logging.getLogger(__name__)
logging.getLogger("uc.connection").setLevel(logging.WARNING)
_NODRIVER_WS_PATCH_APPLIED = False

_JS_EXTRACT_NEW_DROPS = r"""
(() => {
  const textOf = (el) => (el && el.textContent ? el.textContent.trim() : "");
  const toHex = (color) => {
    if (!color) return "";
    const c = String(color).trim();
    if (c.startsWith("#")) return c.toUpperCase();
    const m = c.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (!m) return "";
    const to2 = (n) => Math.max(0, Math.min(255, parseInt(n, 10))).toString(16).padStart(2, "0");
    return ("#" + to2(m[1]) + to2(m[2]) + to2(m[3])).toUpperCase();
  };

  const cards = Array.from(document.querySelectorAll('[data-testid="skin-card"]'));
  const out = [];

  for (const card of cards) {
    const label = textOf(card.querySelector('[data-testid="your-drop-card-label"]')).toLowerCase();
    if (label !== "new") continue;

    const name = textOf(card.querySelector('[data-testid="your-drop-name"]'));
    const categoryEl = card.querySelector('[data-testid="your-drop-category"]');
    const category = textOf(categoryEl);
    const price = textOf(card.querySelector('[data-testid="your-drop-price"]'));

    const caseSourceEl = card.querySelector('[data-testid="your-drops-hover-date"]');
    const caseSource = textOf(caseSourceEl);
    const obtainedWrap = card.querySelector('[data-testid="your-drops-hover-is-drawn"]');
    const obtainedTime = obtainedWrap && obtainedWrap.children && obtainedWrap.children.length > 1
      ? textOf(obtainedWrap.children[1])
      : "";
    const obtainedDate = caseSourceEl && caseSourceEl.nextElementSibling
      ? textOf(caseSourceEl.nextElementSibling)
      : "";

    const condition = textOf(card.querySelector('[data-testid="your-drop-card-condition"]'));
    const image = card.querySelector('[data-testid="your-drop-skin-image"]');

    const upgraderHref = card.querySelector('[data-testid="upgrader-button"]')?.getAttribute("href") || "";
    const exchangeHref = card.querySelector('[data-testid="exchange-button"]')?.getAttribute("href") || "";
    const hrefForItem = upgraderHref || exchangeHref || "";
    const itemMatch = hrefForItem.match(/item=(\d+)/i);

    const cssColor = categoryEl ? toHex(getComputedStyle(categoryEl).color) : "";
    const gradStop = card.querySelector('linearGradient stop[offset="40%"]');
    const gradientColor = gradStop ? toHex(gradStop.getAttribute("stop-color") || "") : "";

    if (!name || !category || !price) continue;

    out.push({
      case: (caseSource || "").toLowerCase() || "unknown",
      skin: `${name} | ${category}`.trim(),
      price: price,
      condition: (condition || "").toUpperCase() || null,
      skin_image_url: image ? (image.currentSrc || image.src || "") : "",
      rarity_color: cssColor || gradientColor || "",
      obtained_time: obtainedTime || "",
      obtained_date: obtainedDate || "",
      item_id: itemMatch ? itemMatch[1] : "",
    });
  }

  return out;
})()
"""


_RARITY_TO_ICON = {
    "Consumer Grade (White)": "⚪",
    "Industrial Grade (Light Blue)": "🔵",
    "Mil-Spec (Blue)": "🔷",
    "Restricted (Purple)": "🟣",
    "Classified (Pink)": "🌸",
    "Covert (Red)": "🔴",
    "Contraband (Orange)": "🟠",
    "Unknown": "⚪",
}

_CASEHUG_FREE_CASE_URLS = (
    "https://casehug.com/free-cases",
)

_SESSION_COOKIE_DOMAINS = (
    ".casehug.com",
    "casehug.com",
    ".steamcommunity.com",
    "steamcommunity.com",
    ".steampowered.com",
    "steampowered.com",
)


def _rarity_icon(rarity_label: str | None) -> str:
    if not rarity_label:
        return "⚪"
    return _RARITY_TO_ICON.get(str(rarity_label).strip(), "⚪")


def _hide_windows_for_pid(pid: int) -> int:
    """
    Hide all top-level windows that belong to PID (Windows only).
    Returns number of hidden windows.
    """
    if os.name != "nt" or not pid:
        return 0

    try:
        import ctypes
        from ctypes import wintypes
    except Exception:
        return 0

    user32 = ctypes.windll.user32
    SW_HIDE = 0
    hidden_hwnds = []

    enum_proc_type = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)

    @enum_proc_type
    def enum_proc(hwnd, _lparam):
        try:
            if not user32.IsWindowVisible(hwnd):
                return True
            proc_id = wintypes.DWORD(0)
            user32.GetWindowThreadProcessId(hwnd, ctypes.byref(proc_id))
            if int(proc_id.value) == int(pid):
                hidden_hwnds.append(hwnd)
        except Exception:
            pass
        return True

    try:
        user32.EnumWindows(enum_proc, 0)
    except Exception:
        return 0

    hidden = 0
    for hwnd in hidden_hwnds:
        try:
            user32.ShowWindow(hwnd, SW_HIDE)
            hidden += 1
        except Exception:
            continue
    return hidden


def _sanitize_profile_name(value: str) -> str:
    """Convert account name to a filesystem-safe profile folder name."""
    safe = re.sub(r"[^A-Za-z0-9._-]+", "_", (value or "").strip())
    return safe.strip("._-") or f"account_{int(time.time())}"


def _cleanup_stale_profile_locks(profile_dir: str):
    """Remove stale Chromium singleton lock files left after hard crashes."""
    for filename in ("SingletonLock", "SingletonCookie", "SingletonSocket"):
        path = os.path.join(profile_dir, filename)
        if not os.path.exists(path):
            continue
        try:
            os.remove(path)
        except PermissionError:
            # Active Chrome process still owns this profile; keep going.
            continue
        except OSError:
            continue


def _kill_profile_chrome_processes(profile_dir: str):
    """Terminate orphan Chrome processes that still hold the same profile path."""
    normalized_profile = os.path.normpath(profile_dir).replace("\\", "/").lower()
    to_terminate = []

    for proc in psutil.process_iter(["name", "cmdline"]):
        try:
            name = (proc.info.get("name") or "").lower()
            if "chrome" not in name:
                continue

            cmdline = proc.info.get("cmdline") or []
            for arg in cmdline:
                if not isinstance(arg, str):
                    continue
                low = arg.lower()
                if not low.startswith("--user-data-dir="):
                    continue

                user_data_arg = arg.split("=", 1)[1].strip().strip('"')
                arg_profile = os.path.normpath(user_data_arg).replace("\\", "/").lower()
                if arg_profile == normalized_profile:
                    to_terminate.append(proc)
                    break
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    for proc in to_terminate:
        try:
            proc.terminate()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue

    if not to_terminate:
        return

    _, alive = psutil.wait_procs(to_terminate, timeout=2.5)
    for proc in alive:
        try:
            proc.kill()
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            continue


def _apply_nodriver_websocket_compat_patch():
    """
    nodriver 0.35 expects `websocket.closed`, but websockets>=16 removed it.
    Patch Connection.closed to support both APIs and prevent startup crash.
    """
    global _NODRIVER_WS_PATCH_APPLIED
    if _NODRIVER_WS_PATCH_APPLIED:
        return

    try:
        from websockets.asyncio.client import ClientConnection
    except Exception:
        ClientConnection = None

    if ClientConnection and not hasattr(ClientConnection, "closed"):
        def _ws_closed(self):
            state = getattr(self, "state", None)
            if state is None:
                return False
            state_name = str(getattr(state, "name", state)).upper()
            return state_name in {"CLOSED", "CLOSING"}

        type.__setattr__(ClientConnection, "closed", property(_ws_closed))

    try:
        from nodriver.core.connection import Connection
    except Exception:
        return

    def _closed_compat(self):
        ws = getattr(self, "websocket", None)
        if ws is None:
            return True

        try:
            return bool(getattr(ws, "closed"))
        except Exception:
            pass

        state = getattr(ws, "state", None)
        if state is None:
            return False

        state_name = str(getattr(state, "name", state)).upper()
        return state_name in {"CLOSED", "CLOSING"}

    # Connection uses a metaclass that blocks direct attribute assignment.
    type.__setattr__(Connection, "closed", property(_closed_compat))
    _NODRIVER_WS_PATCH_APPLIED = True
    logger.info("Applied nodriver websocket compatibility patch (websockets>=16).")


class AutomationLogic:
    def __init__(
        self,
        db_session: Session,
        account_id: int,
        stop_event: threading.Event,
        status_callback: Callable,
        runtime_config: Mapping[str, Any] | None = None,
    ):
        self.db_session = db_session
        self.account_id = account_id
        self.account = AccountCRUD.get_by_id(self.db_session, self.account_id)
        self.stop_event = stop_event
        self._emit_status = status_callback
        self.runtime_config = dict(runtime_config or {})
        self.browser = None
        self.page = None
        self.last_result_status = "unknown"
        self.last_opened_cases_count = 0

    # ------------------------------------------------------------------ #
    #  PUBLIC ENTRY POINT                                                  #
    # ------------------------------------------------------------------ #

    def run(self):
        """Called from bot_runner thread — bridges sync → async."""
        try:
            asyncio.run(self._run_async())
        except Exception as e:
            self._emit_status(self.account_id, f"Critical error: {e}", "error")
            logger.error(f"Critical error for account {self.account_id}: {e}", exc_info=True)
        finally:
            self._emit_status(self.account_id, "Browser closed.", "info")

    def _cfg_str(self, key: str, default: str = "") -> str:
        return str(self.runtime_config.get(key, default) or "").strip()

    def _cfg_bool(self, key: str, default: bool = False) -> bool:
        value = self.runtime_config.get(key, default)
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _cfg_int(self, key: str, default: int = 0) -> int:
        value = self.runtime_config.get(key, default)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float)):
            return int(value)
        try:
            return int(str(value).strip())
        except Exception:
            return default

    def _telegram_is_configured(self) -> bool:
        return bool(self._cfg_str("telegram_bot_token") and self._cfg_str("telegram_chat_id"))

    def _send_telegram_message(self, message: str) -> bool:
        token = self._cfg_str("telegram_bot_token")
        chat_id = self._cfg_str("telegram_chat_id")
        if not token or not chat_id or not message.strip():
            return False

        url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "HTML",
            "disable_web_page_preview": True,
        }
        try:
            response = requests.post(url, data=payload, timeout=15)
            if response.status_code != 200:
                logger.warning(
                    "Telegram send failed for account %s: status=%s body=%s",
                    self.account_id,
                    response.status_code,
                    response.text,
                )
                return False
            return True
        except Exception as exc:
            logger.warning("Telegram send exception for account %s: %s", self.account_id, exc)
            return False

    def _send_telegram_photo(self, image_path: str, caption: str = "") -> bool:
        token = self._cfg_str("telegram_bot_token")
        chat_id = self._cfg_str("telegram_chat_id")
        if not token or not chat_id:
            return False

        file_path = Path(str(image_path or "").strip())
        if not file_path.exists() or not file_path.is_file():
            return False

        url = f"https://api.telegram.org/bot{token}/sendPhoto"
        payload = {"chat_id": chat_id}
        safe_caption = str(caption or "").strip()
        if safe_caption:
            payload["caption"] = safe_caption[:1000]
            payload["parse_mode"] = "HTML"

        try:
            with file_path.open("rb") as image_file:
                response = requests.post(
                    url,
                    data=payload,
                    files={"photo": image_file},
                    timeout=25,
                )
            if response.status_code != 200:
                logger.warning(
                    "Telegram photo send failed for account %s: status=%s body=%s",
                    self.account_id,
                    response.status_code,
                    response.text,
                )
                return False
            return True
        except Exception as exc:
            logger.warning("Telegram photo send exception for account %s: %s", self.account_id, exc)
            return False


    def _format_telegram_report(self, skins: list[dict[str, Any]], opened_cases_count: int) -> str:
        now = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        account_name = (getattr(self.account, "account_name", "") or str(self.account_id)).strip()

        message = "🎰 <b>CaseHug Auto Report</b>\n"
        message += f"📅 {now}\n"
        message += "──────────────────────────\n"
        message += f"<b>Account:</b> {html.escape(account_name)}\n"
        message += f"<b>Cases opened:</b> {int(opened_cases_count or 0)}\n\n"

        if not skins:
            message += "❌ No new skins found.\n"
            return message

        total = 0.0
        for item in skins:
            case_name = str(item.get("case") or "unknown").upper()
            skin_name = str(item.get("skin") or "Unknown skin").strip()
            price_txt = str(item.get("price") or "$0.00").strip()
            rarity_label = str(item.get("rarity") or "Unknown").strip()
            icon = _rarity_icon(rarity_label)
            total += self._parse_price(price_txt)

            message += (
                f"{icon} {html.escape(case_name)}: "
                f"{html.escape(skin_name)} - {html.escape(price_txt)}\n"
            )

        message += f"\n💰 <b>Total:</b> ${total:.2f}"
        return message

    def _notify_telegram_results(self, skins: list[dict[str, Any]], opened_cases_count: int):
        if not self._cfg_bool("telegram_notify_on_skin", True):
            return
        if not self._telegram_is_configured():
            return

        message = self._format_telegram_report(skins, opened_cases_count)
        sent = self._send_telegram_message(message)
        if sent:
            self._emit_status(self.account_id, "Telegram report sent.", "info")


    def _notify_telegram_error(self, error_text: str, screenshot_path: str = "", page_url: str = ""):
        if not self._cfg_bool("telegram_notify_on_error", True):
            return
        if not self._telegram_is_configured():
            return

        account_name = (getattr(self.account, "account_name", "") or str(self.account_id)).strip()
        now_text = datetime.now().strftime("%d.%m.%Y %H:%M:%S")
        safe_error = html.escape(str(error_text or "Unknown error"))
        raw_url = str(page_url or "").strip()
        if len(raw_url) > 320:
            raw_url = f"{raw_url[:317]}..."
        safe_url = html.escape(raw_url)
        page_line = f"<b>Page:</b> {safe_url}\n" if safe_url else ""
        message = (
            "❌ <b>CaseHug Auto Error</b>\n"
            f"<b>Account:</b> {html.escape(account_name)}\n"
            f"<b>Time:</b> {now_text}\n"
            f"{page_line}\n"
            f"{safe_error}"
        )

        sent_photo = False
        if self._cfg_bool("telegram_attach_error_screenshot", False) and screenshot_path:
            photo_caption = (
                "❌ <b>CaseHug Auto Error</b>\n"
                f"<b>Account:</b> {html.escape(account_name)}\n"
                f"<b>Time:</b> {now_text}\n"
                f"{page_line}\n"
                f"{safe_error}"
            )
            sent_photo = self._send_telegram_photo(screenshot_path, caption=photo_caption)
            if sent_photo:
                self._emit_status(self.account_id, "Telegram error screenshot sent.", "info")

        if not sent_photo:
            self._send_telegram_message(message)

    # ------------------------------------------------------------------ #
    #  BROWSER SETUP                                                       #
    # ------------------------------------------------------------------ #

    async def _start_browser(self):
        """Launch nodriver browser without GUI (off-screen window)."""
        account_name = (self.account.account_name or "").strip()
        configured_profile = str(getattr(self.account, "browser_profile_path", "") or "").strip()
        profile_dir = configured_profile or ensure_managed_profile_path(account_name)
        profile_dir = str(Path(profile_dir).expanduser().resolve())
        os.makedirs(profile_dir, exist_ok=True)

        if configured_profile != profile_dir:
            try:
                self.account.browser_profile_path = profile_dir
                self.db_session.commit()
            except Exception:
                self.db_session.rollback()

        self._emit_status(self.account_id, "Launching browser (no GUI)...", "info")
        _apply_nodriver_websocket_compat_patch()

        browser_args = [
            "--window-position=-32000,-32000",  # off-screen = no visible window
            "--window-size=1920,1080",
            "--no-sandbox",
            "--disable-setuid-sandbox",
            "--disable-dev-shm-usage",
            "--disable-infobars",
            "--mute-audio",
            "--no-first-run",
            "--no-default-browser-check",
        ]

        attempts = 3
        last_error = "unknown startup error"
        for attempt in range(1, attempts + 1):
            try:
                _kill_profile_chrome_processes(profile_dir)
                _cleanup_stale_profile_locks(profile_dir)
                self.browser = await uc.start(
                    user_data_dir=profile_dir,
                    headless=False,  # headless=True gets detected by Cloudflare
                    sandbox=False,
                    browser_args=browser_args,
                )
                self.page = self.browser.main_tab
                # Chrome can still appear briefly; hide all windows of this browser PID.
                for _ in range(4):
                    self._hide_browser_windows()
                    await asyncio.sleep(0.15)
                await asyncio.sleep(2)
                self._emit_status(self.account_id, "Browser ready.", "info")
                return
            except Exception as exc:
                last_error = str(exc)
                self.browser = None
                self.page = None
                logger.warning(
                    "Browser startup failed for account %s (attempt %s/%s): %s",
                    self.account_id,
                    attempt,
                    attempts,
                    exc,
                    exc_info=True,
                )
                _kill_profile_chrome_processes(profile_dir)
                if attempt < attempts:
                    self._emit_status(
                        self.account_id,
                        f"Browser start retry {attempt}/{attempts - 1}...",
                        "warning",
                    )
                    await asyncio.sleep(1.2 * attempt)

        raise RuntimeError(f"Browser startup failed after {attempts} attempts: {last_error}")

    async def _stop_browser(self):
        if self.browser:
            try:
                self.browser.stop()
            except Exception as e:
                logger.debug(f"Error stopping browser: {e}")
            self.browser = None
            self.page = None

    def _hide_browser_windows(self):
        if not self.browser:
            return
        try:
            pid = int(getattr(self.browser, "_process_pid", 0) or 0)
        except Exception:
            pid = 0
        if not pid:
            return
        hidden_count = _hide_windows_for_pid(pid)
        if hidden_count:
            logger.debug("Hidden %s browser window(s) for account %s.", hidden_count, self.account_id)

    async def _capture_failure_artifacts(self, reason: str) -> dict:
        """Save temporary debug artifacts right before browser shutdown."""
        if not self.page:
            return {}

        try:
            debug_dir = Path("logs") / "bot_debug"
            debug_dir.mkdir(parents=True, exist_ok=True)

            account_label = _sanitize_profile_name(
                getattr(self.account, "account_name", "") or str(self.account_id)
            )
            stamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S_%f")
            prefix = f"{stamp}_{account_label}_{self.account_id}"

            meta_path = debug_dir / f"{prefix}.json"
            html_path = debug_dir / f"{prefix}.html"
            screenshot_path = debug_dir / f"{prefix}.png"

            current_url = ""
            try:
                current_url = await self._get_tab_url(self.page)
            except Exception:
                current_url = ""

            tabs = []
            try:
                for idx, tab in enumerate(list(getattr(self.browser, "tabs", []) or [])):
                    tabs.append(
                        {
                            "index": idx,
                            "url": await self._get_tab_url(tab),
                        }
                    )
            except Exception:
                tabs = []

            html_saved = False
            screenshot_saved = False
            screenshot_error = ""

            try:
                content = await self.page.get_content()
                html_path.write_text(content or "", encoding="utf-8")
                html_saved = True
            except Exception as exc:
                logger.warning("Could not save debug HTML for account %s: %s", self.account_id, exc)

            try:
                shot = await self.page.send(
                    uc.cdp.page.capture_screenshot(
                        format_="png",
                        from_surface=True,
                        capture_beyond_viewport=True,
                    )
                )
                b64_data = ""
                if isinstance(shot, str):
                    b64_data = shot
                elif isinstance(shot, dict):
                    b64_data = str(shot.get("data") or "")
                if b64_data:
                    screenshot_path.write_bytes(base64.b64decode(b64_data))
                    screenshot_saved = True
            except Exception as exc:
                screenshot_error = str(exc)

            meta = {
                "reason": reason,
                "account_id": self.account_id,
                "account_name": getattr(self.account, "account_name", ""),
                "timestamp_utc": datetime.utcnow().isoformat(),
                "url": current_url,
                "tabs": tabs,
                "html_saved": html_saved,
                "html_path": str(html_path.resolve()) if html_saved else "",
                "screenshot_saved": screenshot_saved,
                "screenshot_path": str(screenshot_path.resolve()) if screenshot_saved else "",
                "screenshot_error": screenshot_error,
            }
            meta_path.write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")

            logger.warning(
                "Saved bot debug artifacts for account %s: meta=%s html=%s screenshot=%s",
                self.account_id,
                meta_path,
                html_saved,
                screenshot_saved,
            )
            return meta
        except Exception as exc:
            logger.warning(
                "Could not save debug artifacts for account %s: %s",
                self.account_id,
                exc,
                exc_info=True,
            )
            return {}

    # ------------------------------------------------------------------ #
    #  MAIN ASYNC FLOW                                                     #
    # ------------------------------------------------------------------ #

    async def _run_async(self):
        if not self.account:
            self._emit_status(self.account_id, f"Account {self.account_id} not found.", "error")
            self.last_result_status = "error"
            return

        self.last_opened_cases_count = 0
        try:
            await self._start_browser()
            await self._login()
            if not await self._is_casehug_logged_in():
                # Guard against transient post-OpenID redirect states.
                self._emit_status(
                    self.account_id,
                    "Post-login session not confirmed yet, retrying verification...",
                    "warning",
                )
                if not await self._ensure_casehug_context_after_login(timeout_seconds=30):
                    raise RuntimeError("Steam login was not confirmed on CaseHug.")

            if self.stop_event.is_set():
                self.last_result_status = "stopped"
                return

            opened_cases_count = 0
            available = await self._check_available_cases()
            if not available:
                self._emit_status(self.account_id, "No cases available today.", "info")
            else:
                opened_cases_count = await self._open_cases(available)
            self.last_opened_cases_count = int(opened_cases_count or 0)

            # Extract only when this run actually opened at least one case.
            results = []
            if opened_cases_count > 0:
                results = await self._extract_new_skins()
                if len(results) > opened_cases_count:
                    # Profile can contain older "New" cards; keep the latest expected drops.
                    logger.info(
                        "Parsed more skins than opened cases. account=%s parsed=%s opened=%s",
                        self.account_id,
                        len(results),
                        opened_cases_count,
                    )
                    results = results[:opened_cases_count]
            else:
                self._emit_status(
                    self.account_id,
                    "No case opened in this run. Skipping drop extraction.",
                    "info",
                )

            total_value = 0.0
            saved_skins_count = 0
            saved_results: list[dict[str, Any]] = []
            seen_signatures = set()
            for r in results:
                try:
                    skin_name = (r.get("skin") or "").strip()
                    case_source = (r.get("case") or "").strip().lower() or None
                    skin_value = self._parse_price(r.get("price", ""))
                    item_id = str(r.get("item_id") or "").strip()
                    obtained_dt = r.get("obtained_date")
                    if not isinstance(obtained_dt, datetime):
                        obtained_dt = datetime.utcnow()

                    if item_id:
                        signature = (self.account_id, "item", item_id)
                    else:
                        signature = (
                            self.account_id,
                            skin_name.lower(),
                            case_source or "",
                            round(float(skin_value or 0.0), 4),
                            obtained_dt.strftime("%Y-%m-%d %H:%M:%S"),
                        )
                    if signature in seen_signatures:
                        logger.info(
                            "Skipping duplicate skin in same extraction cycle: account=%s skin=%s case=%s price=%.4f",
                            self.account_id,
                            skin_name,
                            case_source,
                            skin_value,
                        )
                        continue
                    seen_signatures.add(signature)

                    rarity_label = str(r.get("rarity") or "").strip() or "Unknown"

                    _, created_now = SkinCRUD.upsert_imported(
                        self.db_session,
                        account_id=self.account_id,
                        skin_name=skin_name,
                        external_item_id=item_id or None,
                        estimated_price=skin_value,
                        case_source=case_source,
                        rarity=rarity_label,
                        condition=r.get("condition"),
                        skin_image_url=r.get("skin_image_url"),
                        obtained_date=obtained_dt,
                        is_new=True,
                    )
                    if created_now:
                        total_value += skin_value
                        saved_skins_count += 1
                        saved_results.append(dict(r))
                except Exception as e:
                    logger.warning(f"Could not save skin to DB: {e}")

            try:
                BotStatusCRUD.record_execution(
                    self.db_session,
                    self.account_id,
                    cases_opened=opened_cases_count,
                    skins_obtained=saved_skins_count,
                    total_value=total_value,
                )
            except Exception as exc:
                logger.warning("Could not update bot execution stats: %s", exc)

            try:
                if opened_cases_count > 0:
                    self._notify_telegram_results(saved_results, opened_cases_count)
            except Exception as exc:
                logger.warning("Could not send Telegram report: %s", exc)

            self._emit_status(
                self.account_id,
                f"Done. {saved_skins_count} new skin(s) saved.",
                "success",
            )
            self.last_result_status = "completed"

        except Exception as e:
            debug_meta = await self._capture_failure_artifacts(str(e))
            debug_path = debug_meta.get("screenshot_path") or debug_meta.get("html_path") or ""
            if debug_path:
                self._emit_status(
                    self.account_id,
                    f"Debug snapshot saved: {debug_path}",
                    "warning",
                )
            self._emit_status(self.account_id, f"Error: {e}", "error")
            try:
                self._notify_telegram_error(
                    str(e),
                    screenshot_path=str(debug_meta.get("screenshot_path") or ""),
                    page_url=str(debug_meta.get("url") or ""),
                )
            except Exception:
                pass
            logger.error(f"Error in bot for account {self.account_id}: {e}", exc_info=True)
            self.last_result_status = "error"
        finally:
            await self._stop_browser()

    # ------------------------------------------------------------------ #
    #  LOGIN                                                               #
    # ------------------------------------------------------------------ #

    async def _login(self):
        """Navigate to casehug and verify Steam login."""
        self._emit_status(self.account_id, "Checking Steam login...", "info")
        self._hide_browser_windows()

        await self.page.get("https://casehug.com/free-cases")
        await asyncio.sleep(3)
        self._hide_browser_windows()

        # Pass Cloudflare
        await self._wait_for_cloudflare()

        # Check if already logged in
        if await self._is_casehug_logged_in():
            self._emit_status(self.account_id, "Already logged in with Steam.", "success")
            await self._run_post_login_housekeeping(context_timeout_seconds=20)
            return

        # Restore Steam session from cookies saved in main add-account flow.
        if await self._restore_steam_session():
            self._emit_status(self.account_id, "Steam session restored from saved cookies.", "info")
        else:
            self._emit_status(self.account_id, "Saved Steam cookies not enough, using Steam sign-in flow.", "warning")

        # Fallback: click Steam login button on page.
        max_additional_retries = max(0, self._cfg_int("steam_login_max_retries", 1))
        total_attempts = 1 + max_additional_retries
        for attempt in range(1, total_attempts + 1):
            if await self._steam_login_via_button():
                if await self._run_post_login_housekeeping(context_timeout_seconds=30):
                    return

                self._emit_status(
                    self.account_id,
                    "Steam login looked successful, but CaseHug session was not stable yet.",
                    "warning",
                )

            if attempt < total_attempts:
                self._emit_status(
                    self.account_id,
                    f"Steam login retry {attempt}/{total_attempts - 1}...",
                    "warning",
                )
                try:
                    await self.page.get("https://casehug.com/free-cases")
                    await asyncio.sleep(2.5)
                    await self._wait_for_cloudflare(timeout=25)
                except Exception:
                    pass

        raise RuntimeError("Steam login could not be confirmed.")


    async def _run_post_login_housekeeping(self, context_timeout_seconds: int = 30) -> bool:
        """
        Finalize login flow without allowing silent hangs:
        - save cookies (best effort)
        - sync Steam profile (best effort)
        - verify CaseHug authenticated context (required)
        """
        cookie_timeout = max(6, self._cfg_int("post_login_cookie_sync_timeout_seconds", 12))
        profile_timeout = max(8, self._cfg_int("post_login_profile_sync_timeout_seconds", 20))
        context_timeout = max(12, int(context_timeout_seconds or 30))

        async def _await_step(label: str, coro, timeout: int, required: bool) -> bool:
            try:
                result = await asyncio.wait_for(coro, timeout=timeout)
            except asyncio.TimeoutError:
                self._emit_status(
                    self.account_id,
                    f"{label} timed out after {timeout}s.",
                    "warning",
                )
                logger.warning(
                    "Post-login step timed out: account=%s step=%s timeout=%ss",
                    self.account_id,
                    label,
                    timeout,
                )
                return not required
            except Exception as exc:
                self._emit_status(
                    self.account_id,
                    f"{label} failed: {exc}",
                    "warning",
                )
                logger.warning(
                    "Post-login step failed: account=%s step=%s error=%s",
                    self.account_id,
                    label,
                    exc,
                )
                return not required

            if required and not bool(result):
                self._emit_status(
                    self.account_id,
                    f"{label} could not confirm session.",
                    "warning",
                )
                return False
            return True

        await _await_step(
            "Saving session cookies",
            self._persist_steam_cookies_from_browser(),
            cookie_timeout,
            required=False,
        )
        await _await_step(
            "Syncing Steam profile",
            self._sync_steam_profile_from_browser(),
            profile_timeout,
            required=False,
        )
        return await _await_step(
            "Refreshing CaseHug session",
            self._ensure_casehug_context_after_login(timeout_seconds=context_timeout),
            timeout=context_timeout + 15,
            required=True,
        )

    async def _ensure_casehug_context_after_login(self, timeout_seconds: int = 30) -> bool:
        """Return to CaseHug page and confirm authenticated state there."""
        timeout_seconds = max(10, int(timeout_seconds or 30))

        for target_url in _CASEHUG_FREE_CASE_URLS:
            try:
                await self.page.get(target_url)
                await asyncio.sleep(2.0)
                await self._wait_for_cloudflare(timeout=min(20, timeout_seconds))
                if await self._is_casehug_logged_in():
                    return True
            except Exception:
                continue

        return await self._wait_for_casehug_login(timeout_seconds=min(45, timeout_seconds + 10))

    async def _is_casehug_logged_in(self) -> bool:
        try:
            # Prefer DOM checks over raw HTML substring to avoid false positives
            # from bundled JS/source maps that contain test-id literals.
            for selector in (
                '[data-testid="header-account-balance"]',
                'a[href="/user-account"]',
            ):
                try:
                    node = await self.page.query_selector(selector)
                    if node:
                        return True
                except Exception:
                    continue

            unauth = await self.page.query_selector('[data-testid="header-un-auth-button"]')
            if unauth:
                return False

            content = (await self.page.get_content()).lower()
        except Exception:
            return False
        return ('href="/user-account"' in content) and ("header-un-auth-button" not in content)

    async def _restore_steam_session(self) -> bool:
        cookies = self.account.cookies if isinstance(self.account.cookies, dict) else {}
        if not cookies:
            return False

        self._emit_status(self.account_id, "Restoring saved session cookies...", "info")
        restored = 0

        for name, value in cookies.items():
            if not name:
                continue
            cookie_value = "" if value is None else str(value)
            for domain in _SESSION_COOKIE_DOMAINS:
                try:
                    await self.page.send(
                        uc.cdp.network.set_cookie(
                            name=name,
                            value=cookie_value,
                            domain=domain,
                            path="/",
                        )
                    )
                    restored += 1
                except Exception:
                    continue

        if restored == 0:
            return False

        # First, try direct CaseHug session restore (cookies from login dialog are usually CaseHug cookies).
        for target_url in _CASEHUG_FREE_CASE_URLS:
            try:
                await self.page.get(target_url)
                await asyncio.sleep(2.0)
                await self._wait_for_cloudflare(timeout=15)
                if await self._is_casehug_logged_in():
                    return True
            except Exception:
                continue

        # Fallback: verify Steam session, then regular Steam-sign flow can continue.
        try:
            await self.page.get("https://steamcommunity.com/my")
            await asyncio.sleep(2.5)
            current_url = (self.page.url or "").lower()
            if "steamcommunity.com" in current_url and "login" not in current_url:
                return True
            content = (await self.page.get_content()).lower()
            if "steamcommunity.com" in current_url and "input_username" not in content:
                return True
        except Exception:
            return False
        return False

    async def _persist_steam_cookies_from_browser(self) -> bool:
        """Save current Steam cookies from browser session into account.cookies."""
        if not self.page:
            return False

        try:
            result = await self.page.send(uc.cdp.network.get_all_cookies())
        except Exception as exc:
            logger.debug("Could not read cookies via CDP for account %s: %s", self.account_id, exc)
            return False

        cookies_raw = []
        if isinstance(result, dict):
            cookies_raw = result.get("cookies") or []
        elif isinstance(result, list):
            cookies_raw = result
        else:
            candidate = getattr(result, "cookies", None)
            if isinstance(candidate, list):
                cookies_raw = candidate

        parsed = {}
        for item in cookies_raw:
            try:
                name = str(getattr(item, "name", "") or (item.get("name") if isinstance(item, dict) else "")).strip()
                value = str(getattr(item, "value", "") or (item.get("value") if isinstance(item, dict) else ""))
                domain = str(
                    getattr(item, "domain", "") or (item.get("domain") if isinstance(item, dict) else "")
                ).lower()
                if not name:
                    continue
                if not any(
                    host in domain
                    for host in ("steamcommunity.com", "steampowered.com", "casehug.com")
                ):
                    continue
                parsed[name] = value
            except Exception:
                continue

        if not parsed:
            return False

        try:
            AccountCRUD.update_cookies(self.db_session, self.account_id, parsed)
            self.account = AccountCRUD.get_by_id(self.db_session, self.account_id) or self.account
            self._emit_status(
                self.account_id,
                f"Steam session cookies saved ({len(parsed)}).",
                "info",
            )
            return True
        except Exception as exc:
            logger.warning(
                "Could not persist Steam cookies for account %s: %s",
                self.account_id,
                exc,
            )
            return False

    async def _sync_steam_profile_from_browser(self) -> bool:
        """Read Steam profile (id/nickname/avatar) from active session and persist it."""
        if not self.page:
            return False

        original_url = ""
        restore_casehug_context = False
        try:
            original_url = await self._get_tab_url(self.page)
            low = (original_url or "").lower()
            restore_casehug_context = ("casehug.com" in low)
        except Exception:
            original_url = ""
            restore_casehug_context = False

        try:
            await self.page.get("https://steamcommunity.com/my")
            await asyncio.sleep(2.3)
            current_url = await self._get_tab_url(self.page)
            low_url = (current_url or "").lower()
            if "steamcommunity.com" not in low_url or "login" in low_url:
                return False

            content = await self.page.get_content()

            steam_id = ""
            m = re.search(r"/profiles/(\d+)", current_url or "", re.IGNORECASE)
            if m:
                steam_id = m.group(1).strip()

            nickname = ""
            for pat in (
                r'<span class="actual_persona_name">([^<]+)</span>',
                r'<span class="persona_name_text_content">([^<]+)</span>',
                r"<title>([^<]+)::\s*Steam Community</title>",
            ):
                match = re.search(pat, content, re.IGNORECASE)
                if match:
                    nickname = html.unescape(match.group(1).strip())
                    if nickname:
                        break

            avatar_url = ""
            for pat in (
                r'<meta property="og:image" content="([^"]+)"',
                r'<img[^>]+class="[^"]*playerAvatarAutoSizeInner[^"]*"[^>]+src="([^"]+)"',
                r'<img[^>]+class="[^"]*playerAvatar[^"]*"[^>]+src="([^"]+)"',
            ):
                match = re.search(pat, content, re.IGNORECASE)
                if match:
                    avatar_url = html.unescape(match.group(1).strip())
                    if avatar_url:
                        break

            if not (steam_id or nickname or avatar_url):
                return False

            account = AccountCRUD.get_by_id(self.db_session, self.account_id) or self.account
            if not account:
                return False

            changed = False
            if steam_id and steam_id != (account.steam_id or ""):
                account.steam_id = steam_id
                changed = True
            if nickname and nickname != (account.steam_nickname or ""):
                account.steam_nickname = nickname
                if not (account.steam_username or "").strip():
                    account.steam_username = nickname
                changed = True
            if avatar_url and avatar_url != (account.steam_avatar_url or ""):
                account.steam_avatar_url = avatar_url
                changed = True

            if not changed:
                return False

            account.last_login = datetime.utcnow()
            self.db_session.commit()
            self.db_session.refresh(account)
            self.account = account
            self._emit_status(self.account_id, "Steam profile synced.", "info")
            return True
        except Exception as exc:
            logger.debug(
                "Could not sync Steam profile for account %s: %s",
                self.account_id,
                exc,
            )
            return False
        finally:
            if restore_casehug_context:
                target = original_url or _CASEHUG_FREE_CASE_URLS[0]
                try:
                    await self.page.get(target)
                    await asyncio.sleep(1.2)
                    self._hide_browser_windows()
                except Exception:
                    pass

    async def _dismiss_casehug_login_overlay(self) -> bool:
        """
        Best-effort dismissal for CaseHug modal/backdrop overlays that can block
        clicks or hide the top part of the page during login flow.
        """
        dismissed = False

        close_selectors = (
            '[data-testid="close-modal-button"]',
            ".ant-modal-close",
            ".ant-drawer-close",
            "button[aria-label='Close']",
            "button[aria-label='close']",
            "button[title='Close']",
            "button[title='close']",
        )

        for selector in close_selectors:
            try:
                node = await self.page.query_selector(selector)
                if not node:
                    continue
                await node.scroll_into_view()
                await asyncio.sleep(0.15)
                await node.click()
                dismissed = True
                await asyncio.sleep(0.35)
            except Exception:
                continue

        # Fallback: try backdrop click + ESC on page context.
        try:
            js_dismissed = await self.page.evaluate(
                r"""
(() => {
  let acted = false;
  const backdrops = [
    '.ant-modal-mask',
    '.ant-drawer-mask',
    '.ReactModal__Overlay',
    '[data-testid*="backdrop"]',
  ];
  for (const sel of backdrops) {
    const el = document.querySelector(sel);
    if (!el) continue;
    try { el.click(); acted = true; } catch (_) {}
  }
  try {
    document.dispatchEvent(new KeyboardEvent('keydown', { key: 'Escape', code: 'Escape', bubbles: true }));
    document.dispatchEvent(new KeyboardEvent('keyup', { key: 'Escape', code: 'Escape', bubbles: true }));
    acted = true;
  } catch (_) {}
  return acted;
})()
"""
            )
            if js_dismissed:
                dismissed = True
        except Exception:
            pass

        if dismissed:
            self._hide_browser_windows()
            await asyncio.sleep(0.6)
            logger.info("Dismissed CaseHug overlay for account %s.", self.account_id)
        return dismissed

    async def _click_best_steam_trigger(self) -> bool:
        # Preferred direct target on CaseHug when user is not authenticated.
        try:
            primary = await self.page.query_selector('button[data-testid="header-un-auth-button"]')
            if primary:
                await primary.scroll_into_view()
                await asyncio.sleep(0.3)
                await primary.click()
                self._hide_browser_windows()
                logger.info("Steam login trigger clicked: account=%s selector=header-un-auth-button", self.account_id)
                return True
        except Exception:
            pass

        candidates = []

        # Phase 1: buttons only (safer than generic anchors on dynamic pages).
        for selector in ("button",):
            try:
                elements = await self.page.select_all(selector)
            except Exception:
                continue
            for element in elements:
                try:
                    html = (await element.get_html() or "").lower()
                    try:
                        text = (await element.text or "").lower()
                    except Exception:
                        text = ""

                    blob = f"{text} {html}"
                    score = 0
                    if 'data-testid="header-un-auth-button"' in blob:
                        score += 120
                    if 'title="login"' in blob:
                        score += 70
                    if "ri-steam-fill" in blob:
                        score += 50
                    if "steam login" in blob:
                        score += 40
                    if "steam" in blob:
                        score += 15
                    if "login" in blob or "sign in" in blob:
                        score += 20
                    if "footer-link-steam" in blob:
                        score -= 100
                    if score < 20:
                        continue
                    candidates.append((score, element, selector, blob[:180]))
                except Exception:
                    continue

        # Phase 2: anchors fallback with strict filtering.
        if not candidates:
            try:
                elements = await self.page.select_all("a")
            except Exception:
                elements = []
            for element in elements:
                try:
                    html = (await element.get_html() or "").lower()
                    try:
                        text = (await element.text or "").lower()
                    except Exception:
                        text = ""

                    blob = f"{text} {html}"
                    if "addprofileaward" in blob:
                        continue
                    if "footer-link-steam" in blob:
                        continue
                    if "steamcommunity.com/id/" in blob or "steamcommunity.com/profiles/" in blob:
                        continue
                    if "href=" not in blob:
                        continue
                    if ("login" not in blob) and ("openid" not in blob):
                        continue

                    score = 0
                    if "login=true" in blob:
                        score += 70
                    if 'href="/login' in blob:
                        score += 60
                    if "steamcommunity.com/openid" in blob:
                        score += 50
                    if "steam" in blob:
                        score += 25
                    if "login" in blob:
                        score += 20
                    if score <= 0:
                        continue
                    candidates.append((score, element, "a", blob[:180]))
                except Exception:
                    continue

        if not candidates:
            return False

        candidates.sort(key=lambda item: item[0], reverse=True)
        for score, element, selector, snippet in candidates:
            try:
                await element.scroll_into_view()
                await asyncio.sleep(0.4)
                await element.click()
                self._hide_browser_windows()
                logger.info(
                    "Steam login trigger clicked: account=%s selector=%s score=%s snippet=%s",
                    self.account_id,
                    selector,
                    score,
                    snippet,
                )
                return True
            except Exception:
                continue
        return False

    async def _get_tab_url(self, tab) -> str:
        try:
            value = await tab.evaluate("window.location.href")
            if isinstance(value, str):
                return value
        except Exception:
            pass
        try:
            return tab.url or ""
        except Exception:
            return ""

    async def _complete_steam_openid_if_needed(self):
        if not self.browser:
            return

        deadline = asyncio.get_event_loop().time() + 18
        steam_tab = None

        while asyncio.get_event_loop().time() < deadline:
            tabs = list(getattr(self.browser, "tabs", []) or [])
            for tab in tabs:
                tab_url = (await self._get_tab_url(tab)).lower()
                if "steamcommunity.com/openid/login" in tab_url:
                    steam_tab = tab
                    break
            if steam_tab:
                break
            await asyncio.sleep(0.6)

        if not steam_tab:
            return

        logger.info("Steam OpenID tab detected for account %s.", self.account_id)
        try:
            activate_fn = getattr(steam_tab, "activate", None)
            if callable(activate_fn):
                maybe = activate_fn()
                if asyncio.iscoroutine(maybe):
                    await maybe
        except Exception:
            pass

        await asyncio.sleep(1.0)
        self._hide_browser_windows()

        selectors = [
            "#imageLogin",
            "input#imageLogin",
            "input[type='submit'][value*='Sign In']",
            "button[type='submit']",
        ]
        for selector in selectors:
            try:
                button = await steam_tab.query_selector(selector)
                if not button:
                    continue
                await button.scroll_into_view()
                await asyncio.sleep(0.3)
                await button.click()
                self._hide_browser_windows()
                logger.info(
                    "Clicked Steam OpenID approval button: account=%s selector=%s",
                    self.account_id,
                    selector,
                )
                await asyncio.sleep(2.0)
                return
            except Exception:
                continue

        # Fallback for markup variations.
        for selector in ("button", "input"):
            try:
                elements = await steam_tab.select_all(selector)
            except Exception:
                # Steam page can transiently timeout while querying controls.
                # This should not abort the whole login flow.
                continue
            for element in elements:
                try:
                    html = (await element.get_html() or "").lower()
                    if "sign in" not in html and "proceed" not in html and "allow" not in html:
                        continue
                    await element.scroll_into_view()
                    await asyncio.sleep(0.3)
                    await element.click()
                    self._hide_browser_windows()
                    logger.info(
                        "Clicked Steam OpenID fallback approval control: account=%s selector=%s",
                        self.account_id,
                        selector,
                    )
                    await asyncio.sleep(2.0)
                    return
                except Exception:
                    continue

    async def _wait_for_casehug_login(self, timeout_seconds: int = 35) -> bool:
        deadline = asyncio.get_event_loop().time() + timeout_seconds
        last_refresh = 0.0

        while asyncio.get_event_loop().time() < deadline:
            self._hide_browser_windows()
            if await self._is_casehug_logged_in():
                return True

            # If Steam OpenID popup is still around, try to complete it again.
            try:
                await self._complete_steam_openid_if_needed()
            except Exception:
                pass

            # Clear blocking overlays that can remain after redirects.
            try:
                await self._dismiss_casehug_login_overlay()
            except Exception:
                pass

            now = asyncio.get_event_loop().time()
            if now - last_refresh >= 12:
                for target_url in _CASEHUG_FREE_CASE_URLS:
                    try:
                        await self.page.get(target_url)
                        await asyncio.sleep(2.0)
                        self._hide_browser_windows()
                        await self._wait_for_cloudflare(timeout=15)
                        if await self._is_casehug_logged_in():
                            return True
                    except Exception:
                        continue
                last_refresh = now

            await asyncio.sleep(1.5)

        return await self._is_casehug_logged_in()

    async def _steam_login_via_button(self) -> bool:
        """Click the Steam login button on casehug."""
        self._emit_status(self.account_id, "Attempting Steam login via button...", "info")
        try:
            await self.page.get("https://casehug.com/free-cases")
            await asyncio.sleep(2.5)
            await self._wait_for_cloudflare(timeout=35)
            await self._dismiss_casehug_login_overlay()

            # Guard: page may already be authenticated even if login flow reached this path.
            if await self._is_casehug_logged_in():
                self._emit_status(
                    self.account_id,
                    "CaseHug session already authenticated.",
                    "success",
                )
                return True

            clicked = await self._click_best_steam_trigger()
            if not clicked:
                # One retry after overlay dismissal (some pages block clicks until modal closes).
                try:
                    await self._dismiss_casehug_login_overlay()
                except Exception:
                    pass
                clicked = await self._click_best_steam_trigger()

            if not clicked:
                if await self._is_casehug_logged_in():
                    self._emit_status(
                        self.account_id,
                        "Steam sign-in button not visible, but session is authenticated.",
                        "success",
                    )
                    return True
                self._emit_status(self.account_id, "Steam sign-in button not found.", "warning")
                return False

            await asyncio.sleep(3)
            self._hide_browser_windows()

            # Check boxes
            for testid in [
                "terms-and-age-verification-terms-privacy",
                "terms-and-age-verification-is-adult",
            ]:
                try:
                    cb = await self.page.query_selector(f'input[data-testid="{testid}"]')
                    if cb:
                        await cb.click()
                        await asyncio.sleep(0.5)
                except Exception:
                    pass

            # Submit
            try:
                submit = await self.page.query_selector('button[data-testid="sign-in-button"]')
                if submit:
                    await submit.click()
                    self._hide_browser_windows()
            except Exception:
                pass

            try:
                await asyncio.wait_for(self._complete_steam_openid_if_needed(), timeout=25)
            except asyncio.TimeoutError:
                self._emit_status(
                    self.account_id,
                    "Steam OpenID approval step timed out. Continuing login validation...",
                    "warning",
                )
            except Exception as exc:
                self._emit_status(
                    self.account_id,
                    f"Steam OpenID approval warning: {exc}",
                    "warning",
                )

            logged_in = await self._wait_for_casehug_login(timeout_seconds=35)
            if logged_in:
                self._emit_status(self.account_id, "Steam login successful.", "success")
                return True

            self._emit_status(self.account_id, "Steam login could not be confirmed.", "warning")
            return False

        except Exception as e:
            self._emit_status(self.account_id, f"Steam login error: {e}", "error")
            return False

    # ------------------------------------------------------------------ #
    #  CLOUDFLARE                                                          #
    # ------------------------------------------------------------------ #

    async def _wait_for_cloudflare(self, timeout: int = 30):
        """Wait until Cloudflare challenge is resolved (nodriver handles it automatically)."""
        self._emit_status(self.account_id, "Waiting for Cloudflare...", "info")
        deadline = asyncio.get_event_loop().time() + timeout
        while asyncio.get_event_loop().time() < deadline:
            self._hide_browser_windows()
            content = await self.page.get_content()
            cf_present = any(
                kw in content.lower()
                for kw in ["just a moment", "checking your browser", "cloudflare", "turnstile"]
            )
            if not cf_present:
                self._emit_status(self.account_id, "Cloudflare bypassed.", "info")
                return
            await asyncio.sleep(2)
        self._emit_status(self.account_id, "Cloudflare timeout — continuing anyway.", "warning")

    # ------------------------------------------------------------------ #
    #  CASE DETECTION                                                      #
    # ------------------------------------------------------------------ #

    async def _check_available_cases(self) -> list:
        """Return list of available case names."""
        self._emit_status(self.account_id, "Checking available cases...", "info")
        try:
            BotStatusCRUD.record_case_check(self.db_session, self.account_id)
        except Exception as exc:
            logger.debug("Could not persist last_case_check_at for account %s: %s", self.account_id, exc)
        await self.page.get("https://casehug.com/free-cases")
        await asyncio.sleep(3)
        await self._wait_for_cloudflare()

        content = await self.page.get_content()
        available = []

        level_order = [
            "wood", "iron", "bronze", "silver", "gold", "platinum",
            "emerald", "diamond", "master", "challenger", "legend", "mythic", "immortal",
        ]

        for case_type in ["discord", "steam"] + level_order:
            marker = f'href="/free-cases/{case_type}"'
            pos = content.find(marker)

            if pos == -1:
                if case_type in level_order:
                    self._emit_status(self.account_id, f"STOP at {case_type.upper()} (level locked).", "info")
                    break
                continue

            section = content[pos: pos + 2000]

            if "ri-timer-line" in section:
                self._emit_status(self.account_id, f"{case_type.upper()}: on cooldown", "info")
                if case_type in level_order:
                    continue  # Higher cases may still be available
                continue

            if "si-ch-lock" in section:
                self._emit_status(self.account_id, f"STOP at {case_type.upper()} (locked).", "info")
                if case_type in level_order:
                    break
                continue

            if ">Open<" in section:
                available.append(case_type)
                self._emit_status(self.account_id, f"{case_type.upper()}: available ✓", "info")

        return available

    # ------------------------------------------------------------------ #
    #  CASE OPENING                                                        #
    # ------------------------------------------------------------------ #

    async def _open_cases(self, cases: list) -> int:
        opened_count = 0
        for i, case_type in enumerate(cases, 1):
            if self.stop_event.is_set():
                break

            self._emit_status(
                self.account_id,
                f"Opening case {i}/{len(cases)}: {case_type.upper()}",
                "info",
            )
            if await self._open_single_case(case_type):
                opened_count += 1

            if i < len(cases):
                await self.page.get("https://casehug.com/free-cases")
                await asyncio.sleep(3)
        return opened_count

    async def _open_single_case(self, case_type: str) -> bool:
        case_url = f"https://casehug.com/free-cases/{case_type}"
        links = await self.page.select_all(f'a[href="/free-cases/{case_type}"]')
        if links:
            await links[0].scroll_into_view()
            await asyncio.sleep(0.5)
            await links[0].click()
            await asyncio.sleep(3)
        else:
            await self.page.get(case_url)
            await asyncio.sleep(3)

        # Find Open button
        button = None
        try:
            button = await self.page.query_selector('button[data-testid="open-button"]')
            if button:
                disabled = await button.get_attribute("disabled")
                if disabled is not None:
                    button = None
        except Exception:
            pass

        if not button:
            buttons = await self.page.select_all("button")
            for btn in buttons:
                try:
                    text = await btn.text
                    if text and "open" in text.lower():
                        disabled = await btn.get_attribute("disabled")
                        if disabled is None:
                            button = btn
                            break
                except Exception:
                    continue

        if not button:
            self._emit_status(self.account_id, f"{case_type.upper()}: Open button not found.", "warning")
            return False

        await button.scroll_into_view()
        await asyncio.sleep(0.5)
        await button.click()
        self._emit_status(self.account_id, f"{case_type.upper()}: clicked Open, waiting...", "info")
        await asyncio.sleep(15)
        return True

    # ------------------------------------------------------------------ #
    #  SKIN EXTRACTION                                                     #
    # ------------------------------------------------------------------ #

    async def _extract_new_skins(self) -> list:
        self._emit_status(self.account_id, "Extracting new skins from profile...", "info")
        try:
            await self.page.get("https://casehug.com/user-account")
            await asyncio.sleep(4)
            extracted = await self.page.evaluate(_JS_EXTRACT_NEW_DROPS)
            if isinstance(extracted, list) and extracted:
                normalized = []
                seen = set()
                for item in extracted:
                    try:
                        case_source = str(item.get("case") or "unknown").strip().lower()
                        skin_name = str(item.get("skin") or "").strip()
                        price_text = str(item.get("price") or "").strip()
                        item_id = str(item.get("item_id") or "").strip() or None
                        obtained_dt = self._parse_obtained_datetime(
                            str(item.get("obtained_date") or "").strip(),
                            str(item.get("obtained_time") or "").strip(),
                        )
                        dedupe_key = item_id or "|".join(
                            [
                                case_source,
                                skin_name,
                                price_text,
                                obtained_dt.strftime("%Y-%m-%d %H:%M:%S"),
                            ]
                        )
                        if dedupe_key in seen:
                            continue
                        seen.add(dedupe_key)

                        rarity = rarity_from_color(str(item.get("rarity_color") or "").strip() or None) or "Unknown"
                        normalized.append(
                            {
                                "case": case_source,
                                "skin": skin_name,
                                "price": price_text,
                                "rarity": rarity,
                                "condition": str(item.get("condition") or "").strip().upper() or None,
                                "skin_image_url": str(item.get("skin_image_url") or "").strip() or None,
                                "item_id": item_id,
                                "obtained_date": obtained_dt,
                            }
                        )
                    except Exception:
                        continue
                if normalized:
                    return normalized

            # Fallback parser if DOM extraction fails.
            content = await self.page.get_content()
            return self._parse_new_skins(content)
        except Exception as e:
            logger.error(f"Error extracting skins: {e}")
            return []

    @staticmethod
    def _parse_new_skins(content: str) -> list:
        skins = []
        label_pattern = re.compile(r'<div data-testid="your-drop-card-label"[^>]*>([^<]+)</div>')
        for match in label_pattern.finditer(content):
            if match.group(1).strip().lower() != "new":
                continue
            start = match.start()
            search_back = content[max(0, start - 5000): start]
            container = re.search(r'<div class="sc-965b1227-6[^"]*">', search_back)
            if not container:
                continue
            c_start = start - len(search_back) + container.start()
            section = content[c_start: start + 3000]

            name_m = re.search(r'<div data-testid="your-drop-name"[^>]*>([^<]+)</div>', section)
            cat_m = re.search(r'<div data-testid="your-drop-category"[^>]*>([^<]+)</div>', section)
            price_m = re.search(r'<span data-testid="your-drop-price"[^>]*>([^<]+)</span>', section)
            case_m = re.search(r'<div data-testid="your-drops-hover-date"[^>]*>([^<]+)</div>', section)
            date_m = re.search(
                r'data-testid="your-drops-hover-date"[^>]*>[^<]*</div>\s*<div>([^<]+)</div>',
                section,
                re.IGNORECASE | re.DOTALL,
            )
            time_m = re.search(
                r'data-testid="your-drops-hover-is-drawn"[^>]*>\s*<div>[^<]*</div>\s*<div>([^<]+)</div>',
                section,
                re.IGNORECASE | re.DOTALL,
            )
            cond_m = re.search(r'<div data-testid="your-drop-card-condition"[^>]*>([^<]+)</div>', section)
            img_m = re.search(r'<img[^>]+data-testid="your-drop-skin-image"[^>]+src="([^"]+)"', section)
            item_m = re.search(r'(?:/upgrader\?item=|/skin-changer\?item=)(\d+)', section, re.IGNORECASE)
            rarity_color_m = re.search(
                r'stop\s+offset="40%"\s+stop-color="(#[0-9A-Fa-f]{6})"',
                section,
                re.IGNORECASE,
            )

            if name_m and cat_m and price_m:
                rarity_color = rarity_color_m.group(1).strip() if rarity_color_m else None
                obtained_dt = AutomationLogic._parse_obtained_datetime(
                    date_m.group(1).strip() if date_m else "",
                    time_m.group(1).strip() if time_m else "",
                )
                skins.append({
                    "case": case_m.group(1).strip().lower() if case_m else "unknown",
                    "skin": f"{name_m.group(1).strip()} | {cat_m.group(1).strip()}",
                    "price": price_m.group(1).strip(),
                    "rarity": rarity_from_color(rarity_color) or "Unknown",
                    "condition": cond_m.group(1).strip().upper() if cond_m else None,
                    "skin_image_url": html.unescape(img_m.group(1).strip()) if img_m else None,
                    "item_id": item_m.group(1).strip() if item_m else None,
                    "obtained_date": obtained_dt,
                })
        return skins

    @staticmethod
    def _parse_obtained_datetime(date_raw: str, time_raw: str) -> datetime:
        date_raw = (date_raw or "").strip()
        time_raw = (time_raw or "").strip()
        if date_raw and time_raw:
            for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
                try:
                    return datetime.strptime(f"{date_raw} {time_raw}", fmt)
                except Exception:
                    continue
        return datetime.utcnow()

    @staticmethod
    def _parse_price(price_str: str) -> float:
        try:
            return float(re.sub(r"[^\d.]", "", price_str))
        except Exception:
            return 0.0
