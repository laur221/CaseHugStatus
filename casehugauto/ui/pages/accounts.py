import flet as ft
import logging
import threading
import time
from sqlalchemy import func
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD
from ...models.models import BotStatus, Skin
from ..components.steam_login_qr_dialog import SteamLoginQRDialog
from ...core.bot_runner import bot_runner

logger = logging.getLogger(__name__)


class AccountsPage:
    def __init__(self, app):
        self.app = app
        self.content = None
        self.accounts_list = None
        self._refresh_loop_started = False

    def build(self) -> ft.Container:
        """Build accounts page"""
        header = ft.Row(
            [
                ft.Text("Accounts", size=24, weight="bold"),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Add Account",
                            icon="add",
                            style=ft.ButtonStyle(
                                bgcolor="#1d3f5f",
                                color="#e8f6ff",
                                shape=ft.RoundedRectangleBorder(radius=10),
                            ),
                            on_click=self._show_add_account_dialog,
                        )
                    ],
                    spacing=10,
                ),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.accounts_list = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
            spacing=10,
        )

        self.content = ft.Column(
            [
                header,
                ft.Divider(),
                self.accounts_list,
            ],
            spacing=10,
            expand=True,
        )

        self.refresh_accounts()
        self._start_refresh_loop()

        return ft.Container(
            content=self.content,
            expand=True,
            padding=14,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=["#0d1628", "#101b31", "#0b1423"],
            ),
            border=ft.border.all(1, "#233854"),
            border_radius=14,
        )

    def _start_refresh_loop(self):
        """Refresh account cards periodically while this page is visible."""
        if self._refresh_loop_started:
            return
        self._refresh_loop_started = True

        def _loop():
            while True:
                try:
                    if getattr(self.app, "current_page", None) == self:
                        self.refresh_accounts()
                except Exception:
                    pass
                time.sleep(2.5)

        threading.Thread(target=_loop, daemon=True).start()

    def refresh_accounts(self):
        """Refresh accounts list"""
        db = None
        try:
            db = SessionLocal()
            accounts = AccountCRUD.get_all(db)

            skin_rows = (
                db.query(
                    Skin.account_id,
                    func.count(Skin.id).label("skins_count"),
                    func.coalesce(func.sum(Skin.estimated_price), 0.0).label("total_value"),
                )
                .group_by(Skin.account_id)
                .all()
            )
            skin_stats = {
                row.account_id: {
                    "skins_count": int(row.skins_count or 0),
                    "total_value": float(row.total_value or 0.0),
                }
                for row in skin_rows
            }
            skin_preview_rows = (
                db.query(Skin.account_id, Skin.skin_image_url)
                .filter(Skin.skin_image_url.isnot(None))
                .order_by(Skin.obtained_date.desc().nullslast(), Skin.created_at.desc(), Skin.id.desc())
                .all()
            )
            skin_preview_map = {}
            for row in skin_preview_rows:
                account_id = int(row.account_id or 0)
                image_url = str(row.skin_image_url or "").strip()
                if account_id <= 0 or not image_url:
                    continue
                if account_id in skin_preview_map:
                    continue
                skin_preview_map[account_id] = image_url

            status_rows = db.query(BotStatus).all()
            status_map = {row.account_id: row for row in status_rows if row.account_id is not None}

            if self.accounts_list:
                self.accounts_list.controls.clear()

                if not accounts:
                    self.accounts_list.controls.append(
                        ft.Container(
                            content=ft.Text(
                                "No accounts yet. Add one to get started!",
                                size=14,
                                color="#9aa7bd",
                            ),
                            padding=20,
                            alignment=ft.alignment.center,
                        )
                    )
                else:
                    for account in accounts:
                        self.accounts_list.controls.append(
                            self._create_account_card(account, skin_stats, status_map, skin_preview_map)
                        )

                try:
                    if hasattr(self.accounts_list, "page") and self.accounts_list.page:
                        self.accounts_list.update()
                except Exception as e:
                    logger.debug(f"Could not update accounts list: {e}")

        except Exception as exc:
            logger.error("Failed to load accounts page data: %s", exc, exc_info=True)
            if self.accounts_list:
                self.accounts_list.controls.clear()
                self.accounts_list.controls.append(self._create_database_help_card(str(exc)))
                try:
                    if hasattr(self.accounts_list, "page") and self.accounts_list.page:
                        self.accounts_list.update()
                except Exception:
                    pass
        finally:
            if db:
                db.close()

    def _open_database_settings(self, _=None):
        """Open DB settings page directly from accounts troubleshooting card."""
        try:
            if hasattr(self.app, "settings_page") and self.app.settings_page:
                self.app.settings_page._show_database_settings()
                self.app.current_page = self.app.settings_page
                return
            self.app.navigate_to("settings")
        except Exception as exc:
            logger.error("Could not open database settings from Accounts page: %s", exc)

    def _create_database_help_card(self, error_message: str) -> ft.Card:
        """Beginner-friendly troubleshooting card shown when DB connection fails."""
        preview = (error_message or "Unknown database error").strip()
        if len(preview) > 180:
            preview = f"{preview[:177]}..."

        return ft.Card(
            elevation=3,
            content=ft.Container(
                padding=20,
                border_radius=12,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#2c1a1a", "#1a1212"],
                ),
                border=ft.border.all(1, "#6a3232"),
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Icon(ft.icons.WARNING_AMBER, color="#ffb4b4"),
                                ft.Text(
                                    "Cannot load accounts: database is not connected",
                                    weight="bold",
                                    size=16,
                                    color="#ffd6d6",
                                ),
                            ],
                            spacing=10,
                        ),
                        ft.Text(
                            f"Technical error: {preview}",
                            size=12,
                            color="#ffb4b4",
                            selectable=True,
                        ),
                        ft.Divider(color="#6a3232"),
                        ft.Text("Quick setup guide", size=14, weight="bold", color="#e8f6ff"),
                        ft.Text(
                            "1. Open Settings -> Database Connection.",
                            size=12,
                            color="#cbd6e2",
                        ),
                        ft.Text(
                            "2. Click Configure PostgreSQL.",
                            size=12,
                            color="#cbd6e2",
                        ),
                        ft.Text(
                            "3. Fill Host, Port (usually 5432), Database, Username, Password.",
                            size=12,
                            color="#cbd6e2",
                        ),
                        ft.Text(
                            "4. Click Connect and wait for 'Connection successful'.",
                            size=12,
                            color="#cbd6e2",
                        ),
                        ft.Text(
                            "5. Return to Accounts and click Retry.",
                            size=12,
                            color="#cbd6e2",
                        ),
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Open Database Settings",
                                    icon=ft.icons.SETTINGS,
                                    style=ft.ButtonStyle(
                                        bgcolor="#1d3f5f",
                                        color="#e8f6ff",
                                        shape=ft.RoundedRectangleBorder(radius=10),
                                    ),
                                    on_click=self._open_database_settings,
                                ),
                                ft.OutlinedButton(
                                    "Retry",
                                    icon=ft.icons.REFRESH,
                                    on_click=lambda _: self.refresh_accounts(),
                                ),
                            ],
                            spacing=10,
                        ),
                    ],
                    spacing=8,
                ),
            ),
        )

    def _create_account_card(self, account, skin_stats: dict, status_map: dict, skin_preview_map: dict) -> ft.Card:
        """Create account card"""
        stats = skin_stats.get(account.id, {"skins_count": 0, "total_value": 0.0})
        skins_count = int(stats["skins_count"])
        total_value = float(stats["total_value"])
        bot_status = status_map.get(account.id)
        stored_cases_opened = int(getattr(bot_status, "cases_opened_total", 0) or 0)
        cases_opened_total = max(stored_cases_opened, skins_count)
        last_check = getattr(bot_status, "last_case_check_at", None)
        last_open = getattr(bot_status, "last_cases_opened_at", None)
        is_running = bot_runner.is_running(account.id)

        def _fmt_ts(value):
            if not value:
                return "-"
            try:
                return value.strftime("%Y-%m-%d %H:%M:%S")
            except Exception:
                return str(value)

        avatar_src = str((account.steam_avatar_url or "").strip() or (skin_preview_map.get(account.id) or "")).strip()
        account_initial = ((account.account_name or "?").strip()[:1] or "?").upper()
        if avatar_src:
            avatar = ft.Container(
                width=84,
                height=84,
                border_radius=12,
                clip_behavior=ft.ClipBehavior.ANTI_ALIAS,
                bgcolor="#1a2537",
                content=ft.Image(
                    src=avatar_src,
                    fit=ft.ImageFit.CONTAIN,
                    width=84,
                    height=84,
                ),
            )
        else:
            avatar = ft.Container(
                width=84,
                height=84,
                border_radius=42,
                bgcolor="#2b3a52",
                alignment=ft.alignment.center,
                content=ft.Text(account_initial, color="white", weight="bold", size=24),
            )

        account_info = ft.Column(
            [
                ft.Text(account.account_name, size=16, weight="bold"),
                ft.Text(account.steam_nickname or "Not logged in", size=12, color="#9aa7bd"),
                ft.Text(
                    f"Profile: {account.browser_profile_path or 'pending'}",
                    size=11,
                    color="#7f8da6",
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    f"Skins: {skins_count} | Cases: {cases_opened_total} | Value: ${total_value:.2f}",
                    size=11,
                    color="#7f8da6",
                ),
                ft.Text(
                    f"Last check: {_fmt_ts(last_check)} | Last open: {_fmt_ts(last_open)}",
                    size=11,
                    color="#7f8da6",
                ),
            ],
            spacing=5,
            expand=True,
        )

        actions = ft.Row(
            [
                ft.IconButton(
                    "stop" if is_running else "play_arrow",
                    tooltip="Stop Bot" if is_running else "Run Bot",
                    icon_color="#ff7676" if is_running else "#78d8ff",
                    style=ft.ButtonStyle(bgcolor="#1a2537"),
                    on_click=lambda _: self._toggle_bot(account),
                ),
                ft.IconButton(
                    "delete",
                    tooltip="Delete Account",
                    icon_color="#aeb9cb",
                    style=ft.ButtonStyle(bgcolor="#1a2537"),
                    on_click=lambda _: self._delete_account(account),
                ),
            ],
            spacing=5,
        )

        return ft.Card(
            elevation=3,
            content=ft.Container(
                content=ft.Row(
                    [avatar, account_info, actions],
                    spacing=15,
                    expand=True,
                ),
                padding=15,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#142238", "#101c2f"],
                ),
                border=ft.border.all(1, "#2a4363"),
                border_radius=12,
            ),
            margin=ft.margin.only(bottom=10),
        )

    def _show_add_account_dialog(self, e):
        """Show Steam login dialog for adding new account"""

        def on_account_added(account):
            """Callback when account is successfully added"""
            self.refresh_accounts()
            if hasattr(self.app, "page"):
                self.app.page.snack_bar = ft.SnackBar(
                    ft.Text(f"✓ Account '{account.account_name}' added successfully!")
                )
                self.app.page.snack_bar.open = True
                self.app.page.update()

        steam_dialog = SteamLoginQRDialog(self.app, on_success=on_account_added)
        steam_dialog.show()

    def _close_dialog(self, dlg):
        dlg.open = False
        self.app.main_area.page.update()

    def _run_bot(self, account):
        """Run bot for account"""
        print(f"Running bot for {account.account_name}")

    def _toggle_bot(self, account):
        """Start/stop bot for an account"""
        if bot_runner.is_running(account.id):
            ok, message = bot_runner.stop_account(account.id)
            snack_msg = (
                f"⏹️ {account.account_name}: {message}"
                if ok
                else f"⚠️ {account.account_name}: {message}"
            )
        else:
            ok, message = bot_runner.start_account(account.id)
            snack_msg = (
                f"▶️ {account.account_name}: {message}"
                if ok
                else f"⚠️ {account.account_name}: {message}"
            )

        self.app.main_area.page.snack_bar = ft.SnackBar(ft.Text(snack_msg))
        self.app.main_area.page.snack_bar.open = True

        self.refresh_accounts()
        self.app.main_area.page.update()

    def _delete_account(self, account):
        """Delete account with confirmation"""

        def confirm_delete(_):
            db = SessionLocal()
            try:
                AccountCRUD.delete(db, account.id)
                self.refresh_accounts()
                self.app.main_area.content.update()
            finally:
                db.close()

            dlg.open = False
            self.app.main_area.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Delete Account"),
            content=ft.Text(f"Are you sure you want to delete '{account.account_name}'?"),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._close_dialog(dlg)),
                ft.TextButton("Delete", on_click=confirm_delete),
            ],
        )

        self.app.main_area.page.dialog = dlg
        dlg.open = True
        self.app.main_area.page.update()
