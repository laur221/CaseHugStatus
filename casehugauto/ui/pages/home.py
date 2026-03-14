import flet as ft
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD, BotStatusCRUD
import threading


class HomePage:
    def __init__(self, app):
        self.app = app
        self.content = None
        self.stats_row = None
        self.activity_log = None
        
    def _load_stats_async(self):
        """Load stats in background thread"""
        try:
            db = SessionLocal()
            try:
                accounts = AccountCRUD.get_all(db)
                total_accounts = len(accounts)
                active_accounts = len(AccountCRUD.get_active(db))
                
                total_value = 0
                total_cases = 0
                for account in accounts:
                    try:
                        bot_status = BotStatusCRUD.get_or_create(db, account.id)
                        total_value += bot_status.total_value_obtained
                        total_cases += bot_status.cases_opened_total
                    except Exception:
                        pass
                
                # Update UI with stats
                if self.stats_row and hasattr(self.app, 'page'):
                    self.stats_row.controls.clear()
                    self.stats_row.controls.extend([
                        self._create_stat_card("Total Accounts", str(total_accounts), "group"),
                        self._create_stat_card("Active Accounts", str(active_accounts), "check_circle"),
                        self._create_stat_card("Total Value", f"${total_value:.2f}", "trending_up"),
                        self._create_stat_card("Cases Opened", str(total_cases), "card_giftcard"),
                    ])
                    self.app.page.update()
            finally:
                db.close()
        except Exception as e:
            pass  # Silently fail
    
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

        self.activity_log = ft.ListView(
            spacing=4,
            auto_scroll=True,
            height=180,
        )

        activity_panel = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Live Activity", size=16, weight="bold"),
                        ft.Text(
                            "Runtime events from bot and Steam login sessions.",
                            size=12,
                            color="#8f8f8f",
                        ),
                        self.activity_log,
                    ],
                    spacing=8,
                ),
                padding=14,
                bgcolor="#1a1a1a",
            )
        )
        
        self.content = ft.Column(
            [
                welcome,
                description,
                ft.Divider(height=20, color="transparent"),
                self.stats_row,
                ft.Divider(height=20, color="transparent"),
                quick_actions,
                ft.Divider(height=10, color="transparent"),
                activity_panel,
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
        
        # Load stats in background thread
        stats_thread = threading.Thread(target=self._load_stats_async, daemon=True)
        stats_thread.start()
        self.refresh_activity_log(update_page=False)

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

    def _event_color(self, level: str) -> str:
        normalized = (level or "").lower()
        if normalized in {"error", "failed", "fatal"}:
            return "#ff8787"
        if normalized in {"success", "started", "running"}:
            return "#69db7c"
        if normalized in {"warning", "stopped"}:
            return "#fcc419"
        return "#9ad1ff"

    def refresh_activity_log(self, update_page: bool = True):
        if not self.activity_log:
            return

        events = self.app.get_recent_events(25) if hasattr(self.app, "get_recent_events") else []
        self.activity_log.controls.clear()

        if not events:
            self.activity_log.controls.append(
                ft.Text("No activity yet.", size=12, color="#8f8f8f")
            )
        else:
            for event in events:
                timestamp = event.get("time", "--:--:--")
                message = event.get("message", "")
                level = event.get("level", "info")
                self.activity_log.controls.append(
                    ft.Text(
                        f"[{timestamp}] {message}",
                        size=12,
                        color=self._event_color(level),
                    )
                )

        if update_page and hasattr(self.app, "page") and self.app.page:
            self.app.page.update()
