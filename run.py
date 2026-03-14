#!/usr/bin/env python3
"""
CaseHugAuto - Automated Case Opening for casehug.com
Main entry point for the application
"""

import flet as ft
from casehugauto.app import main

if __name__ == "__main__":
    ft.app(target=main, assets_dir="assets")
