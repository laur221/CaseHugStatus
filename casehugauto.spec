# casehugauto.spec
import sys
from PyInstaller.utils.hooks import collect_submodules, collect_data_files

block_cipher = None

# Colectează submodulele necesare
hidden_imports = (
    collect_submodules("flet") +
    collect_submodules("sqlalchemy") +
    collect_submodules("casehugauto") +
    [
        "casehugauto.app",
        "casehugauto.core.bot_logic",
        "casehugauto.core.bot_runner",
        "casehugauto.core.steam_login_launcher",
        "casehugauto.core.steam_client",
        "casehugauto.core.profile_importer",
        "casehugauto.core.profile_store",
        "casehugauto.database.db",
        "casehugauto.database.crud",
        "casehugauto.models.models",
        "casehugauto.ui.pages.home",
        "casehugauto.ui.pages.accounts",
        "casehugauto.ui.pages.settings",
        "casehugauto.ui.pages.skins",
        "casehugauto.ui.components.steam_login_dialog",
        "casehugauto.ui.components.steam_login_qr_dialog",
        "casehugauto.ui.components.db_connection_dialog",
        "casehugauto.ui.components.database_connection",
        "importlib.util",
        "subprocess",
        "asyncio",
        "threading",
        "sqlite3",
        "json",
        "re",
    ]
)

datas = (
    collect_data_files("flet") +
    [
        ("casehugauto/assets", "casehugauto/assets"),
    ]
)

a = Analysis(
    ["run.py"],                     # Entry point = run.py
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=hidden_imports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        # Excludem librăriile grele — se instalează la runtime
        "nodriver",
        "selenium",
        "undetected_chromedriver",
        "psycopg2",
        "qrcode",
    ],
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
    name="CasehugAuto",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,          # Fără consolă vizibilă
    disable_windowed_traceback=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
    icon="casehugauto/assets/icon.ico",  # Schimbă cu iconița ta
)