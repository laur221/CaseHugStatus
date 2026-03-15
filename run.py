#!/usr/bin/env python3
"""
CaseHugAuto - Automated Case Opening for casehug.com
Main entry point for the application
"""

import sys
import os
import subprocess
import importlib.util


# ------------------------------------------------------------------ #
#  DEPENDENCIES — (import_name, pip_spec)                            #
# ------------------------------------------------------------------ #
REQUIREMENTS = [
    ("sqlalchemy",              "sqlalchemy==2.0.25"),
    ("psycopg2",                "psycopg2-binary>=2.9.9"),
    ("qrcode",                  "qrcode==7.4.2"),
    ("PIL",                     "pillow>=10.4.0"),
    ("nodriver",                "nodriver>=0.35"),
    ("selenium",                "selenium>=4.0.0"),
    ("undetected_chromedriver", "undetected-chromedriver>=3.5.0"),
    ("requests",                "requests>=2.28.0"),
    ("psutil",                  "psutil>=5.9.0"),
]

_NO_WINDOW = subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0


def _is_installed(import_name: str) -> bool:
    return importlib.util.find_spec(import_name) is not None


def _install(pip_spec: str):
    subprocess.run(
        [sys.executable, "-m", "pip", "install", pip_spec,
        "--quiet", "--disable-pip-version-check"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )


def ensure_dependencies():
    missing = [spec for name, spec in REQUIREMENTS if not _is_installed(name)]
    for spec in missing:
        _install(spec)


# ------------------------------------------------------------------ #
#  MAIN                                                               #
# ------------------------------------------------------------------ #
if __name__ == "__main__":
    ensure_dependencies()

    import flet as ft
    from casehugauto.app import main

    ft.app(target=main, assets_dir="assets")