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
from typing import Callable

import nodriver as uc
import psutil
from sqlalchemy.orm import Session

from ..database.crud import AccountCRUD, BotStatusCRUD, SkinCRUD
from .rarity import rarity_from_color

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
    const obtainedDate = caseSourceEl && caseSourceEl.nextElementSibling
      ? textOf(caseSourceEl.nextElementSibling)
      : "";
    const obtainedWrap = card.querySelector('[data-testid="your-drops-hover-is-drawn"]');
    const obtainedTime = obtainedWrap && obtainedWrap.children && obtainedWrap.children.length > 1
      ? textOf(obtainedWrap.children[1])
      : "";
    const condition = textOf(card.querySelector('[data-testid="your-drop-card-condition"]'));
    const image = card.querySelector('[data-testid="your-drop-skin-image"]');

    const cssColor = categoryEl ? toHex(getComputedStyle(categoryEl).color) : "";
    const gradStop = card.querySelector('linearGradient stop[offset="40%"]');
    const gradientColor = gradStop ? toHex(gradStop.getAttribute("stop-color") || "") : "";

    if (!name || !category || !price) continue;

    out.push({
      case: (caseSource || "").toLowerCase() || "unknown",
      skin: `${name} | ${category}`.trim(),
      price: price,
      obtained_date_raw: obtainedDate || "",
      obtained_time_raw: obtainedTime || "",
      condition: (condition || "").toUpperCase() || null,
      skin_image_url: image ? (image.currentSrc || image.src || "") : "",
      rarity_color: cssColor || gradientColor || "",
    });
  }

  return out;
})()
"""


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
    ):
        self.db_session = db_session
        self.account_id = account_id
        self.account = AccountCRUD.get_by_id(self.db_session, self.account_id)
        self.stop_event = stop_event
        self._emit_status = status_callback
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

    # ------------------------------------------------------------------ #
    #  BROWSER SETUP                                                       #
    # ------------------------------------------------------------------ #

    async def _start_browser(self):
        """Launch nodriver browser without GUI (off-screen window)."""
        account_name = _sanitize_profile_name(self.account.account_name)
        profile_dir = os.path.abspath(f"profiles/{account_name}")
        os.makedirs(profile_dir, exist_ok=True)

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
            seen_signatures = set()
            for r in results:
                try:
                    skin_name = (r.get("skin") or "").strip()
                    case_source = (r.get("case") or "").strip().lower() or None
                    skin_value = self._parse_price(r.get("price", ""))
                    signature = (
                        self.account_id,
                        skin_name.lower(),
                        case_source or "",
                        round(float(skin_value or 0.0), 4),
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

                    if SkinCRUD.find_recent_duplicate(
                        self.db_session,
                        account_id=self.account_id,
                        skin_name=skin_name,
                        case_source=case_source,
                        estimated_price=skin_value,
                        window_minutes=20,
                    ):
                        logger.info(
                            "Skipping recent duplicate skin in DB: account=%s skin=%s case=%s price=%.4f",
                            self.account_id,
                            skin_name,
                            case_source,
                            skin_value,
                        )
                        continue

                    total_value += skin_value
                    SkinCRUD.create(
                        self.db_session,
                        account_id=self.account_id,
                        skin_name=skin_name,
                        estimated_price=skin_value,
                        case_source=case_source,
                        rarity=r.get("rarity"),
                        condition=r.get("condition"),
                        skin_image_url=r.get("skin_image_url"),
                        obtained_date=r.get("obtained_date") or datetime.utcnow(),
                    )
                    saved_skins_count += 1
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
            await self._persist_steam_cookies_from_browser()
            await self._sync_steam_profile_from_browser()
            return

        # Restore Steam session from cookies saved in main add-account flow.
        if await self._restore_steam_session():
            self._emit_status(self.account_id, "Steam session restored from saved cookies.", "info")
        else:
            self._emit_status(self.account_id, "Saved Steam cookies not enough, using Steam sign-in flow.", "warning")

        # Fallback: click Steam login button on page
        if await self._steam_login_via_button():
            await self._persist_steam_cookies_from_browser()
            await self._sync_steam_profile_from_browser()
            return
        raise RuntimeError("Steam login could not be confirmed.")

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

        self._emit_status(self.account_id, "Restoring Steam session from saved cookies...", "info")
        restored = 0

        for name, value in cookies.items():
            if not name:
                continue
            cookie_value = "" if value is None else str(value)
            for domain in (".steamcommunity.com", "steamcommunity.com"):
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
                    break
                except Exception:
                    continue

        if restored == 0:
            return False

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
                if ("steamcommunity.com" not in domain) and ("steampowered.com" not in domain):
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
            elements = await self.page.select_all(selector)
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
            elements = await self.page.select_all("a")
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
            elements = await steam_tab.select_all(selector)
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

            now = asyncio.get_event_loop().time()
            if now - last_refresh >= 12:
                try:
                    await self.page.get("https://casehug.com/free-cases")
                    await asyncio.sleep(2.0)
                    self._hide_browser_windows()
                    await self._wait_for_cloudflare(timeout=15)
                except Exception:
                    pass
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

            clicked = await self._click_best_steam_trigger()
            if not clicked:
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

            await self._complete_steam_openid_if_needed()

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
                for item in extracted:
                    try:
                        rarity = rarity_from_color(str(item.get("rarity_color") or "").strip() or None) or "Unknown"
                        obtained_date = self._parse_obtained_datetime(
                            str(item.get("obtained_date_raw") or "").strip(),
                            str(item.get("obtained_time_raw") or "").strip(),
                        )
                        normalized.append(
                            {
                                "case": str(item.get("case") or "unknown").strip().lower(),
                                "skin": str(item.get("skin") or "").strip(),
                                "price": str(item.get("price") or "").strip(),
                                "rarity": rarity,
                                "condition": str(item.get("condition") or "").strip().upper() or None,
                                "skin_image_url": str(item.get("skin_image_url") or "").strip() or None,
                                "obtained_date": obtained_date,
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
            case_m = re.search(
                r'<div data-testid="your-drops-hover-date"[^>]*>([^<]+)</div>\s*<div>([^<]+)</div>',
                section,
            )
            obtained_time_m = re.search(
                r'data-testid="your-drops-hover-is-drawn"[^>]*>\s*<div>[^<]*</div>\s*<div>([^<]+)</div>',
                section,
            )
            cond_m = re.search(r'<div data-testid="your-drop-card-condition"[^>]*>([^<]+)</div>', section)
            img_m = re.search(r'<img[^>]+data-testid="your-drop-skin-image"[^>]+src="([^"]+)"', section)
            rarity_color_m = re.search(
                r'stop\s+offset="40%"\s+stop-color="(#[0-9A-Fa-f]{6})"',
                section,
                re.IGNORECASE,
            )

            if name_m and cat_m and price_m:
                rarity_color = rarity_color_m.group(1).strip() if rarity_color_m else None
                obtained_date = AutomationLogic._parse_obtained_datetime(
                    case_m.group(2).strip() if case_m and len(case_m.groups()) > 1 else "",
                    obtained_time_m.group(1).strip() if obtained_time_m else "",
                )
                skins.append({
                    "case": case_m.group(1).strip().lower() if case_m else "unknown",
                    "skin": f"{name_m.group(1).strip()} | {cat_m.group(1).strip()}",
                    "price": price_m.group(1).strip(),
                    "rarity": rarity_from_color(rarity_color) or "Unknown",
                    "condition": cond_m.group(1).strip().upper() if cond_m else None,
                    "skin_image_url": html.unescape(img_m.group(1).strip()) if img_m else None,
                    "obtained_date": obtained_date,
                })
        return skins

    @staticmethod
    def _parse_obtained_datetime(date_raw: str, time_raw: str):
        date_text = (date_raw or "").strip()
        time_text = (time_raw or "").strip()
        if not date_text or not time_text:
            return None
        try:
            return datetime.strptime(f"{date_text} {time_text}", "%Y-%m-%d %H:%M:%S")
        except Exception:
            return None

    @staticmethod
    def _parse_price(price_str: str) -> float:
        try:
            return float(re.sub(r"[^\d.]", "", price_str))
        except Exception:
            return 0.0
