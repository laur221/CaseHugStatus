"""Database connection UI for PostgreSQL configuration."""

from __future__ import annotations

import logging
import os
import threading
import time

import flet as ft
from dotenv import dotenv_values
from sqlalchemy.engine import URL, make_url

from ...database.db import ensure_database_exists, init_db

logger = logging.getLogger(__name__)


def _read_env_file() -> dict[str, str]:
    env_content: dict[str, str] = {}
    try:
        with open(".env", "r", encoding="utf-8") as env_file:
            for line in env_file:
                stripped = line.strip()
                if stripped and not stripped.startswith("#") and "=" in stripped:
                    key, value = stripped.split("=", 1)
                    env_content[key.strip()] = value.strip()
    except FileNotFoundError:
        pass
    return env_content


def _write_env_file(env_content: dict[str, str]):
    with open(".env", "w", encoding="utf-8") as env_file:
        for key, value in env_content.items():
            env_file.write(f"{key}={value}\n")


def _get_saved_database_url() -> str:
    saved_values = dotenv_values(".env")
    saved_url = saved_values.get("DATABASE_URL")
    if saved_url:
        return str(saved_url)
    return os.getenv("DATABASE_URL", "")


def _get_connection_summary() -> tuple[str, str, str]:
    raw_url = _get_saved_database_url()
    if not raw_url:
        return "PostgreSQL", "Not configured", "Not configured"

    try:
        parsed = make_url(raw_url)
        masked_url = parsed.render_as_string(hide_password=True)
        return "PostgreSQL", parsed.database or "Unknown", masked_url
    except Exception:
        return "PostgreSQL", "Unknown", raw_url


class DatabaseConnectionDialog:
    """Dialog for configuring and testing a PostgreSQL connection."""

    def __init__(self, app, on_connected=None):
        self.app = app
        self.on_connected = on_connected
        self.dialog = None
        self.connecting = False

    def show(self):
        """Show database connection dialog."""
        saved_url = _get_saved_database_url()
        default_host = "localhost"
        default_port = "5432"
        default_database = "casehugauto"
        default_username = "postgres"
        default_password = ""

        if saved_url:
            try:
                parsed = make_url(saved_url)
                default_host = parsed.host or default_host
                default_port = str(parsed.port or default_port)
                default_database = parsed.database or default_database
                default_username = parsed.username or default_username
                default_password = parsed.password or default_password
            except Exception:
                logger.warning("Could not parse saved DATABASE_URL.", exc_info=True)

        host_field = ft.TextField(
            label="Host/IP",
            value=default_host,
            width=400,
            prefix_icon=ft.icons.DNS,
        )
        port_field = ft.TextField(
            label="Port",
            value=default_port,
            width=400,
            prefix_icon=ft.icons.SETTINGS_ETHERNET,
        )
        database_field = ft.TextField(
            label="Database Name",
            value=default_database,
            width=400,
            prefix_icon=ft.icons.STORAGE,
        )
        username_field = ft.TextField(
            label="Username",
            value=default_username,
            width=400,
            prefix_icon=ft.icons.PERSON,
        )
        password_field = ft.TextField(
            label="Password",
            value=default_password,
            password=True,
            can_reveal_password=True,
            width=400,
            prefix_icon=ft.icons.LOCK,
        )
        status_text = ft.Text(
            "Introduce detaliile PostgreSQL. Baza de date va fi creata automat daca lipseste.",
            size=12,
            color="#888888",
        )

        def connect_database():
            self.connecting = True
            page = self.app.main_area.page
            try:
                status_text.value = "Se verifica conexiunea PostgreSQL..."
                status_text.color = "#ffaa00"
                page.update()

                host = (host_field.value or "localhost").strip()
                port = (port_field.value or "5432").strip()
                database = (database_field.value or "casehugauto").strip()
                username = (username_field.value or "postgres").strip()
                password = password_field.value or ""

                connection_url = URL.create(
                    drivername="postgresql",
                    username=username,
                    password=password,
                    host=host,
                    port=int(port),
                    database=database,
                ).render_as_string(hide_password=False)

                created = ensure_database_exists(connection_url)
                if not init_db(connection_url):
                    raise RuntimeError("Aplicatia nu a putut initializa tabelele PostgreSQL.")

                self._save_connection_details(connection_url)

                status_text.value = (
                    "Conexiune reusita. Baza de date a fost creata automat."
                    if created
                    else "Conexiune reusita."
                )
                status_text.color = "#00d4ff"
                page.update()

                if self.on_connected:
                    self.on_connected(connection_url)

                time.sleep(0.8)
                self.dialog.open = False
                page.update()
            except Exception as exc:
                status_text.value = f"Eroare conexiune: {str(exc)[:120]}"
                status_text.color = "red"
                logger.error("Database connection failed: %s", exc, exc_info=True)
                page.update()
            finally:
                self.connecting = False

        def on_connect_click(_):
            if not self.connecting:
                threading.Thread(target=connect_database, daemon=True).start()

        def on_cancel(_):
            self.dialog.open = False
            self.app.main_area.page.update()

        form_content = ft.Column(
            [
                ft.Text("PostgreSQL Connection", size=20, weight="bold"),
                ft.Divider(),
                host_field,
                port_field,
                database_field,
                username_field,
                password_field,
                ft.Container(height=10),
                status_text,
                ft.Container(height=10),
                ft.Text(
                    "Aplicatia foloseste doar PostgreSQL. Nu este necesara creare manuala a bazei daca utilizatorul are drepturile necesare.",
                    size=11,
                    color="#666666",
                ),
            ],
            spacing=10,
            scroll=ft.ScrollMode.AUTO,
        )

        self.dialog = ft.AlertDialog(
            title=ft.Text("Database Configuration"),
            content=ft.Container(content=form_content, width=500, padding=10),
            actions=[
                ft.TextButton("Cancel", on_click=on_cancel),
                ft.ElevatedButton("Connect", on_click=on_connect_click),
            ],
            modal=True,
        )

        self.app.main_area.page.dialog = self.dialog
        self.dialog.open = True
        self.app.main_area.page.update()

    def _save_connection_details(self, connection_url: str):
        env_content = _read_env_file()
        env_content["DATABASE_URL"] = connection_url
        os.environ["DATABASE_URL"] = connection_url
        _write_env_file(env_content)
        logger.info("Database configuration saved to .env")


class DatabaseSettingsPage:
    """Settings page for PostgreSQL connection management."""

    def __init__(self, app):
        self.app = app
        self.content = None
        self.connection_type_text = None
        self.database_name_text = None
        self.connection_url_text = None

    def build(self) -> ft.Container:
        self.connection_type_text = ft.Text(size=12, color="#888888")
        self.database_name_text = ft.Text(size=12, color="#888888")
        self.connection_url_text = ft.Text(size=11, color="#666666")

        current_connection = ft.Card(
            content=ft.Container(
                content=ft.Column(
                    [
                        ft.Text("Current Connection", size=14, weight="bold"),
                        self.connection_type_text,
                        self.database_name_text,
                        self.connection_url_text,
                    ],
                    spacing=5,
                ),
                padding=15,
                bgcolor="#1a1a1a",
            ),
        )

        def open_connection_dialog(_):
            dialog = DatabaseConnectionDialog(
                self.app,
                on_connected=lambda _url: self._refresh_current_connection_info(),
            )
            dialog.show()

        self.content = ft.Column(
            [
                ft.Text("Database Connection Settings", size=24, weight="bold"),
                ft.Divider(),
                ft.Text("Current Configuration", size=14, weight="bold", color="#00d4ff"),
                current_connection,
                ft.Container(height=20),
                ft.Text("Configure Database", size=14, weight="bold", color="#00d4ff"),
                ft.Row(
                    [
                        ft.ElevatedButton(
                            "Configure PostgreSQL",
                            icon=ft.icons.SETTINGS,
                            on_click=open_connection_dialog,
                        ),
                    ],
                    spacing=10,
                ),
                ft.Container(height=20),
                ft.Text("Information", size=14, weight="bold", color="#00d4ff"),
                ft.Card(
                    content=ft.Container(
                        content=ft.Column(
                            [
                                ft.Text("PostgreSQL only", weight="bold", size=12),
                                ft.Text(
                                    "CaseHugAuto foloseste exclusiv PostgreSQL pentru stocarea conturilor, skin-urilor si statisticilor.",
                                    size=11,
                                    color="#888888",
                                ),
                                ft.Container(height=10),
                                ft.Text("Creare automata", weight="bold", size=12),
                                ft.Text(
                                    "Daca baza specificata nu exista, aplicatia incearca sa o creeze automat folosind aceleasi credentiale.",
                                    size=11,
                                    color="#888888",
                                ),
                                ft.Container(height=10),
                                ft.Text("Conexiune curenta", weight="bold", size=12),
                                ft.Text(
                                    "Cardul de mai sus se actualizeaza imediat dupa o conectare reusita, fara restart al aplicatiei.",
                                    size=11,
                                    color="#888888",
                                ),
                            ],
                            spacing=5,
                        ),
                        padding=15,
                        bgcolor="#1a1a1a",
                    ),
                ),
            ],
            spacing=15,
            expand=True,
        )

        self._refresh_current_connection_info()

        return ft.Container(
            content=self.content,
            expand=True,
            padding=10,
        )

    def _refresh_current_connection_info(self):
        connection_type, database_name, database_url = _get_connection_summary()
        self.connection_type_text.value = f"Type: {connection_type}"
        self.database_name_text.value = f"Database: {database_name}"
        self.connection_url_text.value = f"URL: {database_url}"

        if hasattr(self.app, "page"):
            self.app.page.update()
