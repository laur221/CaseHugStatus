# -*- mode: python ; coding: utf-8 -*-
"""Release spec for CaseHugAuto.

Build command:
  pyinstaller --clean --noconfirm casehugauto.spec
"""

from PyInstaller.utils.hooks import collect_data_files, collect_submodules

block_cipher = None

hidden_imports = (
    collect_submodules("flet")
    + collect_submodules("sqlalchemy")
    + collect_submodules("casehugauto")
    + [
        "psycopg2",
        "psycopg2.extensions",
        "psycopg2.extras",
        "nodriver",
        "selenium",
        "undetected_chromedriver",
        "qrcode",
        "PIL",
        "PIL.Image",
        "pystray",
        "pystray._win32",
    ]
)

datas = (
    collect_data_files("flet")
    + collect_data_files("casehugauto", includes=["assets/**/*"])
    + [
        ("README.md", "."),
        ("config.example.json", "."),
        (".env.example", "."),
    ]
)

a = Analysis(
    ["run.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.zipfiles,
    a.datas,
    [],
    name="CaseHugAuto",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    icon="casehugauto/assets/casehugauto_icon.ico",
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
