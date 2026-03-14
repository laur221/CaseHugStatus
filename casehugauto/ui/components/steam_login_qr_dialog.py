"""Add-account dialog with headless Steam login, QR preview, and credential submit."""

from __future__ import annotations

import asyncio
import base64
from datetime import datetime, timedelta
import io
import logging
from pathlib import Path
import threading
import time
from uuid import uuid4

import flet as ft

try:
    from PIL import Image, ImageOps
except Exception:
    Image = None
    ImageOps = None

from ...core.steam_login_launcher import steam_login_launcher
from ...core.profile_store import ensure_profile_path
from ...database.crud import AccountCRUD
from ...database.db import SessionLocal

logger = logging.getLogger(__name__)


class SteamLoginQRDialog:
    """Create account through an isolated Steam headless login session."""

    _LOG_IMAGE_PATTERNS = (
        "steam_qr_preview_*.png",
        "steam_qr_*.png",
        "qr_t*.png",
        "debug_branch_*.png",
        "qr_direct_geom*.png",
    )

    def __init__(self, app, on_success=None):
        self.app = app
        self.on_success = on_success
        self.dialog = None
        self.status_text = None
        self.monitor_ring = None
        self.monitor_text = None
        self._step_icons = {}
        self._step_texts = {}
        self.qr_image = None
        self.detected_account_text = None
        self.username_input = None
        self.password_input = None
        self._session_ref = f"add_{int(time.time() * 1000)}"
        self._qr_preview_path = ""
        self._detected_account_name = ""
        self._steam_ok = False
        self._steam_profile = {}
        self._busy = False
        self._saving = False
        self._monitor_attempts = 0
        self._last_status_message = ""
        self._auth_monitor_enabled = False
        self._auth_monitor_started = False
        self._auth_monitor_stop = threading.Event()

    def _page(self):
        if hasattr(self.app, "page") and self.app.page:
            return self.app.page
        return self.app.main_area.page

    def show(self):
        self._cleanup_stale_log_images(max_age_hours=12)
        self.status_text = ft.Text(
            "Pornim sesiunea de login Steam...",
            size=12,
            color="#888888",
        )
        self.monitor_ring = ft.ProgressRing(width=14, height=14, value=None, color="#00d4ff")
        self.monitor_text = ft.Text("Stare: inițializare...", size=12, color="#00d4ff")
        self.detected_account_text = ft.Text(
            "Cont detectat: -",
            size=12,
            color="#aaaaaa",
        )
        self.username_input = ft.TextField(
            label="Steam Username sau Email (opțional)",
            width=420,
        )
        self.password_input = ft.TextField(
            label="Steam Password (nu se salvează)",
            password=True,
            can_reveal_password=True,
            width=420,
        )
        self.qr_image = ft.Image(
            width=320,
            height=320,
            fit=ft.ImageFit.CONTAIN,
            visible=False,
        )

        login_form = ft.Column(
            [
                self.detected_account_text,
                self.username_input,
                self.password_input,
            ],
            spacing=10,
            width=430,
        )

        qr_panel = ft.Container(
            content=ft.Column(
                [
                    ft.Text("Logare prin QR", size=12, color="#88aaff"),
                    self.qr_image,
                ],
                spacing=10,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            width=350,
            padding=12,
            border_radius=10,
            bgcolor="#11151d",
            alignment=ft.alignment.top_center,
        )
        progress_panel = self._build_progress_panel()

        self.dialog = ft.AlertDialog(
            title=ft.Text("Adăugare Cont Steam"),
            content=ft.Column(
                [
                    self.status_text,
                    ft.Row(
                        [
                            self.monitor_ring,
                            self.monitor_text,
                        ],
                        spacing=8,
                        vertical_alignment=ft.CrossAxisAlignment.CENTER,
                    ),
                    ft.Row(
                        [
                            login_form,
                            qr_panel,
                        ],
                        spacing=14,
                        vertical_alignment=ft.CrossAxisAlignment.START,
                        wrap=False,
                    ),
                    progress_panel,
                ],
                spacing=12,
                width=840,
                scroll=ft.ScrollMode.AUTO,
            ),
            actions=[
                ft.TextButton("Actualizează QR", on_click=self._refresh_qr),
                ft.TextButton("Trimite Datele", on_click=self._submit_credentials),
                ft.TextButton("Verifică Login", on_click=self._check_steam_login),
                ft.TextButton("Salvează Contul", on_click=self._save_account),
                ft.TextButton("Anulează", on_click=self._cancel),
            ],
            modal=True,
        )

        self._page().dialog = self.dialog
        self.dialog.open = True
        self._page().update()
        self._publish_activity("Dialog deschis. Pregătim sesiunea Steam...", "info")
        self._start_headless_session()
        self._start_auth_monitor()

    def _set_status(self, message: str, status: str = "info"):
        self.status_text.value = message
        self.status_text.color = self._status_color(status)
        if message != self._last_status_message:
            self._publish_activity(message, status)
            self._last_status_message = message
        self._page().update()

    def _status_color(self, status: str) -> str:
        color_map = {
            "info": "#00d4ff",
            "success": "#51cf66",
            "error": "#ff6b6b",
            "warning": "#fcc419",
            "stopped": "#f59f00",
        }
        return color_map.get((status or "").lower(), "#888888")

    def _build_progress_panel(self) -> ft.Container:
        self._step_icons = {}
        self._step_texts = {}

        step_defs = [
            ("browser", "1. Pornim browserul Steam"),
            ("qr", "2. Afișăm codul QR"),
            ("approve", "3. Așteptăm confirmarea în aplicația Steam"),
            ("save", "4. Salvăm contul"),
        ]

        rows = []
        for key, label in step_defs:
            icon = ft.Icon(ft.icons.RADIO_BUTTON_UNCHECKED, size=16, color="#6f7785")
            text = ft.Text(label, size=12, color="#9aa2b1")
            self._step_icons[key] = icon
            self._step_texts[key] = text
            rows.append(
                ft.Row(
                    [icon, text],
                    spacing=8,
                    vertical_alignment=ft.CrossAxisAlignment.CENTER,
                )
            )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Progres Login", size=12, color="#8f8f8f"),
                    ft.Text(
                        "Scanează QR din aplicația Steam și aprobă loginul pe telefon.",
                        size=11,
                        color="#6f7785",
                    ),
                    ft.Column(rows, spacing=6),
                ],
                spacing=8,
            ),
            padding=10,
            border_radius=8,
            bgcolor="#171b22",
        )

    def _set_step_state(self, step_key: str, state: str):
        icon = self._step_icons.get(step_key)
        text = self._step_texts.get(step_key)
        if not icon or not text:
            return

        if state == "active":
            icon.name = ft.icons.HOURGLASS_TOP
            icon.color = "#00d4ff"
            text.color = "#d7ebff"
        elif state == "done":
            icon.name = ft.icons.CHECK_CIRCLE
            icon.color = "#51cf66"
            text.color = "#a8f0b8"
        elif state == "error":
            icon.name = ft.icons.ERROR
            icon.color = "#ff6b6b"
            text.color = "#ffb3b3"
        else:
            icon.name = ft.icons.RADIO_BUTTON_UNCHECKED
            icon.color = "#6f7785"
            text.color = "#9aa2b1"

    def _set_monitor_state(self, message: str, status: str = "info", busy: bool = True):
        if self.monitor_text:
            self.monitor_text.value = f"Stare: {message}"
            self.monitor_text.color = self._status_color(status)
        if self.monitor_ring:
            self.monitor_ring.visible = busy
        self._page().update()

    def _publish_activity(self, message: str, status: str = "info"):
        if hasattr(self.app, "add_activity"):
            self.app.add_activity(f"Adăugare cont Steam: {message}", status)

    def _start_headless_session(self):
        if self._busy:
            return
        self._busy = True
        self._set_step_state("browser", "active")
        self._set_monitor_state("pornim browserul...", "info", busy=True)

        try:
            logger.info(
                "Starting headless Steam add-account session without temporary profile: session_ref=%s",
                self._session_ref,
            )

            ok, msg = steam_login_launcher.start_steam_headless(self._session_ref, "")
            if not ok:
                self._set_step_state("browser", "error")
                self._set_monitor_state("nu am putut porni browserul", "error", busy=False)
                self._set_status(msg, "error")
                return

            self._set_step_state("browser", "done")
            self._set_step_state("qr", "active")
            self._set_monitor_state("browser pornit, pregătim codul QR...", "info", busy=True)
            self._set_status("Browser pornit. Încărcăm codul QR...", "info")
            self._fetch_qr(timeout_seconds=25)
        except Exception as exc:
            logger.error("Failed to start headless Steam session: %s", exc, exc_info=True)
            self._set_step_state("browser", "error")
            self._set_monitor_state("pornirea sesiunii a eșuat", "error", busy=False)
            self._set_status(f"Nu am putut porni sesiunea Steam: {exc}", "error")
        finally:
            self._busy = False

    def _start_auth_monitor(self):
        if self._auth_monitor_started:
            return
        self._auth_monitor_started = True
        self._auth_monitor_enabled = True
        self._auth_monitor_stop.clear()
        self._monitor_attempts = 0
        logger.info("Steam auth monitor started: session_ref=%s", self._session_ref)
        self._set_monitor_state("așteptăm confirmarea în Steam...", "info", busy=True)

        async def monitor():
            try:
                while self._auth_monitor_enabled and not self._auth_monitor_stop.is_set():
                    await asyncio.sleep(2.5)
                    if not self.dialog or not self.dialog.open:
                        break
                    if self._saving:
                        continue
                    if self._steam_ok:
                        continue

                    self._monitor_attempts += 1
                    ok, msg, _cookies = await asyncio.to_thread(
                        steam_login_launcher.is_steam_authenticated,
                        self._session_ref,
                    )
                    if self._monitor_attempts % 2 == 0:
                        self._set_monitor_state(
                            "așteptăm confirmarea în aplicația Steam...",
                            "info",
                            busy=True,
                        )
                    if not ok:
                        if self._monitor_attempts % 6 == 0:
                            logger.info(
                                "Steam auth monitor waiting: session_ref=%s attempts=%s status=%s",
                                self._session_ref,
                                self._monitor_attempts,
                                msg,
                            )
                        continue

                    ok_profile, _msg_profile, profile = await asyncio.to_thread(
                        steam_login_launcher.get_steam_profile,
                        self._session_ref,
                    )
                    if not ok_profile:
                        continue

                    self._steam_ok = True
                    self._steam_profile = profile
                    self._set_step_state("approve", "done")
                    self._set_step_state("save", "active")
                    self._set_monitor_state("login detectat, salvăm contul...", "success", busy=False)
                    self._detected_account_name = self._build_unique_account_name(
                        profile.get("steam_nickname") or ""
                    )
                    self.detected_account_text.value = f"Cont detectat: {self._detected_account_name}"
                    self._set_status("Login detectat. Salvăm contul automat...", "success")
                    self._save_account(None, auto_trigger=True)
                    break
            except Exception as exc:
                logger.warning("Steam auth monitor stopped with error: %s", exc, exc_info=True)
                self._set_step_state("approve", "error")
                self._set_monitor_state("monitorul s-a oprit cu eroare", "error", busy=False)
            finally:
                logger.info(
                    "Steam auth monitor stopped: session_ref=%s enabled=%s dialog_open=%s",
                    self._session_ref,
                    self._auth_monitor_enabled,
                    bool(self.dialog and self.dialog.open),
                )
                if not self._steam_ok and self.dialog and self.dialog.open:
                    self._set_step_state("approve", "error")
                    self._set_monitor_state("nu a fost detectat loginul încă", "warning", busy=False)

        self._page().run_task(monitor)

    def _apply_qr_image(self, image_base64: str, status_message: str):
        self.qr_image.src_base64 = None
        self.qr_image.src = None
        try:
            raw = base64.b64decode(image_base64)
            if Image and ImageOps:
                qr_img = Image.open(io.BytesIO(raw)).convert("RGB")
                # Improve phone scan reliability: crisp upscale + white quiet border.
                nearest = getattr(getattr(Image, "Resampling", Image), "NEAREST")
                scale = 4
                qr_img = qr_img.resize((qr_img.width * scale, qr_img.height * scale), nearest)
                qr_img = ImageOps.expand(qr_img, border=32, fill="white")
                buffer = io.BytesIO()
                qr_img.save(buffer, format="PNG")
                output_bytes = buffer.getvalue()
            else:
                output_bytes = raw

            preview_dir = Path("logs")
            preview_dir.mkdir(parents=True, exist_ok=True)
            self._cleanup_current_preview()
            preview_file = preview_dir / f"steam_qr_preview_{self._session_ref}.png"
            preview_file.write_bytes(output_bytes)
            self._qr_preview_path = str(preview_file.resolve())
            self.qr_image.src = self._qr_preview_path
        except Exception:
            # Fallback when local file preview cannot be written.
            self.qr_image.src_base64 = image_base64
        self.qr_image.visible = True
        logger.info(
            "Steam QR captured: session_ref=%s base64_len=%s preview=%s",
            self._session_ref,
            len(image_base64 or ""),
            self._qr_preview_path or "<base64>",
        )
        self._set_status(status_message, "success")
        self._page().update()

    def _fetch_qr(self, timeout_seconds: int = 30):
        ok, msg, image_base64 = steam_login_launcher.get_qr_image_data(
            self._session_ref,
            timeout_seconds,
        )
        if not ok:
            logger.warning(
                "QR fetch failed: session_ref=%s timeout=%s message=%s",
                self._session_ref,
                timeout_seconds,
                msg,
            )
            self._set_step_state("qr", "error")
            self._set_monitor_state("codul QR nu este disponibil încă", "warning", busy=True)
            self._set_status(msg, "error")
            return

        status_message = (
            "Cod QR actualizat. Scanează acum din aplicația Steam sau folosește datele de login."
            if "snapshot" not in (msg or "").lower()
            else "Pagina Steam s-a încărcat. Apasă 'Actualizează QR' dacă nu vezi codul."
        )
        self._set_step_state("qr", "done")
        self._set_step_state("approve", "active")
        self._set_monitor_state("codul QR e gata, așteptăm aprobarea...", "info", busy=True)
        self._apply_qr_image(image_base64, status_message)

    def _refresh_qr(self, _):
        self._fetch_qr(timeout_seconds=35)

    def _submit_credentials(self, _):
        username = (self.username_input.value or "").strip()
        password = self.password_input.value or ""
        if not username or not password:
            self._set_status("Completează username și parola Steam.", "error")
            return

        self._set_step_state("approve", "active")
        self._set_monitor_state("trimitem datele de login...", "info", busy=True)
        ok, msg = steam_login_launcher.submit_credentials(
            session_ref=self._session_ref,
            steam_username=username,
            steam_password=password,
        )
        self.password_input.value = ""
        logger.info(
            "Steam credentials submit result: session_ref=%s success=%s",
            self._session_ref,
            ok,
        )
        if ok:
            self._set_monitor_state("datele au fost trimise, așteptăm confirmarea...", "info", busy=True)
        else:
            self._set_step_state("approve", "error")
            self._set_monitor_state("nu am putut trimite datele", "error", busy=False)
        self._set_status(msg, "success" if ok else "error")
        self._page().update()

    def _check_steam_login(self, _):
        ok, msg, _cookies = steam_login_launcher.is_steam_authenticated(self._session_ref)
        self._steam_ok = bool(ok)
        if not ok:
            logger.info(
                "Steam auth not confirmed yet: session_ref=%s message=%s",
                self._session_ref,
                msg,
            )
            self._set_step_state("approve", "active")
            self._set_monitor_state("loginul nu este confirmat încă", "warning", busy=True)
            self._set_status(msg, "error")
            return

        ok_profile, msg_profile, profile = steam_login_launcher.get_steam_profile(self._session_ref)
        if not ok_profile:
            self._set_step_state("approve", "error")
            self._set_monitor_state("nu am putut citi profilul Steam", "error", busy=False)
            self._set_status(msg_profile, "error")
            return

        self._steam_profile = profile
        self._detected_account_name = self._build_unique_account_name(profile.get("steam_nickname") or "")
        self.detected_account_text.value = f"Cont detectat: {self._detected_account_name}"
        self._set_step_state("approve", "done")
        self._set_step_state("save", "active")
        self._set_monitor_state("login confirmat", "success", busy=False)
        logger.info(
            "Steam profile detected for add-account session: session_ref=%s steam_id=%s nickname=%s",
            self._session_ref,
            profile.get("steam_id", ""),
            profile.get("steam_nickname", ""),
        )
        self._set_status("Login confirmat. Numele contului a fost preluat automat.", "success")
        self._page().update()

    def _save_account(self, _, auto_trigger: bool = False):
        if self._saving:
            return
        self._saving = True
        self._set_step_state("save", "active")
        self._set_monitor_state("salvăm contul...", "info", busy=True)
        account_name = (self._detected_account_name or "").strip()
        if not account_name:
            self._set_step_state("save", "error")
            self._set_monitor_state("nu putem salva: contul nu e detectat", "error", busy=False)
            self._set_status("Contul nu a fost detectat încă. Apasă 'Verifică Login'.", "error")
            self._saving = False
            return
        if not self._steam_ok:
            self._set_step_state("save", "error")
            self._set_monitor_state("nu putem salva: loginul nu e confirmat", "error", busy=False)
            self._set_status("Loginul Steam nu este confirmat. Apasă 'Verifică Login'.", "error")
            self._saving = False
            return

        db = SessionLocal()
        try:
            self._auth_monitor_enabled = False
            self._auth_monitor_stop.set()
            # Close browser before persisting account metadata.
            steam_login_launcher.close(self._session_ref)

            final_profile_path = ensure_profile_path(account_name)
            logger.info(
                "Creating final profile for account save: session_ref=%s account=%s final_profile=%s",
                self._session_ref,
                account_name,
                final_profile_path,
            )

            account = AccountCRUD.get_by_name(db, account_name)
            if not account:
                account = AccountCRUD.create(
                    db,
                    account_name=account_name,
                    steam_username=self._steam_profile.get("steam_username"),
                    steam_id=self._steam_profile.get("steam_id"),
                    steam_nickname=self._steam_profile.get("steam_nickname") or account_name,
                    cookies=self._steam_profile.get("cookies"),
                )

            # Persist final dedicated profile path for this account.
            account.browser_profile_path = final_profile_path
            account.last_login = datetime.utcnow()
            if self._steam_profile.get("steam_id"):
                account.steam_id = self._steam_profile.get("steam_id")
            if self._steam_profile.get("steam_nickname"):
                account.steam_nickname = self._steam_profile.get("steam_nickname")
            if self._steam_profile.get("steam_username"):
                account.steam_username = self._steam_profile.get("steam_username")
            if self._steam_profile.get("cookies"):
                account.cookies = self._steam_profile.get("cookies")
            db.commit()
            db.refresh(account)

            logger.info(
                "Account saved from Steam session: account_id=%s account_name=%s",
                account.id,
                account.account_name,
            )
            self._set_step_state("save", "done")
            self._set_monitor_state("cont salvat cu succes", "success", busy=False)
            self._set_status(
                "Cont salvat automat." if auto_trigger else "Cont salvat.",
                "success",
            )

            if self.on_success:
                self.on_success(account)

            self.dialog.open = False
            self._page().update()
            self._cleanup_current_preview()
        except Exception as exc:
            logger.error("Could not save account after Steam login: %s", exc, exc_info=True)
            self._set_step_state("save", "error")
            self._set_monitor_state("salvarea a eșuat", "error", busy=False)
            self._set_status(f"Nu am putut salva contul: {exc}", "error")
            db.rollback()
        finally:
            db.close()
            self._saving = False

    def _cancel(self, _):
        self._auth_monitor_enabled = False
        self._auth_monitor_stop.set()
        steam_login_launcher.close(self._session_ref)
        self._set_monitor_state("sesiune anulată", "stopped", busy=False)
        self._cleanup_current_preview()
        logger.info("Steam add-account session canceled: session_ref=%s", self._session_ref)
        self.dialog.open = False
        self._page().update()

    def _cleanup_current_preview(self):
        preview_path = (self._qr_preview_path or "").strip()
        if not preview_path:
            return
        try:
            path = Path(preview_path)
            if path.exists():
                path.unlink()
        except Exception:
            logger.debug("Could not remove QR preview file: %s", preview_path, exc_info=True)
        finally:
            self._qr_preview_path = ""

    def _cleanup_stale_log_images(self, max_age_hours: int = 12):
        logs_dir = Path("logs")
        if not logs_dir.exists():
            return

        cutoff = datetime.now() - timedelta(hours=max_age_hours)
        removed = 0

        try:
            for pattern in self._LOG_IMAGE_PATTERNS:
                for path in logs_dir.glob(pattern):
                    try:
                        modified = datetime.fromtimestamp(path.stat().st_mtime)
                        if modified <= cutoff:
                            path.unlink(missing_ok=True)
                            removed += 1
                    except Exception:
                        logger.debug("Could not remove stale log image: %s", path, exc_info=True)
        except Exception:
            logger.debug("Stale log image cleanup failed.", exc_info=True)

        if removed:
            logger.info("Removed stale log images: count=%s", removed)

    def _build_unique_account_name(self, base_name: str) -> str:
        candidate = (base_name or "").strip() or f"steam_{uuid4().hex[:6]}"
        db = SessionLocal()
        try:
            if not AccountCRUD.get_by_name(db, candidate):
                return candidate

            suffix = 2
            while True:
                new_candidate = f"{candidate}_{suffix}"
                if not AccountCRUD.get_by_name(db, new_candidate):
                    return new_candidate
                suffix += 1
        finally:
            db.close()
