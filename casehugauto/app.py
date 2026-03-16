import flet as ft
import asyncio
from datetime import datetime
from pathlib import Path
from queue import Empty, SimpleQueue
import time
from .ui.pages.home import HomePage
from .ui.pages.accounts import AccountsPage
from .ui.pages.skins import SkinsPage
from .ui.pages.account_stats import AccountStatsPage
from .ui.pages.settings import SettingsPage
from .database.db import init_db
from .core.bot_runner import bot_runner
import logging
import os
from threading import Thread
try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*_args, **_kwargs):
        return False

try:
    import pystray
except Exception:  # pragma: no cover - optional dependency fallback
    pystray = None

try:
    from PIL import Image
except Exception:  # pragma: no cover - optional dependency fallback
    Image = None


# Setup logging
os.makedirs("logs", exist_ok=True)
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("logs/app.log", encoding="utf-8"),
    ],
    force=True,
)
logger = logging.getLogger(__name__)
logging.getLogger("urllib3.connectionpool").setLevel(logging.ERROR)
load_dotenv()

APP_ASSETS_DIR = Path(__file__).resolve().parent / "assets"
APP_LOGO_PATH = APP_ASSETS_DIR / "casehugauto_logo.png"
APP_SIDEBAR_LOGO_PATH = APP_ASSETS_DIR / "casehugauto_sidebar.png"
APP_ICON_PATH = APP_ASSETS_DIR / "casehugauto_icon.ico"


class CaseHugAutoApp:
    def __init__(self):
        self.current_page = None
        self.accounts_page = None
        self.skins_page = None
        self.home_page = None
        self.settings_page = None
        self.account_stats_page = None
        self.activity_events = []
        self._ui_event_queue = SimpleQueue()
        self._ui_event_pump_started = False
        self._last_runtime_update = None
        self._status_icon = None
        self._status_text = None
        self._status_time_text = None
        self._last_heartbeat_render = 0.0
        self._auto_start_checked = False
        self.nav_rail = None
        self._page_switcher = None
        self._close_to_background_enabled = True
        self._close_background_hint_sent = False
        self._last_close_request_at = 0.0
        self._tray_icon = None
        self._tray_thread = None

    def init_pages(self, page: ft.Page):
        """Initialize all pages"""
        self.home_page = HomePage(self)
        self.accounts_page = AccountsPage(self)
        self.skins_page = SkinsPage(self)
        self.account_stats_page = AccountStatsPage(self)
        self.settings_page = SettingsPage(self)

    def add_activity(self, message: str, level: str = "info"):
        """Thread-safe activity feed entry shown in GUI."""
        self._ui_event_queue.put(
            {
                "time": datetime.now().strftime("%H:%M:%S"),
                "message": message,
                "level": level,
            }
        )

    def get_recent_events(self, limit: int = 25):
        if limit <= 0:
            return []
        return self.activity_events[-limit:]

    def _register_bot_status_callback(self):
        def _on_bot_status(payload):
            account_name = (payload.get("account_name") or "").strip()
            if not account_name:
                account_name = str(payload.get("account_id", "?"))
            message = payload.get("message", "")
            status = payload.get("status", "info")
            self.add_activity(f"Bot[{account_name}] {message}", status)

        bot_runner.set_status_callback(_on_bot_status)

    def _status_color(self, level: str) -> str:
        normalized = (level or "").lower()
        if normalized in {"error", "failed", "fatal"}:
            return "#ff6b6b"
        if normalized in {"success", "started", "running"}:
            return "#51cf66"
        if normalized in {"warning", "stopped"}:
            return "#f59f00"
        return "#00d4ff"

    def _apply_activity_event(self, event):
        self.activity_events.append(event)
        if len(self.activity_events) > 300:
            self.activity_events = self.activity_events[-300:]

        if self._status_text:
            self._status_text.value = event["message"]
            self._status_text.color = self._status_color(event["level"])
        if self._status_icon:
            self._status_icon.color = self._status_color(event["level"])
        if self._status_time_text:
            self._status_time_text.value = f"Last update: {event['time']}"

        self._last_runtime_update = event["time"]

    def _refresh_home_activity_if_visible(self):
        if self.current_page == self.home_page and hasattr(self.home_page, "refresh_activity_log"):
            self.home_page.refresh_activity_log(update_page=False)

    def _start_ui_event_pump(self):
        if self._ui_event_pump_started:
            return
        self._ui_event_pump_started = True

        async def _pump():
            while True:
                await asyncio.sleep(0.4)
                changed = False
                drained = 0
                while drained < 100:
                    try:
                        event = self._ui_event_queue.get_nowait()
                    except Empty:
                        break
                    self._apply_activity_event(event)
                    drained += 1
                    changed = True

                if changed:
                    self._refresh_home_activity_if_visible()
                    if hasattr(self, "page"):
                        self.page.update()
                else:
                    now_monotonic = time.monotonic()
                    if (
                        self._status_time_text
                        and hasattr(self, "page")
                        and (now_monotonic - self._last_heartbeat_render) >= 3.0
                    ):
                        self._status_time_text.value = (
                            f"Alive: {datetime.now().strftime('%H:%M:%S')}"
                        )
                        self._last_heartbeat_render = now_monotonic
                        self.page.update()

        self.page.run_task(_pump)

    def _auto_start_active_accounts_on_launch(self):
        if self._auto_start_checked:
            return
        self._auto_start_checked = True

        cfg = bot_runner.get_config()
        if not bool(cfg.get("auto_start_active_accounts_on_launch", False)):
            return

        started, already_running, errors = bot_runner.start_active_accounts()

        if started > 0:
            self.add_activity(
                f"Auto-start launched {started} active account worker(s).",
                "success",
            )
        if already_running > 0:
            self.add_activity(
                f"{already_running} active account worker(s) were already running.",
                "info",
            )
        if errors:
            preview = errors[0]
            self.add_activity(
                f"Auto-start warning: {preview}",
                "warning",
            )


    def _create_tray_image(self):
        if Image is None:
            return None
        if APP_ICON_PATH.exists():
            try:
                return Image.open(APP_ICON_PATH)
            except Exception:
                pass
        try:
            return Image.new("RGBA", (64, 64), (11, 21, 36, 255))
        except Exception:
            return None

    def _restore_from_tray(self):
        try:
            self.page.window.skip_task_bar = False
            self.page.window.minimized = False
            self.page.window.visible = True
            self.page.update()
        except Exception as exc:
            logger.warning("Failed to restore window from tray: %s", exc)

    def _exit_from_tray(self):
        self._close_to_background_enabled = False
        self._stop_tray_icon()
        try:
            self.page.window.destroy()
        except Exception:
            pass

    def _ensure_tray_icon(self) -> bool:
        if pystray is None:
            return False
        if self._tray_icon is not None:
            return True

        image = self._create_tray_image()
        if image is None:
            return False

        try:
            menu = pystray.Menu(
                pystray.MenuItem("Open", lambda _icon, _item: self._restore_from_tray()),
                pystray.MenuItem("Exit", lambda _icon, _item: self._exit_from_tray()),
            )
            self._tray_icon = pystray.Icon("CaseHugAuto", image, "CaseHugAuto", menu=menu)
            self._tray_thread = Thread(target=self._tray_icon.run, name="casehugauto-tray", daemon=True)
            self._tray_thread.start()
            return True
        except Exception as exc:
            logger.warning("Failed to initialize tray icon: %s", exc)
            self._tray_icon = None
            self._tray_thread = None
            return False

    def _stop_tray_icon(self):
        if self._tray_icon is None:
            return
        try:
            self._tray_icon.stop()
        except Exception:
            pass
        self._tray_icon = None
        self._tray_thread = None

    def _on_window_event(self, e: ft.WindowEvent):
        """Handle desktop window events."""
        if e.type == ft.WindowEventType.CLOSE and self._close_to_background_enabled:
            tray_ready = self._ensure_tray_icon()
            self.page.window.minimized = True
            self.page.window.skip_task_bar = True if tray_ready else False
            if not self._close_background_hint_sent:
                self._close_background_hint_sent = True
                self.add_activity(
                    "Window minimized to system tray. Use tray icon to restore or exit."
                    if tray_ready
                    else "Tray icon is unavailable. Window was minimized instead.",
                    "info",
                )
            self.page.update()

    def _set_main_content(self, content):
        """Set main content with transition animation when available."""
        if self._page_switcher is not None:
            self._page_switcher.content = ft.Container(
                content=content,
                expand=True,
                key=f"view-{time.time_ns()}",
            )
            if hasattr(self._page_switcher, "page") and self._page_switcher.page:
                self._page_switcher.update()
        else:
            self.main_area.content = content

    def _looks_like_db_error(self, error_text: str) -> bool:
        text = (error_text or "").lower()
        markers = (
            "psycopg2.operationalerror",
            "password authentication failed",
            "could not connect to server",
            "connection to server at",
            "connection refused",
            "localhost",
            "port 5432",
            "postgresql",
            "sqlalchemy.exc.operationalerror",
        )
        return any(marker in text for marker in markers)

    def _open_database_settings(self, _=None):
        try:
            self.navigate_to("settings")
            if self.settings_page and hasattr(self.settings_page, "_show_database_settings"):
                self.settings_page._show_database_settings()
        except Exception as exc:
            logger.warning("Could not open Database Settings from error view: %s", exc)

    def _build_page_error_content(self, error: Exception):
        error_text = str(error)

        if self._looks_like_db_error(error_text):
            return ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Database connection failed", color="#ff6b6b", weight="bold", size=18),
                        ft.Text(
                            "The Skins/Stats page requires a valid PostgreSQL connection before it can be displayed.",
                            size=13,
                            color="#d0d8e4",
                        ),
                        ft.Text("What to do first:", weight="bold", size=13, color="#7ed8ff"),
                        ft.Text("1. Open Settings -> Database Connection", size=12, color="#c2cedd"),
                        ft.Text("2. Enter the correct Host, Port, Database, Username, and Password", size=12, color="#c2cedd"),
                        ft.Text("3. Click Test Connection, then Save", size=12, color="#c2cedd"),
                        ft.Text("4. Open the Skins/Stats page again", size=12, color="#c2cedd"),
                        ft.Row(
                            [
                                ft.ElevatedButton(
                                    "Open database settings",
                                    icon=ft.icons.STORAGE,
                                    on_click=self._open_database_settings,
                                ),
                            ]
                        ),
                        ft.Divider(),
                        ft.Text("Technical details:", size=11, color="#8fa0b8"),
                        ft.Text(error_text, size=11, color="#8fa0b8", selectable=True),
                    ],
                    spacing=8,
                    scroll=ft.ScrollMode.AUTO,
                    expand=True,
                ),
                padding=20,
                bgcolor="#1a1a1a",
                border_radius=8,
            )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Error loading page", color="red", weight="bold"),
                    ft.Text(error_text, size=12, color="#888888", selectable=True),
                ],
                spacing=8,
            ),
            padding=20,
            bgcolor="#1a1a1a",
            border_radius=8,
        )

    def show_custom_content(self, content):
        """Show non-page content (e.g. settings sub-pages) in main area with animation."""
        self._set_main_content(content)
        if hasattr(self, "page"):
            self.page.update()

    def navigate_to(self, page_name: str):
        """Navigate to specific page"""
        index_map = {
            "home": 0,
            "accounts": 1,
            "skins": 2,
            "account_stats": 3,
            "settings": 4,
        }
        target_index = index_map.get(page_name)
        if self.nav_rail is not None and target_index is not None and self.nav_rail.selected_index != target_index:
            self.nav_rail.selected_index = target_index
            if hasattr(self.nav_rail, "page") and self.nav_rail.page:
                self.nav_rail.update()

        if page_name == "home":
            self.show_page(self.home_page)
        elif page_name == "accounts":
            self.show_page(self.accounts_page)
        elif page_name == "skins":
            self.show_page(self.skins_page)
        elif page_name == "account_stats":
            self.show_page(self.account_stats_page)
        elif page_name == "settings":
            self.show_page(self.settings_page)

    def show_page(self, page_content):
        """Show page in main area"""
        try:
            built_content = page_content.build()
            self._set_main_content(built_content)
            self.current_page = page_content
            if hasattr(self, "page"):
                self.page.update()
        except Exception as e:
            logger.error(f"Error showing page: {e}", exc_info=True)
            error_container = self._build_page_error_content(e)
            self._set_main_content(error_container)
            if hasattr(self, "page"):
                self.page.update()

    def build(self, page: ft.Page):
        """Build main application UI"""
        page.title = "CaseHugAuto"
        page.window.width = 1200
        page.window.height = 800
        page.theme_mode = ft.ThemeMode.DARK
        page.theme = ft.Theme(color_scheme_seed="#00d4ff", use_material3=True)
        page.bgcolor = "#080f1d"
        page.padding = 0
        page.spacing = 0
        page.window.prevent_close = True
        page.window.on_event = self._on_window_event
        page.window.skip_task_bar = False

        if APP_ICON_PATH.exists():
            try:
                page.window.icon = str(APP_ICON_PATH)
            except Exception:
                pass

        self.page = page

        # Initialize pages
        self.init_pages(page)

        # Create navigation rail
        logo_control = ft.Container(
            content=ft.Column(
                [
                    ft.Image(
                        src=str(APP_SIDEBAR_LOGO_PATH if APP_SIDEBAR_LOGO_PATH.exists() else APP_LOGO_PATH),
                        width=36,
                        height=36,
                        fit=ft.ImageFit.CONTAIN,
                    ) if (APP_SIDEBAR_LOGO_PATH.exists() or APP_LOGO_PATH.exists()) else ft.Icon(ft.icons.ROCKET_LAUNCH, size=32, color="#7ed8ff"),
                ],
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                spacing=4,
            ),
            padding=ft.padding.only(top=6, bottom=8),
        )

        def nav_destination(icon_outline, icon_filled, label):
            return ft.NavigationRailDestination(
                icon=icon_outline,
                selected_icon=icon_filled,
                label=label,
            )

        nav_kwargs = dict(
            selected_index=0,
            min_width=78,
            min_extended_width=78,
            group_alignment=-0.95,
            use_indicator=True,
            indicator_color="#1f3753",
            indicator_shape=ft.RoundedRectangleBorder(radius=12),
            leading=logo_control,
            destinations=[
                nav_destination(ft.icons.HOME, ft.icons.HOME, "Home"),
                nav_destination(ft.icons.PEOPLE, ft.icons.PEOPLE, "Accounts"),
                nav_destination(ft.icons.INVENTORY, ft.icons.INVENTORY, "Skins"),
                nav_destination(ft.icons.INSIGHTS, ft.icons.INSIGHTS, "Stats"),
                nav_destination(ft.icons.SETTINGS, ft.icons.SETTINGS, "Settings"),
            ],
            on_change=lambda e: self.navigate_to(
                ["home", "accounts", "skins", "account_stats", "settings"][e.control.selected_index]
            ),
            bgcolor="#0f1726",
        )
        # Flet API differs between versions; drop unsupported style args gracefully.
        for optional_key in ("use_indicator", "indicator_shape", "indicator_color"):
            try:
                nav_rail = ft.NavigationRail(**nav_kwargs)
                break
            except TypeError as exc:
                if optional_key in nav_kwargs and optional_key in str(exc):
                    nav_kwargs.pop(optional_key, None)
                    continue
                raise
        else:
            nav_rail = ft.NavigationRail(**nav_kwargs)
        self.nav_rail = nav_rail

        # Main content area with animated transitions
        self._page_switcher = ft.AnimatedSwitcher(
            content=ft.Container(content=ft.Text(" "), expand=True, key="initial"),
            transition=ft.AnimatedSwitcherTransition.FADE,
            duration=220,
            reverse_duration=140,
            switch_in_curve="easeOutCubic",
            switch_out_curve="easeInCubic",
            expand=True,
        )

        self.main_area = ft.Container(
            content=self._page_switcher,
            expand=True,
            padding=ft.padding.symmetric(horizontal=20, vertical=16),
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=["#0a1220", "#101a2a", "#0b1524"],
            ),
            border=ft.border.all(1, "#1a2b43"),
            border_radius=ft.border_radius.all(12),
        )

        main_layout = ft.Container(
            content=ft.Row(
                [nav_rail, self.main_area],
                spacing=12,
                expand=True,
            ),
            expand=True,
            padding=ft.padding.only(left=12, right=12, top=10, bottom=6),
        )

        self._status_icon = ft.Icon(ft.icons.CIRCLE, size=10, color="#51cf66")
        self._status_text = ft.Text("Application is running.", size=12, color="#51cf66")
        self._status_time_text = ft.Text("Last update: -", size=11, color="#9aa7bd")
        status_bar = ft.Container(
            content=ft.Row(
                [
                    self._status_icon,
                    self._status_text,
                    ft.Container(expand=True),
                    self._status_time_text,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            padding=ft.padding.symmetric(horizontal=14, vertical=8),
            gradient=ft.LinearGradient(
                begin=ft.alignment.center_left,
                end=ft.alignment.center_right,
                colors=["#141d2d", "#162337"],
            ),
            border=ft.border.only(top=ft.BorderSide(1, "#2b3a52")),
        )

        root_layout = ft.Container(
            content=ft.Column(
                [
                    main_layout,
                    status_bar,
                ],
                spacing=0,
                expand=True,
            ),
            expand=True,
            gradient=ft.LinearGradient(
                begin=ft.alignment.top_left,
                end=ft.alignment.bottom_right,
                colors=["#060b14", "#0a1120", "#070d18"],
            ),
        )

        page.add(root_layout)
        self._register_bot_status_callback()
        self._start_ui_event_pump()
        self.add_activity("Application UI started.", "success")
        self._auto_start_active_accounts_on_launch()

        try:
            self.show_page(self.home_page)
        except Exception as e:
            logger.error(f"FATAL: Failed to build initial page: {e}", exc_info=True)
            error_dialog = ft.AlertDialog(
                title=ft.Text("Application Error"),
                content=ft.Text(f"Could not load the application UI.\n\nError: {e}\n\nCheck logs for more details."),
                modal=True,
            )
            page.dialog = error_dialog
            error_dialog.open = True

        page.update()


def main(page: ft.Page):
    """Main entry point"""
    try:
        db_init_success = init_db()
        if db_init_success:
            logger.info("Database initialized successfully")
        else:
            logger.warning("Database initialization failed - app will work with limited functionality")

        app = CaseHugAutoApp()
        app.build(page)

    except Exception as e:
        logger.error(f"Error starting app: {e}", exc_info=True)
        error_container = ft.Container(
            content=ft.Column(
                [
                    ft.Text("⚠️ Application Error", size=20, weight="bold", color="orange"),
                    ft.Divider(),
                    ft.Text(f"Error: {str(e)}", size=14, color="red"),
                    ft.Text(
                        "\nPossible fixes:\n"
                        "1. Configure PostgreSQL credentials in .env\n"
                        "2. Verify the PostgreSQL server is reachable\n"
                        "3. Ensure the user can create or access the target database",
                        size=12,
                        color="#888888",
                    ),
                ],
                spacing=10,
                alignment=ft.MainAxisAlignment.START,
            ),
            padding=20,
            bgcolor="#1e1a1a",
        )
        page.add(error_container)


def run():
    """Run the application"""
    ft.app(target=main)


if __name__ == "__main__":
    run()
