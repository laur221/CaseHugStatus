import flet as ft
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD, SkinCRUD


class SkinsPage:
    def __init__(self, app):
        self.app = app
        self.content = None
        self.selected_account = None
        self.skins_grid = None
        
    def build(self) -> ft.Container:
        """Build skins page"""
        db = SessionLocal()
        try:
            accounts = AccountCRUD.get_all(db)
        finally:
            db.close()
        
        # Account selector
        account_dropdown = ft.Dropdown(
            label="Select Account",
            width=300,
            options=[ft.dropdown.Option(a.account_name, a.id) for a in accounts],
            on_change=self._on_account_selected,
        )
        
        header = ft.Row(
            [
                ft.Text("Skins", size=24, weight="bold"),
                account_dropdown,
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )
        
        # Skins grid
        self.skins_grid = ft.GridView(
            expand=True,
            runs_count=5,
            spacing=10,
            run_spacing=10,
        )
        
        self.content = ft.Column(
            [
                header,
                ft.Divider(),
                self.skins_grid,
            ],
            spacing=10,
            expand=True,
        )
        
        return ft.Container(
            content=self.content,
            expand=True,
            padding=10,
        )
    
    def _on_account_selected(self, e):
        """Account selected"""
        if e.control.value:
            self.selected_account = e.control.value
            self._refresh_skins()
    
    def _refresh_skins(self):
        """Refresh skins display"""
        if not self.selected_account:
            return
        
        db = SessionLocal()
        try:
            skins = SkinCRUD.get_by_account(db, self.selected_account)
            
            self.skins_grid.controls.clear()
            
            if not skins:
                self.skins_grid.controls.append(
                    ft.Container(
                        content=ft.Text("No skins yet", color="#888888"),
                    )
                )
            else:
                for skin in skins:
                    self.skins_grid.controls.append(self._create_skin_card(skin))
            
            self.skins_grid.update()
        
        finally:
            db.close()
    
    def _create_skin_card(self, skin) -> ft.Card:
        """Create skin card"""
        new_badge = ft.Container(
            content=ft.Text("NEW", size=10, weight="bold", color="white"),
            padding=5,
            bgcolor="#00d4ff",
            border_radius=3,
            visible=skin.is_new,
        )
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        new_badge,
                        ft.Container(
                            content=ft.Text(
                                skin.skin_name,
                                size=12,
                                weight="bold",
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            padding=10,
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"${skin.estimated_price:.2f}",
                                size=14,
                                weight="bold",
                                color="#00d4ff",
                            ),
                            padding=5,
                        ),
                        ft.Text(
                            skin.rarity or "Unknown",
                            size=10,
                            color="#888888",
                        ),
                    ],
                    spacing=5,
                    alignment=ft.MainAxisAlignment.START,
                ),
                padding=10,
                bgcolor="#1a1a1a",
            ),
            width=200,
            height=200,
        )
