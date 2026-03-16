import flet as ft
from sqlalchemy import func
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD
from ...models.models import BotStatus, Skin
import threading
import time
import logging

logger = logging.getLogger(__name__)


class HomePage:
    def __init__(self, app):
        self.app = app
        self.content = None
        self.stats_row = None
        self._stats_refresh_started = False
        self._stats_snapshot = None

    def _fetch_stats_snapshot(self):
        """Fetch dashboard counters from database."""
        db = SessionLocal()
        try:
            accounts = AccountCRUD.get_all(db)
            total_accounts = len(accounts)
            active_accounts = len(AccountCRUD.get_active(db))

            total_value = (
                db.query(func.coalesce(func.sum(Skin.estimated_price), 0.0)).scalar() or 0.0
            )
            total_cases = (
                db.query(func.coalesce(func.sum(BotStatus.cases_opened_total), 0)).scalar() or 0
            )

            return (
                total_accounts,
                active_accounts,
                round(float(total_value), 2),
                int(total_cases),
            )
        finally:
            db.close()

    def _refresh_stats(self, update_ui: bool = True):
        """Refresh stat cards from DB values."""
        try:
            stats_snapshot = self._fetch_stats_snapshot()
            if stats_snapshot == self._stats_snapshot:
                return
            self._stats_snapshot = stats_snapshot

            total_accounts, active_accounts, total_value, total_cases = stats_snapshot
            if not self.stats_row:
                return

            self.stats_row.controls.clear()
            self.stats_row.controls.extend([
                self._create_stat_card("Total Accounts", str(total_accounts), "group"),
                self._create_stat_card("Active Accounts", str(active_accounts), "check_circle"),
                self._create_stat_card("Total Value", f"${float(total_value):.2f}", "trending_up"),
                self._create_stat_card("Cases Opened", str(total_cases), "card_giftcard"),
            ])

            if update_ui and getattr(self.stats_row, "page", None):
                self.stats_row.update()
                if hasattr(self.app, "page"):
                    self.app.page.update()
        except Exception as e:
            logger.debug(f"Could not refresh home stats: {e}")

    def _start_stats_refresh_loop(self):
        """Refresh dashboard stats periodically from DB."""
        if self._stats_refresh_started:
            return

        self._stats_refresh_started = True

        def _loop():
            while True:
                try:
                    if getattr(self.app, "current_page", None) == self:
                        self._refresh_stats(update_ui=True)
                except Exception:
                    pass
                time.sleep(2.5)

        threading.Thread(target=_loop, daemon=True).start()

    def build(self) -> ft.Container:
        """Build home page - non-blocking"""
        self._stats_snapshot = None

        self.stats_row = ft.Row(
            [
                self._create_stat_card("Total Accounts", "0", "group"),
                self._create_stat_card("Active Accounts", "0", "check_circle"),
                self._create_stat_card("Total Value", "$0.00", "trending_up"),
                self._create_stat_card("Cases Opened", "0", "card_giftcard"),
            ],
            spacing=14,
            run_spacing=14,
            wrap=True,
        )

        welcome = ft.Text(
            "Welcome to CaseHugAuto",
            size=34,
            weight="bold",
            color="#8be9ff",
        )

        description = ft.Text(
            "Automate your case opening process on casehug.com. Manage multiple accounts and track your skins.",
            size=14,
            color="#9aa7bd",
        )

        button_style = ft.ButtonStyle(
            bgcolor="#1d3f5f",
            color="#e8f6ff",
            shape=ft.RoundedRectangleBorder(radius=10),
            padding=ft.padding.symmetric(horizontal=18, vertical=14),
        )

        quick_actions = ft.Row(
            [
                ft.ElevatedButton(
                    "Add Account",
                    icon="add",
                    style=button_style,
                    on_click=lambda _: self.app.navigate_to("accounts"),
                ),
                ft.ElevatedButton(
                    "View Skins",
                    icon="collections",
                    style=button_style,
                    on_click=lambda _: self.app.navigate_to("skins"),
                ),
                ft.ElevatedButton(
                    "Settings",
                    icon="settings",
                    style=button_style,
                    on_click=lambda _: self.app.navigate_to("settings"),
                ),
            ],
            spacing=10,
            wrap=True,
        )

        self.content = ft.Column(
            [
                welcome,
                description,
                ft.Divider(height=18, color="transparent"),
                self.stats_row,
                ft.Divider(height=18, color="transparent"),
                quick_actions,
            ],
            spacing=12,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
            scroll=ft.ScrollMode.AUTO,
        )

        container = ft.Container(
            content=self.content,
            expand=True,
            padding=ft.padding.all(18),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=["#0d1628", "#101b31", "#0b1423"],
            ),
            border=ft.border.all(1, "#233854"),
            border_radius=14,
        )

        self._refresh_stats(update_ui=False)
        self._start_stats_refresh_loop()

        return container

    def _create_stat_card(self, title: str, value: str, icon_name: str) -> ft.Card:
        """Create stat card"""
        return ft.Card(
            elevation=3,
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(icon_name, size=30, color="#7ed8ff"),
                        ft.Text(title, size=12, color="#9aa7bd"),
                        ft.Text(value, size=21, weight="bold", color="white"),
                    ],
                    spacing=9,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=18,
                width=245,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#142238", "#101c2f"],
                ),
                border=ft.border.all(1, "#2a4363"),
                border_radius=12,
            ),
        )
