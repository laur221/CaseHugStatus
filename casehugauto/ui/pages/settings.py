import flet as ft
from ..components.database_connection import DatabaseSettingsPage
from ...core.bot_runner import bot_runner


class SettingsPage:
    def __init__(self, app):
        self.app = app
        self.content = None
        
    def build(self) -> ft.Container:
        """Build settings page"""
        
        settings_items = [
            self._create_setting_item(
                "Database Connection",
                "Configure PostgreSQL connection",
                "database",
                lambda _: self._show_database_settings(),
            ),
            self._create_setting_item(
                "Bot Configuration",
                "Set bot execution schedule and parameters",
                "settings_automation",
                lambda _: self._show_bot_settings(),
            ),
            self._create_setting_item(
                "Notifications",
                "Configure Telegram and other notifications",
                "notifications",
                lambda _: self._show_notifications_settings(),
            ),
            self._create_setting_item(
                "Appearance",
                "Change theme and display settings",
                "palette",
                lambda _: self._show_appearance_settings(),
            ),
            self._create_setting_item(
                "About",
                "About CaseHugAuto",
                "info",
                lambda _: self._show_about(),
            ),
        ]
        
        self.content = ft.Column(
            [
                ft.Text("Settings", size=24, weight="bold"),
                ft.Divider(),
                ft.Column(settings_items, spacing=5, expand=True),
            ],
            spacing=15,
            expand=True,
        )
        
        return ft.Container(
            content=self.content,
            expand=True,
            padding=10,
        )
    
    def _create_setting_item(self, title: str, subtitle: str, icon, on_click) -> ft.Card:
        """Create setting item card"""
        return ft.Card(
            content=ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(icon),
                    title=ft.Text(title, weight="bold"),
                    subtitle=ft.Text(subtitle, size=12, color="#888888"),
                    on_click=on_click,
                ),
                bgcolor="#1a1a1a",
                padding=10,
            ),
            margin=ft.margin.only(bottom=5),
        )
    
    def _show_database_settings(self):
        """Show database settings page"""
        db_settings = DatabaseSettingsPage(self.app)
        self.app.main_area.content = db_settings.build()
        self.app.main_area.update()
    
    def _show_bot_settings(self):
        """Show bot settings dialog"""
        current_cfg = bot_runner.get_config()

        auto_start_cb = ft.Checkbox(
            label="Auto-run bot for new accounts",
            value=current_cfg.get("auto_start_new_accounts", False),
        )
        interval_field = ft.TextField(
            label="Heartbeat interval (seconds)",
            value=str(current_cfg.get("case_open_interval_seconds", 60)),
        )
        retries_field = ft.TextField(
            label="Max retries",
            value=str(current_cfg.get("max_retries", 3)),
        )

        def save_settings(_):
            ok, message = bot_runner.update_config(
                {
                    "auto_start_new_accounts": bool(auto_start_cb.value),
                    "case_open_interval_seconds": interval_field.value,
                    "max_retries": retries_field.value,
                }
            )

            dlg.open = False
            self.app.main_area.page.dialog = None
            self.app.main_area.page.snack_bar = ft.SnackBar(
                ft.Text(("✅ " if ok else "⚠️ ") + message)
            )
            self.app.main_area.page.snack_bar.open = True
            self.app.main_area.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Bot Configuration"),
            content=ft.Column([
                auto_start_cb,
                interval_field,
                retries_field,
            ]),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._close_dialog(dlg)),
                ft.TextButton("Save", on_click=save_settings),
            ],
        )
        
        self.app.main_area.page.dialog = dlg
        dlg.open = True
        self.app.main_area.page.update()

    def _close_dialog(self, dlg):
        dlg.open = False
        self.app.main_area.page.dialog = None
        self.app.main_area.page.update()
    
    def _show_notifications_settings(self):
        """Show notifications settings"""
        dlg = ft.AlertDialog(
            title=ft.Text("Notifications"),
            content=ft.Column([
                ft.TextField(label="Telegram Bot Token", password=True),
                ft.TextField(label="Telegram Chat ID"),
                ft.Checkbox(label="Notify on skin obtained", value=True),
                ft.Checkbox(label="Notify on error", value=True),
            ]),
            actions=[
                ft.TextButton("Cancel"),
                ft.TextButton("Save"),
            ],
        )
        
        self.app.main_area.page.dialog = dlg
        dlg.open = True
        self.app.main_area.page.update()
    
    def _show_appearance_settings(self):
        """Show appearance settings"""
        dlg = ft.AlertDialog(
            title=ft.Text("Appearance"),
            content=ft.Column([
                ft.Dropdown(
                    label="Theme",
                    options=[
                        ft.dropdown.Option("Dark"),
                        ft.dropdown.Option("Light"),
                    ],
                    value="Dark",
                ),
            ]),
            actions=[
                ft.TextButton("Cancel"),
                ft.TextButton("Save"),
            ],
        )
        
        self.app.main_area.page.dialog = dlg
        dlg.open = True
        self.app.main_area.page.update()
    
    def _show_about(self):
        """Show about dialog"""
        dlg = ft.AlertDialog(
            title=ft.Text("About CaseHugAuto"),
            content=ft.Column([
                ft.Text("CaseHugAuto v1.0.0", weight="bold"),
                ft.Text("Automate your case opening on casehug.com", color="#888888"),
                ft.Divider(),
                ft.Text("Features:", weight="bold"),
                ft.Text("• Multi-account management", size=12),
                ft.Text("• Automated case opening", size=12),
                ft.Text("• Skin tracking and statistics", size=12),
                ft.Text("• PostgreSQL database", size=12),
            ], spacing=5),
            actions=[
                ft.TextButton("OK"),
            ],
        )
        
        self.app.main_area.page.dialog = dlg
        dlg.open = True
        self.app.main_area.page.update()
