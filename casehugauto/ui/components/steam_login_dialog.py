"""Steam login dialog for existing accounts using persistent profiles."""

from __future__ import annotations

from datetime import datetime
import logging
import os
import threading

import flet as ft

from ...core.steam_login_launcher import steam_login_launcher
from ...database.crud import AccountCRUD, LoginSessionCRUD
from ...database.db import SessionLocal

logger = logging.getLogger(__name__)


class SteamLoginDialog:
    """Interactive Steam login dialog for an existing account."""

    def __init__(self, app, account=None):
        self.app = app
        self.account = account
        self.dlg = None
        self.status_text = None
        self.username_field = None
        self.password_field = None
        self.use_qr_checkbox = None
        self.background_checkbox = None
        self.session_id = None
        self._is_busy = False

    def _page(self):
        if hasattr(self.app, "page") and self.app.page:
            return self.app.page
        return self.app.main_area.page

    def show(self):
        if not self.account:
            return

        db = SessionLocal()
        try:
            account = AccountCRUD.get_by_id(db, self.account.id)
            if account:
                self.account = account
        finally:
            db.close()

        self.status_text = ft.Text(
            "Start hidden login session, approve Steam Guard if needed, then confirm session.",
            size=12,
            color="#888888",
        )
        self.username_field = ft.TextField(
            label="Steam Username or Email",
            value=self.account.steam_username or "",
            width=420,
        )
        self.password_field = ft.TextField(
            label="Password (used only for autofill)",
            password=True,
            can_reveal_password=True,
            width=420,
        )
        self.use_qr_checkbox = ft.Checkbox(
            label="Use Steam QR login instead of password submit (disabled in hidden mode)",
            value=False,
            disabled=True,
        )
        self.background_checkbox = ft.Checkbox(
            label="Background mode is always enabled (no visible window)",
            value=True,
            disabled=True,
        )

        profile_path = self.account.browser_profile_path or ""

        def start_login(_):
            if self._is_busy:
                return
            username = (self.username_field.value or "").strip()
            password = self.password_field.value or ""
            prefer_qr = False
            run_in_background = True

            if not username or not password:
                self._set_status("Username and password are required.", "error")
                return

            self._is_busy = True
            self._set_status("Launching Steam login browser...", "info")

            def run():
                db = SessionLocal()
                try:
                    account = AccountCRUD.get_by_id(db, self.account.id)
                    if not account:
                        self._set_status("Account no longer exists.", "error")
                        return

                    if username:
                        account.steam_username = username
                        db.commit()
                        db.refresh(account)

                    AccountCRUD.ensure_profile_path(db, account)
                    session = LoginSessionCRUD.create(db, account.id)
                    LoginSessionCRUD.update_status(db, session.id, "in_progress")
                    self.session_id = session.id
                    self.account = account

                    ok, message = steam_login_launcher.start(
                        account_id=account.id,
                        profile_path=account.browser_profile_path or "",
                        steam_username=username,
                        steam_password=password,
                        prefer_qr=prefer_qr,
                        run_in_background=run_in_background,
                    )
                    self.password_field.value = ""
                    self._set_status(message, "success" if ok else "error")
                except Exception as exc:
                    logger.error("Failed to start Steam login for existing account: %s", exc, exc_info=True)
                    self._set_status(f"Could not start login flow: {exc}", "error")
                finally:
                    db.close()
                    self._is_busy = False
                    self._page().update()

            threading.Thread(target=run, daemon=True).start()

        def complete_login(_):
            if not self.session_id:
                self._set_status("Start browser login first.", "error")
                return

            ok, message, cookies = steam_login_launcher.complete(self.account.id, close_browser=False)
            if not ok:
                self._set_status(message, "error")
                return

            db = SessionLocal()
            try:
                account = AccountCRUD.get_by_id(db, self.account.id)
                if account:
                    if cookies:
                        AccountCRUD.update_cookies(db, account.id, cookies)
                    if self.username_field.value:
                        account.steam_username = self.username_field.value.strip()
                    account.last_login = datetime.utcnow()
                    db.commit()
                    db.refresh(account)
                    self.account = account

                LoginSessionCRUD.update_status(db, self.session_id, "completed")
                self._set_status("Session saved for this profile.", "success")

                self.dlg.open = False
                self._page().snack_bar = ft.SnackBar(
                    ft.Text(f"Steam session updated for '{self.account.account_name}'.")
                )
                self._page().snack_bar.open = True
                self._page().update()
            except Exception as exc:
                logger.error("Could not finalize Steam login session: %s", exc, exc_info=True)
                self._set_status(f"Could not save session: {exc}", "error")
            finally:
                db.close()

        def close_browser(_):
            steam_login_launcher.close(self.account.id)
            self._set_status("Login browser closed.", "info")

        def open_profile_folder(_):
            try:
                if profile_path:
                    os.startfile(profile_path)
                    self._set_status("Profile folder opened.", "info")
            except Exception as exc:
                self._set_status(f"Could not open profile folder: {exc}", "error")

        def on_cancel(_):
            self.dlg.open = False
            self._page().update()

        self.dlg = ft.AlertDialog(
            title=ft.Text(f"Steam Session - {self.account.account_name}"),
            content=ft.Column(
                [
                    self.status_text,
                    ft.TextField(
                        label="Profile path",
                        value=profile_path,
                        read_only=True,
                        width=420,
                    ),
                    self.username_field,
                    self.password_field,
                    self.use_qr_checkbox,
                    self.background_checkbox,
                ],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
                width=460,
            ),
            actions=[
                ft.TextButton("Open Profile Folder", on_click=open_profile_folder),
                ft.TextButton("Close Browser", on_click=close_browser),
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton("Start Browser Login", on_click=start_login),
                ft.ElevatedButton("Session Completed", on_click=complete_login),
            ],
            modal=True,
        )

        self._page().dialog = self.dlg
        self.dlg.open = True
        self._page().update()

    def _set_status(self, message: str, status: str):
        if not self.status_text:
            return

        color_map = {
            "info": "#00d4ff",
            "success": "#51cf66",
            "error": "#ff6b6b",
        }
        self.status_text.value = message
        self.status_text.color = color_map.get(status, "#888888")
