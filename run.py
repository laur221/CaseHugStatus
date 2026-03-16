#!/usr/bin/env python3
"""
CaseHugAuto - main entry point.

Runtime behavior:
- On Windows, hides console window by default (use --show-console to keep it).
- Uses per-user data directory by default:
  %APPDATA%\\CaseHugAuto (Windows) or platform equivalent.
- Supports overriding data directory via:
  --data-dir <path>, CASEHUGAUTO_HOME env var, or saved override file.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
import subprocess
import sys

from casehugauto.core.data_paths import (
    DATA_DIR_ENV,
    cleanup_old_logs,
    ensure_runtime_dirs,
    resolve_data_dir,
)


if sys.platform == "win32":
    try:
        import ctypes
    except Exception:  # pragma: no cover - platform specific fallback
        ctypes = None
else:
    ctypes = None


# ------------------------------------------------------------------ #
#  DEPENDENCIES — (import_name, pip_spec)
# ------------------------------------------------------------------ #
REQUIREMENTS = [
    ("sqlalchemy", "sqlalchemy==2.0.25"),
    ("psycopg2", "psycopg2-binary>=2.9.9"),
    ("dotenv", "python-dotenv>=1.0.1"),
    ("qrcode", "qrcode==7.4.2"),
    ("PIL", "pillow>=10.4.0"),
    ("nodriver", "nodriver>=0.35"),
    ("selenium", "selenium>=4.0.0"),
    ("undetected_chromedriver", "undetected-chromedriver>=3.5.0"),
    ("requests", "requests>=2.28.0"),
    ("psutil", "psutil>=5.9.0"),
]

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _hide_console_window() -> None:
    if sys.platform != "win32" or ctypes is None:
        return
    try:
        hwnd = ctypes.windll.kernel32.GetConsoleWindow()
        if hwnd:
            # 0 = SW_HIDE
            ctypes.windll.user32.ShowWindow(hwnd, 0)
    except Exception:
        pass


def _is_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _install(pip_spec: str) -> None:
    subprocess.run(
        [
            sys.executable,
            "-m",
            "pip",
            "install",
            pip_spec,
            "--quiet",
            "--disable-pip-version-check",
        ],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
        check=False,
    )


def ensure_dependencies() -> None:
    # In frozen builds, dependencies are bundled already.
    if getattr(sys, "frozen", False):
        return

    missing = [spec for name, spec in REQUIREMENTS if not _is_installed(name)]
    for spec in missing:
        _install(spec)


def _consume_option(option: str) -> str | None:
    """Consume '--option value' or '--option=value' from sys.argv."""
    value: str | None = None
    kept = [sys.argv[0]]
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg == option:
            if i + 1 < len(sys.argv):
                value = sys.argv[i + 1]
                i += 2
                continue
            i += 1
            continue
        if arg.startswith(option + "="):
            value = arg.split("=", 1)[1]
            i += 1
            continue
        kept.append(arg)
        i += 1
    sys.argv = kept
    return value


def _resource_root() -> Path:
    meipass = getattr(sys, "_MEIPASS", None)
    if meipass:
        return Path(meipass)
    return Path(__file__).resolve().parent


def _resolve_assets_dir(resource_root: Path, data_dir: Path) -> Path:
    candidates = [
        resource_root / "assets",
        resource_root / "casehugauto" / "assets",
        data_dir / "assets",
    ]
    for candidate in candidates:
        if candidate.exists() and candidate.is_dir():
            return candidate

    fallback = data_dir / "assets"
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def main() -> int:
    if "--show-console" not in sys.argv:
        _hide_console_window()

    data_dir_arg = _consume_option("--data-dir")
    data_dir = resolve_data_dir(data_dir_arg)
    os.environ[DATA_DIR_ENV] = str(data_dir)

    ensure_runtime_dirs(data_dir)

    # Keep logs folder bounded in size by deleting old entries.
    retention_raw = os.getenv("CASEHUGAUTO_LOG_RETENTION_DAYS", "7").strip()
    try:
        retention_days = max(1, int(retention_raw))
    except Exception:
        retention_days = 7
    try:
        cleanup_old_logs(data_dir / "logs", retention_days=retention_days)
    except Exception:
        pass

    os.chdir(data_dir)

    ensure_dependencies()

    if "--worker" in sys.argv:
        from casehugauto.background_worker import run_background_worker

        return run_background_worker()

    import flet as ft
    from casehugauto.app import main as app_main

    resource_root = _resource_root()
    assets_dir = _resolve_assets_dir(resource_root, data_dir)
    ft.app(target=app_main, assets_dir=str(assets_dir))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
