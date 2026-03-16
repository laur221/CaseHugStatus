from __future__ import annotations

import os
from pathlib import Path
import sys
from typing import Tuple

STARTUP_SCRIPT_NAME = "CaseHugAutoBackground.vbs"
LEGACY_STARTUP_SCRIPT_NAME = "CaseHugAutoBackground.cmd"
DATA_DIR_ENV = "CASEHUGAUTO_HOME"


def is_windows_platform() -> bool:
    return os.name == "nt" or sys.platform.startswith("win")


def _is_frozen_app() -> bool:
    return bool(getattr(sys, "frozen", False))


def _startup_folder() -> Path:
    appdata = os.getenv("APPDATA", "").strip()
    if appdata:
        return (
            Path(appdata)
            / "Microsoft"
            / "Windows"
            / "Start Menu"
            / "Programs"
            / "Startup"
        )
    return (
        Path.home()
        / "AppData"
        / "Roaming"
        / "Microsoft"
        / "Windows"
        / "Start Menu"
        / "Programs"
        / "Startup"
    )


def _project_root() -> Path:
    if _is_frozen_app():
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parents[2]


def _python_background_executable() -> Path:
    executable = Path(sys.executable)
    if executable.name.lower() == "python.exe":
        pythonw = executable.with_name("pythonw.exe")
        if pythonw.exists():
            return pythonw
    return executable


def _startup_script_path() -> Path:
    return _startup_folder() / STARTUP_SCRIPT_NAME


def _legacy_startup_script_path() -> Path:
    return _startup_folder() / LEGACY_STARTUP_SCRIPT_NAME


def _escape_vbs(value: str) -> str:
    return value.replace('"', '""')


def _data_dir_from_env() -> str:
    return os.getenv(DATA_DIR_ENV, "").strip()


def _startup_command() -> str:
    if _is_frozen_app():
        command_parts = [str(Path(sys.executable).resolve()), "--worker"]
    else:
        root = _project_root()
        python_exec = _python_background_executable()
        run_py = root / "run.py"
        command_parts = [str(python_exec), str(run_py), "--worker"]

    data_dir = _data_dir_from_env()
    if data_dir:
        command_parts.extend(["--data-dir", data_dir])

    # Quote all arguments for safe execution through WScript.Shell.Run
    return " ".join(f'"{_escape_vbs(part)}"' for part in command_parts)


def _script_content() -> str:
    root = _project_root()
    command = _startup_command()
    return (
        'Set WshShell = CreateObject("WScript.Shell")\n'
        f'WshShell.CurrentDirectory = "{_escape_vbs(str(root))}"\n'
        f'WshShell.Run "{command}", 0, False\n'
    )


def is_background_startup_enabled() -> bool:
    if not is_windows_platform():
        return False
    return _startup_script_path().exists() or _legacy_startup_script_path().exists()


def has_legacy_background_startup() -> bool:
    if not is_windows_platform():
        return False
    return _legacy_startup_script_path().exists()


def enable_background_startup() -> Tuple[bool, str]:
    if not is_windows_platform():
        return False, "Windows startup is supported only on Windows."

    try:
        startup_folder = _startup_folder()
        startup_folder.mkdir(parents=True, exist_ok=True)

        script_path = _startup_script_path()
        script_path.write_text(_script_content(), encoding="utf-8")

        legacy_path = _legacy_startup_script_path()
        if legacy_path.exists():
            legacy_path.unlink()

        return True, f"Windows startup enabled: {script_path}"
    except Exception as exc:
        return False, f"Could not enable Windows startup: {exc}"


def disable_background_startup() -> Tuple[bool, str]:
    if not is_windows_platform():
        return False, "Windows startup is supported only on Windows."

    try:
        removed = []
        for script_path in (_startup_script_path(), _legacy_startup_script_path()):
            if script_path.exists():
                script_path.unlink()
                removed.append(str(script_path))

        if removed:
            return True, "Windows startup disabled."
        return True, "Windows startup already disabled."
    except Exception as exc:
        return False, f"Could not disable Windows startup: {exc}"
