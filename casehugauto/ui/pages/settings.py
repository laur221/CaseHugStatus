from pathlib import Path

import flet as ft

from ..components.database_connection import DatabaseSettingsPage
from ...core.bot_runner import bot_runner
from ...core.data_paths import apply_data_dir_change, current_data_dir
from ...core.profile_store import apply_profile_root_change, resolve_profile_root
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD
from ...core.windows_startup import is_windows_platform


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
                ft.icons.STORAGE,
                lambda _: self._show_database_settings(),
            ),
            self._create_setting_item(
                "Bot Configuration",
                "Set bot execution schedule and parameters",
                ft.icons.SETTINGS,
                lambda _: self._show_bot_settings(),
            ),
            self._create_setting_item(
                "Notifications",
                "Configure Telegram and other notifications",
                ft.icons.NOTIFICATIONS,
                lambda _: self._show_notifications_settings(),
            ),
            self._create_setting_item(
                "About",
                "About CaseHugAuto",
                ft.icons.INFO,
                lambda _: self._show_about(),
            ),
        ]

        self.content = ft.Column(
            [
                ft.Text("Settings", size=24, weight="bold"),
                ft.Divider(),
                ft.Column(settings_items, spacing=8, expand=True, scroll=ft.ScrollMode.AUTO),
            ],
            spacing=15,
            expand=True,
        )

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

    def _create_setting_item(self, title: str, subtitle: str, icon, on_click) -> ft.Card:
        """Create setting item card"""
        return ft.Card(
            elevation=2,
            content=ft.Container(
                content=ft.ListTile(
                    leading=ft.Icon(icon, color="#7ed8ff"),
                    title=ft.Text(title, weight="bold"),
                    subtitle=ft.Text(subtitle, size=12, color="#9aa7bd"),
                    on_click=on_click,
                ),
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#142238", "#101c2f"],
                ),
                border=ft.border.all(1, "#2a4363"),
                border_radius=12,
                padding=10,
            ),
            margin=ft.margin.only(bottom=5),
        )

    def _show_database_settings(self):
        """Show database settings page"""
        db_settings = DatabaseSettingsPage(self.app)
        content = db_settings.build()
        if hasattr(self.app, "show_custom_content"):
            self.app.show_custom_content(content)
        else:
            self.app.main_area.content = content
            self.app.main_area.update()

    def _show_bot_settings(self):
        """Show bot settings dialog"""
        current_cfg = bot_runner.get_config()
        interval_seconds = int(current_cfg.get("case_open_interval_seconds", 60) or 60)
        interval_minutes = max(1, int(round(interval_seconds / 60)))
        startup_supported = is_windows_platform()
        startup_enabled = bot_runner.get_windows_startup_state() if startup_supported else False
        current_data_dir_path = current_data_dir()
        current_profile_root = resolve_profile_root()

        auto_start_cb = ft.Checkbox(
            label="Auto-run bot for new accounts",
            value=current_cfg.get("auto_start_new_accounts", False),
        )
        auto_start_on_launch_cb = ft.Checkbox(
            label="Auto-run bot for active accounts when app starts",
            value=current_cfg.get("auto_start_active_accounts_on_launch", False),
        )
        windows_startup_cb = ft.Checkbox(
            label="Start headless background worker with Windows",
            value=startup_enabled,
            disabled=not startup_supported,
        )
        picker_target = {"field": None}

        def _on_folder_picked(e: ft.FilePickerResultEvent):
            selected = str(getattr(e, "path", "") or "").strip()
            if not selected:
                return

            target = picker_target.get("field")
            if target == "data":
                data_dir_field.value = selected
                data_dir_field.update()
            elif target == "profiles":
                profiles_dir_field.value = selected
                profiles_dir_field.update()

        page = self.app.main_area.page
        folder_picker = getattr(self, "_folder_picker", None)
        if folder_picker is None:
            folder_picker = ft.FilePicker(on_result=_on_folder_picked)
            self._folder_picker = folder_picker
            page.overlay.append(folder_picker)
            page.update()
        else:
            folder_picker.on_result = _on_folder_picked
        startup_hint = ft.Text(
            "Background mode runs without UI and opens cases automatically after cooldown.",
            size=11,
            color="#7f8da6",
        )
        data_dir_field = ft.TextField(
            label="Data folder (profiles, logs, local config)",
            value=str(current_data_dir_path),
            hint_text="Example: D:/CaseHugAutoData",
            expand=True,
        )
        data_dir_browse_btn = ft.OutlinedButton(
            "Browse...",
            icon=ft.icons.FOLDER_OPEN,
            on_click=lambda _: _open_folder_picker("data"),
        )
        data_dir_hint = ft.Text(
            "When changed, local app data is copied to the new folder. Restart app after saving.",
            size=11,
            color="#7f8da6",
        )
        profiles_dir_field = ft.TextField(
            label="Profiles folder (browser sessions only)",
            value=str(current_profile_root),
            hint_text="Example: E:/CaseHugAutoProfiles",
            expand=True,
        )
        profiles_dir_browse_btn = ft.OutlinedButton(
            "Browse...",
            icon=ft.icons.FOLDER_OPEN,
            on_click=lambda _: _open_folder_picker("profiles"),
        )
        profiles_dir_hint = ft.Text(
            "Use this when C disk is low. Existing profile folders are copied to the new location.",
            size=11,
            color="#7f8da6",
        )

        def _open_folder_picker(target: str):
            picker_target["field"] = target
            folder_picker.get_directory_path(dialog_title="Select folder")
        interval_field = ft.TextField(
            label="Cooldown check interval (minutes)",
            value=str(interval_minutes),
            hint_text="Example: 10 = 10 minutes",
        )
        retries_field = ft.TextField(
            label="Max retries",
            value=str(current_cfg.get("max_retries", 3)),
        )
        steam_login_retries_field = ft.TextField(
            label="Steam login retries",
            value=str(current_cfg.get("steam_login_max_retries", 1)),
            hint_text="0 = single login attempt",
        )

        def save_settings(_):
            try:
                minutes_value = int(float(str(interval_field.value or "").strip()))
            except Exception:
                minutes_value = 1
            minutes_value = max(1, minutes_value)

            try:
                steam_login_retries = int(float(str(steam_login_retries_field.value or "").strip()))
            except Exception:
                steam_login_retries = 1
            steam_login_retries = max(0, steam_login_retries)

            ok, message = bot_runner.update_config(
                {
                    "auto_start_new_accounts": bool(auto_start_cb.value),
                    "auto_start_active_accounts_on_launch": bool(auto_start_on_launch_cb.value),
                    "start_with_windows_headless": (
                        bool(windows_startup_cb.value)
                        if startup_supported
                        else bool(current_cfg.get("start_with_windows_headless", False))
                    ),
                    "case_open_interval_seconds": minutes_value * 60,
                    "max_retries": retries_field.value,
                    "steam_login_max_retries": steam_login_retries,
                }
            )
            if not ok:
                self.app.main_area.page.snack_bar = ft.SnackBar(ft.Text(f"⚠️ {message}"))
                self.app.main_area.page.snack_bar.open = True
                self.app.main_area.page.update()
                return

            info_messages = [message]
            data_dir_changed = False
            profile_root_changed = False

            def _sync_account_profile_paths():
                db = SessionLocal()
                try:
                    changed_profiles = AccountCRUD.rebind_profile_paths(db)
                    if changed_profiles > 0:
                        info_messages.append(
                            f"Updated browser profile paths for {changed_profiles} account(s)."
                        )
                except Exception as exc:
                    info_messages.append(f"Profile path sync warning: {exc}")
                finally:
                    db.close()

            requested_dir = str(data_dir_field.value or "").strip()
            if requested_dir:
                try:
                    changed_data_dir = str(current_data_dir_path.resolve()) != str(
                        Path(requested_dir).expanduser().resolve()
                    )
                except Exception:
                    changed_data_dir = False

                if changed_data_dir:
                    ok_dir, msg_dir, _ = apply_data_dir_change(
                        requested_dir,
                        source_dir=current_data_dir_path,
                    )
                    if not ok_dir:
                        self.app.main_area.page.snack_bar = ft.SnackBar(ft.Text(f"⚠️ {msg_dir}"))
                        self.app.main_area.page.snack_bar.open = True
                        self.app.main_area.page.update()
                        return

                    data_dir_changed = True
                    info_messages.append(msg_dir)
                    if startup_supported and bool(windows_startup_cb.value):
                        # Regenerate startup script to include latest data-dir context.
                        ok_start, startup_msg = bot_runner.configure_windows_startup(True, persist=False)
                        if not ok_start:
                            info_messages.append(f"Startup script warning: {startup_msg}")

            requested_profiles_dir = str(profiles_dir_field.value or "").strip()
            if requested_profiles_dir:
                try:
                    changed_profile_root = str(current_profile_root.resolve()) != str(
                        Path(requested_profiles_dir).expanduser().resolve()
                    )
                except Exception:
                    changed_profile_root = False

                if changed_profile_root:
                    ok_profiles, msg_profiles, _ = apply_profile_root_change(
                        requested_profiles_dir,
                        source_root=current_profile_root,
                    )
                    if not ok_profiles:
                        self.app.main_area.page.snack_bar = ft.SnackBar(ft.Text(f"⚠️ {msg_profiles}"))
                        self.app.main_area.page.snack_bar.open = True
                        self.app.main_area.page.update()
                        return

                    profile_root_changed = True
                    info_messages.append(msg_profiles)

            if data_dir_changed or profile_root_changed:
                _sync_account_profile_paths()

            dlg.open = False
            self.app.main_area.page.dialog = None
            self.app.main_area.page.snack_bar = ft.SnackBar(
                ft.Text("✅ " + " ".join(info_messages))
            )
            self.app.main_area.page.snack_bar.open = True
            self.app.main_area.page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Bot Configuration"),
            content=ft.Column(
                [
                    auto_start_cb,
                    auto_start_on_launch_cb,
                    windows_startup_cb,
                    startup_hint,
                    ft.Row([data_dir_field, data_dir_browse_btn], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    data_dir_hint,
                    ft.Row(
                        [profiles_dir_field, profiles_dir_browse_btn],
                        alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
                    ),
                    profiles_dir_hint,
                    interval_field,
                    retries_field,
                    steam_login_retries_field,
                ],
                tight=True,
                spacing=8,
            ),
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
        current_cfg = bot_runner.get_config()

        token_field = ft.TextField(
            label="Telegram Bot Token",
            password=True,
            can_reveal_password=True,
            value=str(current_cfg.get("telegram_bot_token", "") or ""),
            hint_text="Example: 123456:ABC-DEF...",
        )
        chat_id_field = ft.TextField(
            label="Telegram Chat ID",
            value=str(current_cfg.get("telegram_chat_id", "") or ""),
            hint_text="Example: 123456789",
        )
        notify_skin_cb = ft.Checkbox(
            label="Notify when skins are obtained",
            value=bool(current_cfg.get("telegram_notify_on_skin", True)),
        )
        notify_error_cb = ft.Checkbox(
            label="Notify when errors happen",
            value=bool(current_cfg.get("telegram_notify_on_error", True)),
        )

        def save_settings(_):
            ok, message = bot_runner.update_config(
                {
                    "telegram_bot_token": token_field.value,
                    "telegram_chat_id": chat_id_field.value,
                    "telegram_notify_on_skin": bool(notify_skin_cb.value),
                    "telegram_notify_on_error": bool(notify_error_cb.value),
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
            title=ft.Text("Notifications"),
            content=ft.Column(
                [
                    token_field,
                    chat_id_field,
                    notify_skin_cb,
                    notify_error_cb,
                ],
                spacing=10,
                tight=True,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._close_dialog(dlg)),
                ft.TextButton("Save", on_click=save_settings),
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
            ], spacing=5, tight=True),
            actions=[
                ft.TextButton("OK", on_click=lambda _: self._close_dialog(dlg)),
            ],
        )

        self.app.main_area.page.dialog = dlg
        dlg.open = True
        self.app.main_area.page.update()
