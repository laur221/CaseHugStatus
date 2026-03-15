import flet as ft
from sqlalchemy import func
from ...database.db import SessionLocal
from ...database.crud import AccountCRUD
from ...models.models import BotStatus, Skin
import threading
import time


class AccountStatsPage:
    def __init__(self, app):
        self.app = app
        self.content = None
        self.summary_row = None
        self.stats_list = None
        self._refresh_loop_started = False
        self._last_snapshot = None

    def build(self) -> ft.Container:
        """Build account statistics page."""
        header = ft.Row(
            [
                ft.Text("Account Statistics", size=24, weight="bold"),
                ft.ElevatedButton("Refresh", icon="refresh", on_click=lambda _: self._refresh_stats()),
            ],
            alignment=ft.MainAxisAlignment.SPACE_BETWEEN,
        )

        self.summary_row = ft.Row(
            [
                self._create_summary_card("Total Accounts", "0", "group"),
                self._create_summary_card("Total Skins", "0", "inventory"),
                self._create_summary_card("Total Value", "$0.00", "trending_up"),
            ],
            spacing=12,
            wrap=True,
        )

        self.stats_list = ft.Column(
            expand=True,
            scroll=ft.ScrollMode.AUTO,
            spacing=10,
        )

        self.content = ft.Column(
            [
                header,
                ft.Divider(),
                self.summary_row,
                ft.Divider(),
                self.stats_list,
            ],
            expand=True,
            spacing=10,
        )

        self._refresh_stats(update_ui=False)
        self._start_refresh_loop()

        return ft.Container(content=self.content, expand=True, padding=10)

    def _start_refresh_loop(self):
        if self._refresh_loop_started:
            return
        self._refresh_loop_started = True

        def _loop():
            while True:
                try:
                    if getattr(self.app, "current_page", None) == self:
                        self._refresh_stats()
                except Exception:
                    pass
                time.sleep(2.5)

        threading.Thread(target=_loop, daemon=True).start()

    def _refresh_stats(self, update_ui: bool = True):
        db = SessionLocal()
        try:
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
            skin_map = {
                row.account_id: {
                    "skins_count": int(row.skins_count or 0),
                    "total_value": float(row.total_value or 0.0),
                }
                for row in skin_rows
            }

            status_rows = db.query(BotStatus).all()
            status_map = {row.account_id: row for row in status_rows if row.account_id is not None}

            items = []
            total_skins = 0
            total_value = 0.0

            for account in sorted(accounts, key=lambda a: (a.account_name or "").lower()):
                skin_info = skin_map.get(account.id, {"skins_count": 0, "total_value": 0.0})
                status = status_map.get(account.id)
                cases_opened = int(getattr(status, "cases_opened_total", 0) or 0)
                bot_status = str(getattr(status, "status", "stopped") or "stopped").capitalize()
                last_run = getattr(status, "last_run", None)
                last_run_text = last_run.strftime("%Y-%m-%d %H:%M:%S") if last_run else "Never"

                skins_count = int(skin_info["skins_count"])
                account_value = float(skin_info["total_value"])
                avg_value = account_value / skins_count if skins_count > 0 else 0.0

                total_skins += skins_count
                total_value += account_value

                items.append(
                    {
                        "account_id": account.id,
                        "account_name": account.account_name,
                        "is_active": bool(account.is_active),
                        "bot_status": bot_status,
                        "skins_count": skins_count,
                        "total_value": round(account_value, 2),
                        "cases_opened": cases_opened,
                        "avg_value": round(avg_value, 2),
                        "last_run": last_run_text,
                    }
                )

            snapshot = (
                len(accounts),
                total_skins,
                round(total_value, 2),
                tuple(
                    (
                        item["account_id"],
                        item["is_active"],
                        item["bot_status"],
                        item["skins_count"],
                        item["total_value"],
                        item["cases_opened"],
                        item["avg_value"],
                        item["last_run"],
                    )
                    for item in items
                ),
            )

            if snapshot == self._last_snapshot:
                return
            self._last_snapshot = snapshot

            if self.summary_row:
                self.summary_row.controls.clear()
                self.summary_row.controls.extend(
                    [
                        self._create_summary_card("Total Accounts", str(len(accounts)), "group"),
                        self._create_summary_card("Total Skins", str(total_skins), "inventory"),
                        self._create_summary_card("Total Value", f"${total_value:.2f}", "trending_up"),
                    ]
                )

            if self.stats_list:
                self.stats_list.controls.clear()
                if not items:
                    self.stats_list.controls.append(
                        ft.Container(
                            content=ft.Text("No account statistics available yet.", color="#888888"),
                            padding=20,
                        )
                    )
                else:
                    for item in items:
                        self.stats_list.controls.append(self._create_account_stats_card(item))

            if update_ui and hasattr(self.app, "page"):
                self.app.page.update()
        finally:
            db.close()

    def _create_summary_card(self, title: str, value: str, icon_name: str) -> ft.Card:
        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Icon(icon_name, size=26, color="#00d4ff"),
                        ft.Text(title, size=12, color="#9aa3b2"),
                        ft.Text(value, size=20, weight="bold"),
                    ],
                    spacing=8,
                    horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                ),
                padding=16,
                width=240,
                bgcolor="#1a1a1a",
            )
        )

    def _create_account_stats_card(self, item: dict) -> ft.Card:
        active_color = "#51cf66" if item["is_active"] else "#9aa3b2"
        bot_color = "#51cf66" if item["bot_status"].lower() == "running" else "#9aa3b2"

        return ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Row(
                            [
                                ft.Text(item["account_name"], size=16, weight="bold"),
                                ft.Container(expand=True),
                                ft.Text(
                                    "Active" if item["is_active"] else "Inactive",
                                    size=11,
                                    color=active_color,
                                ),
                            ]
                        ),
                        ft.Row(
                            [
                                ft.Text(f"Bot: {item['bot_status']}", size=12, color=bot_color),
                                ft.Container(expand=True),
                                ft.Text(f"Last Run: {item['last_run']}", size=11, color="#888888"),
                            ]
                        ),
                        ft.Row(
                            [
                                ft.Text(f"Skins: {item['skins_count']}", size=12),
                                ft.Text(f"Total Value: ${item['total_value']:.2f}", size=12),
                                ft.Text(f"Avg Skin: ${item['avg_value']:.2f}", size=12),
                                ft.Text(f"Cases Opened: {item['cases_opened']}", size=12),
                            ],
                            wrap=True,
                            spacing=14,
                        ),
                    ],
                    spacing=8,
                ),
                padding=14,
                bgcolor="#1a1a1a",
            )
        )
