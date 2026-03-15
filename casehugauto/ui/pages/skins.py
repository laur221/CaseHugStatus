import flet as ft
import html
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD, SkinCRUD
from ...core.rarity import color_for_rarity_label


class SkinsPage:
    def __init__(self, app):
        self.app = app
        self.content = None
        self.selected_account = None  # None = All Accounts
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
            value="all",
            options=[ft.dropdown.Option(key="all", text="All Accounts")]
            + [ft.dropdown.Option(key=str(a.id), text=a.account_name) for a in accounts],
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
            runs_count=4,
            child_aspect_ratio=0.72,
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

        # Load all skins initially.
        self._refresh_skins(update_ui=False)
        
        return ft.Container(
            content=self.content,
            expand=True,
            padding=10,
        )
    
    def _on_account_selected(self, e):
        """Account selected"""
        if e.control.value:
            if e.control.value == "all":
                self.selected_account = None
            else:
                try:
                    self.selected_account = int(e.control.value)
                except (TypeError, ValueError):
                    self.selected_account = None
            self._refresh_skins()
    
    def _refresh_skins(self, update_ui: bool = True):
        """Refresh skins display"""
        db = SessionLocal()
        try:
            if self.selected_account is None:
                skins = SkinCRUD.get_all(db)
            else:
                skins = SkinCRUD.get_by_account(db, self.selected_account)

            # Build a fallback image map by skin name so cards with missing image_url
            # can still render a known image from another row of the same item.
            image_by_skin_name = {}
            for skin in skins:
                key = str(getattr(skin, "skin_name", "") or "").strip().lower()
                if not key:
                    continue
                src = html.unescape(str(getattr(skin, "skin_image_url", "") or "").strip())
                if not src:
                    continue
                image_by_skin_name.setdefault(key, src)
            
            self.skins_grid.controls.clear()
            
            if not skins:
                self.skins_grid.controls.append(
                    ft.Container(
                        content=ft.Text("No skins yet", color="#888888"),
                    )
                )
            else:
                for skin in skins:
                    self.skins_grid.controls.append(
                        self._create_skin_card(skin, image_by_skin_name)
                    )
            
            if update_ui and self.skins_grid.page:
                self.skins_grid.update()
        
        finally:
            db.close()
    
    def _create_skin_card(self, skin, image_by_skin_name: dict) -> ft.Card:
        """Create skin card"""
        account_name = (
            skin.account.account_name
            if getattr(skin, "account", None) and skin.account and skin.account.account_name
            else f"Account #{skin.account_id}"
        )
        image_src = html.unescape(str(skin.skin_image_url or "").strip())
        if not image_src:
            key = str(getattr(skin, "skin_name", "") or "").strip().lower()
            if key:
                image_src = image_by_skin_name.get(key, "")
        new_badge = ft.Container(
            content=ft.Text("NEW", size=10, weight="bold", color="white"),
            padding=5,
            bgcolor="#00d4ff",
            border_radius=3,
            visible=skin.is_new,
        )
        rarity_label = str(getattr(skin, "rarity", "") or "").strip()
        rarity_color = color_for_rarity_label(rarity_label)
        if image_src:
            image_block = ft.Image(
                src=image_src,
                                fit=ft.ImageFit.CONTAIN,
                width=180,
                height=130,
                border_radius=8,
            )
        else:
            image_block = ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(ft.icons.IMAGE_NOT_SUPPORTED, color="#666666", size=30),
                        ft.Text("No image", size=10, color="#666666"),
                    ],
                    spacing=4,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                    alignment=ft.MainAxisAlignment.CENTER,
                ),
                width=180,
                height=130,
                bgcolor="#111111",
                border_radius=8,
                alignment=ft.alignment.center,
            )
        
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        new_badge,
                        ft.Container(content=image_block, alignment=ft.alignment.center),
                        ft.Container(
                            content=ft.Text(
                                skin.skin_name,
                                size=12,
                                weight="bold",
                            ),
                            padding=ft.padding.only(top=8, left=6, right=6),
                        ),
                        ft.Container(
                            content=ft.Text(
                                f"${(skin.estimated_price or 0.0):.2f}",
                                size=14,
                                weight="bold",
                                color="#00d4ff",
                            ),
                            padding=ft.padding.only(left=6, right=6),
                        ),
                        ft.Text(
                            rarity_label or "Unknown rarity",
                            size=10,
                            color=rarity_color if rarity_label else "#888888",
                        ),
                        ft.Text(
                            (skin.case_source or "unknown").upper(),
                            size=10,
                            color="#888888",
                        ),
                        ft.Text(
                            f"Account: {account_name}",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            height=24,
                            size=10,
                            color="#aaaaaa",
                        ),
                    ],
                    spacing=5,
                    alignment=ft.MainAxisAlignment.START,
                ),
                padding=10,
                bgcolor="#1a1a1a",
            ),
            width=220,
            height=380,
        )
