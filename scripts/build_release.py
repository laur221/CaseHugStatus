#!/usr/bin/env python3
"""Build CaseHugAuto release artifacts.

Creates:
- dist/CaseHugAuto.exe (PyInstaller one-file)
- dist/installer/CaseHugAuto-Setup.exe (if Inno Setup is installed)
"""

from __future__ import annotations


import argparse
import os
from pathlib import Path
import shutil
import subprocess
import sys


def run(cmd: list[str], cwd: Path) -> None:
    print("$", " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True)


def to_windows_path(path: Path) -> str:
    """Convert /mnt/* path to Windows path when running from WSL."""
    if os.name == "nt":
        return str(path)

    wslpath = shutil.which("wslpath")
    if not wslpath:
        return str(path)

    return subprocess.check_output([wslpath, "-w", str(path)], text=True).strip()


def find_iscc() -> Path | None:
    candidates: list[Path] = []

    # Standard Windows install locations.
    program_files_x86 = os.environ.get("ProgramFiles(x86)", "")
    program_files = os.environ.get("ProgramFiles", "")
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if program_files_x86:
        candidates.append(Path(program_files_x86) / "Inno Setup 6" / "ISCC.exe")
    if program_files:
        candidates.append(Path(program_files) / "Inno Setup 6" / "ISCC.exe")
    if local_app_data:
        candidates.append(Path(local_app_data) / "Programs" / "Inno Setup 6" / "ISCC.exe")

    # PATH lookup (works when ISCC is registered in PATH).
    path_hit = shutil.which("ISCC.exe")
    if path_hit:
        candidates.append(Path(path_hit))

    # WSL fallback when Windows-side env vars are not exported.
    user_name = os.environ.get("USERNAME") or os.environ.get("USER")
    if user_name:
        candidates.append(
            Path("/mnt/c/Users") / user_name / "AppData" / "Local" / "Programs" / "Inno Setup 6" / "ISCC.exe"
        )

    for candidate in candidates:
        if candidate.exists():
            return candidate
    return None


def main() -> int:
    parser = argparse.ArgumentParser(description="Build CaseHugAuto release")
    parser.add_argument("--skip-installer", action="store_true", help="Build exe only")
    parser.add_argument(
        "--python",
        default=sys.executable,
        help="Python interpreter to use for build (default: current)",
    )
    args = parser.parse_args()

    root = Path(__file__).resolve().parents[1]

    for dirname in ("build", "dist"):
        target = root / dirname
        if target.exists():
            shutil.rmtree(target)

    run([args.python, "-m", "pip", "install", "--upgrade", "pip"], root)
    run([args.python, "-m", "pip", "install", "-r", "requirements.txt"], root)
    run([args.python, "-m", "pip", "install", "pyinstaller"], root)

    run(
        [args.python, "-m", "PyInstaller", "--clean", "--noconfirm", "casehugauto.spec"],
        root,
    )

    exe_path = root / "dist" / "CaseHugAuto.exe"
    if not exe_path.exists():
        raise FileNotFoundError(f"Expected executable not found: {exe_path}")

    print(f"[OK] EXE built: {exe_path}")

    if args.skip_installer:
        print("[SKIP] Installer build skipped (--skip-installer).")
        return 0

    iscc = find_iscc()
    if not iscc:
        print("[WARN] Inno Setup ISCC.exe not found. Installer was not built.")
        print("       Install Inno Setup 6 and run this script again.")
        return 0

    iss_file = root / "installer" / "CaseHugAuto.iss"
    if not iss_file.exists():
        print(f"[WARN] Installer script not found: {iss_file}")
        print("       Create installer/CaseHugAuto.iss and run this script again.")
        return 0

    iss_arg = str(iss_file)
    if os.name != "nt" and str(iscc).lower().endswith(".exe"):
        iss_arg = to_windows_path(iss_file)

    run([str(iscc), iss_arg], root)

    installer_exe = root / "dist" / "installer" / "CaseHugAuto-Setup.exe"
    if installer_exe.exists():
        print(f"[OK] Installer built: {installer_exe}")
    else:
        print("[WARN] Installer command finished, but output file was not found.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
