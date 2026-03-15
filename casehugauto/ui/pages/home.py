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
                db.query(func.coalesce(func.sum(Skin.estimated_price), 0.0))
                .scalar()
                or 0.0
            )
            total_cases = (
                db.query(func.coalesce(func.sum(BotStatus.cases_opened_total), 0))
                .scalar()
                or 0
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
        # Create stats cards with initial empty data
        self.stats_row = ft.Row(
            [
                self._create_stat_card("Total Accounts", "0", "group"),
                self._create_stat_card("Active Accounts", "0", "check_circle"),
                self._create_stat_card("Total Value", "$0.00", "trending_up"),
                self._create_stat_card("Cases Opened", "0", "card_giftcard"),
            ],
            spacing=15,
            wrap=True,
        )
        
        # Welcome message
        welcome = ft.Text(
            "Welcome to CaseHugAuto",
            size=32,
            weight="bold",
            color="#00d4ff",
        )
        
        description = ft.Text(
            "Automate your case opening process on casehug.com. Manage multiple accounts and track your skins.",
            size=14,
            color="#888888",
        )
        
        # Quick actions
        quick_actions = ft.Row(
            [
                ft.ElevatedButton(
                    "Add Account",
                    icon="add",
                    on_click=lambda _: self.app.navigate_to("accounts"),
                ),
                ft.ElevatedButton(
                    "View Skins",
                    icon="collections",
                    on_click=lambda _: self.app.navigate_to("skins"),
                ),
                ft.ElevatedButton(
                    "Settings",
                    icon="settings",
                    on_click=lambda _: self.app.navigate_to("settings"),
                ),
            ],
            spacing=10,
        )
        
        self.content = ft.Column(
            [
                welcome,
                description,
                ft.Divider(height=20, color="transparent"),
                self.stats_row,
                ft.Divider(height=20, color="transparent"),
                quick_actions,
            ],
            spacing=15,
            alignment=ft.MainAxisAlignment.START,
            horizontal_alignment=ft.CrossAxisAlignment.START,
        )
        
        # Construct container
        container = ft.Container(
            content=self.content,
            expand=True,
            padding=ft.padding.all(20),
        )
        
        # Initial load and periodic refresh.
        self._refresh_stats(update_ui=False)
        self._start_stats_refresh_loop()

        return container
    
    def _create_stat_card(self, title: str, value: str, icon_name: str) -> ft.Card:
        """Create stat card"""
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(icon_name, size=30, color="#00d4ff"),
                        ft.Text(title, size=12, color="#888888"),
                        ft.Text(value, size=20, weight="bold", color="white"),
                    ],
                    spacing=10,
                    alignment=ft.MainAxisAlignment.CENTER,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=20,
                width=250,
                bgcolor="#1a1a1a",
            ),
        )
