import flet as ft
import html
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD, SkinCRUD
from ...core.rarity import color_for_rarity_label
from ...core.skin_importer import import_skins_from_html


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

        account_dropdown = ft.Dropdown(
            label="Select Account",
            width=320,
            value="all",
            options=[ft.dropdown.Option(key="all", text="All Accounts")]
            + [ft.dropdown.Option(key=str(a.id), text=a.account_name) for a in accounts],
            on_change=self._on_account_selected,
        )

        import_html_btn = ft.OutlinedButton(
            "Import HTML",
            icon=ft.icons.UPLOAD_FILE,
            on_click=lambda _: self._show_import_html_dialog(),
        )

        header = ft.Row(
            [
                ft.Text("Skins", size=24, weight="bold"),
                ft.Row([account_dropdown, import_html_btn], spacing=8),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.skins_grid = ft.GridView(
            expand=True,
            runs_count=4,
            child_aspect_ratio=0.84,
            spacing=12,
            run_spacing=12,
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

        self._refresh_skins(update_ui=False)

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
            # Keep UX consistent: when account filter changes, show newest items from top.
            try:
                if self.skins_grid:
                    self.skins_grid.scroll_to(offset=0, duration=150)
            except Exception:
                pass

    def _refresh_skins(self, update_ui: bool = True):
        """Refresh skins display"""
        db = SessionLocal()
        try:
            if self.selected_account is None:
                skins = SkinCRUD.get_all(db)
            else:
                skins = SkinCRUD.get_by_account(db, self.selected_account)

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
                        content=ft.Text("No skins yet", color="#9aa7bd"),
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
                height=112,
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
                height=112,
                bgcolor="#111111",
                border_radius=8,
                alignment=ft.alignment.center,
            )

        return ft.Card(
            elevation=3,
            content=ft.Container(
                content=ft.Column(
                    [
                        new_badge,
                        ft.Container(content=image_block, alignment=ft.alignment.center),
                        ft.Container(
                            content=ft.Text(
                                skin.skin_name,
                                size=11,
                                weight="bold",
                                max_lines=1,
                                overflow=ft.TextOverflow.ELLIPSIS,
                            ),
                            padding=ft.padding.only(top=4),
                        ),
                        ft.Text(
                            f"${(skin.estimated_price or 0.0):.2f}",
                            size=15,
                            weight="bold",
                            color="#7ed8ff",
                        ),
                        ft.Text(
                            rarity_label or "Unknown rarity",
                            size=10,
                            color=rarity_color if rarity_label else "#9aa7bd",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                        ),
                        ft.Text(
                            (skin.case_source or "unknown").upper(),
                            size=10,
                            color="#9aa7bd",
                        ),
                        ft.Text(
                            f"Account: {account_name}",
                            max_lines=1,
                            overflow=ft.TextOverflow.ELLIPSIS,
                            size=10,
                            color="#aeb9cb",
                        ),
                    ],
                    spacing=3,
                    alignment=ft.MainAxisAlignment.START,
                ),
                padding=8,
                gradient=ft.LinearGradient(
                    begin=ft.alignment.top_left,
                    end=ft.alignment.bottom_right,
                    colors=["#142238", "#101c2f"],
                ),
                border=ft.border.all(1, "#2a4363"),
                border_radius=12,
            ),
        )

    def _show_import_html_dialog(self):
        page = self.app.main_area.page

        if self.selected_account is None:
            self._show_snackbar("⚠️ Select an account first, then import HTML.")
            return

        html_field = ft.TextField(
            label="Paste HTML from casehug.com/user-account",
            hint_text="Open user-account page, View Source / Copy Element, then paste here.",
            multiline=True,
            min_lines=14,
            max_lines=24,
            autofocus=True,
        )

        def do_import(_):
            raw_html = str(html_field.value or "").strip()
            if not raw_html:
                self._show_snackbar("⚠️ Paste HTML content first.")
                return

            db = SessionLocal()
            try:
                report = import_skins_from_html(db, self.selected_account, raw_html)
            except Exception as exc:
                self._show_snackbar(f"⚠️ Import failed: {exc}")
                return
            finally:
                db.close()

            if report.get("imported") is False or report.get("parsed", 0) == 0:
                self._show_snackbar(
                    f"⚠️ {report.get('message', 'No skins found in provided HTML.')}"
                )
                return

            dlg.open = False
            page.dialog = None
            self._refresh_skins(update_ui=True)
            self._show_snackbar(
                "✅ Import complete. "
                f"Parsed: {report.get('parsed', 0)}, "
                f"Created: {report.get('created', 0)}, "
                f"Updated: {report.get('updated', 0)}, "
                f"Skipped: {report.get('skipped', 0)}"
            )
            page.update()

        dlg = ft.AlertDialog(
            title=ft.Text("Import Skins (Non-destructive)"),
            content=ft.Column(
                [
                    ft.Text(
                        "This import does NOT delete existing skins from DB. "
                        "It only adds missing ones and updates matches.",
                        size=12,
                        color="#9aa7bd",
                    ),
                    html_field,
                ],
                tight=True,
                spacing=8,
                width=860,
            ),
            actions=[
                ft.TextButton("Cancel", on_click=lambda _: self._close_dialog(dlg)),
                ft.TextButton("Import", on_click=do_import),
            ],
        )

        page.dialog = dlg
        dlg.open = True
        page.update()

    def _close_dialog(self, dlg):
        page = self.app.main_area.page
        dlg.open = False
        page.dialog = None
        page.update()

    def _show_snackbar(self, message: str):
        page = self.app.main_area.page
        page.snack_bar = ft.SnackBar(ft.Text(message))
        page.snack_bar.open = True
        page.update()
