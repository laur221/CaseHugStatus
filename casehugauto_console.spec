# PyInstaller console-debug spec for CaseHugAuto

import os

block_cipher = None
project_dir = os.path.dirname(os.path.abspath(SPEC))

a = Analysis(
    [os.path.join(project_dir, "run.py")],
    pathex=[project_dir],
    binaries=[],
    datas=[
        (os.path.join(project_dir, "casehugauto"), "casehugauto"),
        (os.path.join(project_dir, "profiles"), "profiles"),
        (os.path.join(project_dir, ".env"), "."),
        (os.path.join(project_dir, ".env.example"), "."),
    ],
    hiddenimports=[
        "flet",
        "sqlalchemy",
        "psycopg",
        "psycopg_binary",
        "psycopg2",
        "qrcode",
        "nodriver",
        "PIL",
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludedimports=[],
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
    name="CaseHugAutoConsole",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=True,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name="CaseHugAutoConsole",
)
