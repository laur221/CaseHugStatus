import flet as ft
import logging
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD, SkinCRUD, BotStatusCRUD
from ..components.steam_login_dialog import SteamLoginDialog
from ..components.steam_login_qr_dialog import SteamLoginQRDialog
from ...core.bot_runner import bot_runner

logger = logging.getLogger(__name__)


class AccountsPage:
    def __init__(self, app):
        self.app = app
        self.content = None
        self.accounts_list = None
        self.steam_login_dialog = None
        
    def build(self) -> ft.Container:
        """Build accounts page"""
        header = ft.Row(
            [
                ft.Text("Accounts", size=24, weight="bold"),
                ft.Row([
                    ft.ElevatedButton(
                        "Import Profiles",
                        icon="cloud_download",
                        on_click=self._import_profiles,
                    ),
                    ft.ElevatedButton(
                        "Add Account",
                        icon="add",
                        on_click=self._show_add_account_dialog,
                    )
                ], spacing=10)
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        # Accounts list
        self.accounts_list = ft.Column(
            scroll=ft.ScrollMode.AUTO,
            expand=True,
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

        # Populate list only after controls are initialized.
        self.refresh_accounts()
        
        return ft.Container(
            content=self.content,
            expand=True,
            padding=10,
        )
    
    def refresh_accounts(self):
        """Refresh accounts list"""
        if not self.accounts_list:
            return

        db = SessionLocal()
        try:
            accounts = AccountCRUD.get_all(db)
            self.accounts_list.controls.clear()

            if not accounts:
                self.accounts_list.controls.append(
                    ft.Container(
                        content=ft.Text(
                            "No accounts yet. Add one to get started!",
                            size=14,
                            color="#888888",
                        ),
                        padding=20,
                        alignment=ft.alignment.center,
                    )
                )
            else:
                rendered = 0
                for account in accounts:
                    try:
                        self.accounts_list.controls.append(self._create_account_card(account, db))
                        rendered += 1
                    except Exception as exc:
                        logger.error(
                            "Could not render account card for account_id=%s: %s",
                            getattr(account, "id", "unknown"),
                            exc,
                            exc_info=True,
                        )

                if rendered == 0:
                    self.accounts_list.controls.append(
                        ft.Container(
                            content=ft.Text(
                                "Accounts exist in database, but rendering failed. Check logs.",
                                size=14,
                                color="#ff6b6b",
                            ),
                            padding=20,
                            alignment=ft.alignment.center,
                        )
                    )

            # Only update if control is already on page
            try:
                if hasattr(self.accounts_list, "page") and self.accounts_list.page:
                    self.accounts_list.update()
            except Exception as e:
                logger.debug(f"Could not update accounts list: {e}")
        
        finally:
            db.close()
    
    def _create_account_card(self, account, db) -> ft.Card:
        """Create account card"""
        bot_status = BotStatusCRUD.get_or_create(db, account.id)
        skins_count = len(SkinCRUD.get_by_account(db, account.id))
        is_running = bot_runner.is_running(account.id)
        
        avatar = ft.CircleAvatar(
            foreground_image_src=account.steam_avatar_url if account.steam_avatar_url else None,
            radius=40,
            bgcolor="#333",
        )
        
        account_info = ft.Column(
            [
                ft.Text(account.account_name, size=16, weight="bold"),
                ft.Text(account.steam_nickname or "Not logged in", size=12, color="#888888"),
                ft.Text(
                    f"Profile: {account.browser_profile_path or 'pending'}",
                    size=11,
                    color="#666666",
                    overflow=ft.TextOverflow.ELLIPSIS,
                ),
                ft.Text(
                    f"Skins: {skins_count} | Cases: {bot_status.cases_opened_total} | Value: ${bot_status.total_value_obtained:.2f}",
                    size=11,
                    color="#666666",
                ),
            ],
            spacing=5,
            expand=True,
        )
        
        # Action buttons
        actions = ft.Row(
            [
                ft.IconButton(
                    "refresh",
                    tooltip="Login/Refresh",
                    on_click=lambda _: self._refresh_account(account),
                ),
                ft.IconButton(
                    "stop" if is_running else "play_arrow",
                    tooltip="Stop Bot" if is_running else "Run Bot",
                    icon_color="#ff6b6b" if is_running else "#00d4ff",
                    on_click=lambda _: self._toggle_bot(account),
                ),
                ft.IconButton(
                    "delete",
                    tooltip="Delete Account",
                    on_click=lambda _: self._delete_account(account),
                ),
            ],
            spacing=5,
        )
        
        return ft.Card(
            content=ft.Container(
                content=ft.Row(
                    [avatar, account_info, actions],
                    spacing=15,
                    expand=True,
                ),
                padding=15,
                bgcolor="#1a1a1a",
            ),
            margin=ft.margin.only(bottom=10),
        )
    
    def _show_add_account_dialog(self, e):
        """Show Steam login dialog for adding new account"""
        def on_account_added(account):
            """Callback when account is successfully added"""
            self.refresh_accounts()
            if hasattr(self.app, 'page'):
                self.app.page.snack_bar = ft.SnackBar(
                    ft.Text(f"✓ Account '{account.account_name}' added successfully!")
                )
                self.app.page.snack_bar.open = True
                self.app.page.update()
        
        # Create and show Steam login dialog
        steam_dialog = SteamLoginQRDialog(self.app, on_success=on_account_added)
        steam_dialog.show()
    
    def _import_profiles(self, e):
        """Import profiles from profiles/ folder"""
        db = SessionLocal()
        try:
            # Get available profiles to import
            available = AccountCRUD.get_available_profiles_to_import()
            
            if not available:
                self.app.main_area.page.snack_bar = ft.SnackBar(
                    ft.Text("❌ No profiles found in profiles/ folder")
                )
                self.app.main_area.page.snack_bar.open = True
                self.app.main_area.page.update()
                return
            
            # Import all profiles
            results = AccountCRUD.import_profiles_from_folder(db)
            
            # Count successes
            imported = sum(1 for v in results.values() if v)
            skipped = len(results) - imported
            
            message = f"✓ Imported {imported} profile(s)"
            if skipped > 0:
                message += f", skipped {skipped} (already exist)"
            
            self.refresh_accounts()
            
            self.app.main_area.page.snack_bar = ft.SnackBar(ft.Text(message))
            self.app.main_area.page.snack_bar.open = True
            self.app.main_area.page.update()
            
        except Exception as ex:
            self.app.main_area.page.snack_bar = ft.SnackBar(
                ft.Text(f"❌ Import error: {str(ex)}")
            )
            self.app.main_area.page.snack_bar.open = True
            self.app.main_area.page.update()
        
        finally:
            db.close()
    
    def _close_dialog(self, dlg):
        dlg.open = False
        self.app.main_area.page.update()
    
    def _refresh_account(self, account):
        """Trigger Steam login for account"""
        # Show Steam login dialog
        if not self.steam_login_dialog:
            self.steam_login_dialog = SteamLoginDialog(self.app, account)
        else:
            self.steam_login_dialog.account = account
        
        self.steam_login_dialog.show()
    
    def _run_bot(self, account):
        """Run bot for account"""
        print(f"Running bot for {account.account_name}")
        # TODO: Implement bot execution

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

        # Refresh to update status/button icon
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
