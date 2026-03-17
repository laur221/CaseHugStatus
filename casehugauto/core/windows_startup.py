from __future__ import annotations

import os
from pathlib import Path
import subprocess
import sys
from typing import Tuple

STARTUP_SHORTCUT_NAME = "CaseHugAutoBackground.lnk"
LEGACY_STARTUP_SCRIPT_NAMES = (
    "CaseHugAutoBackground.vbs",
    "CaseHugAutoBackground.cmd",
)
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


def _startup_shortcut_path() -> Path:
    return _startup_folder() / STARTUP_SHORTCUT_NAME


def _legacy_startup_script_paths() -> Tuple[Path, ...]:
    startup_folder = _startup_folder()
    return tuple(startup_folder / name for name in LEGACY_STARTUP_SCRIPT_NAMES)


def _escape_powershell_single_quoted(value: str) -> str:
    return value.replace("'", "''")


def _data_dir_from_env() -> str:
    return os.getenv(DATA_DIR_ENV, "").strip()


def _startup_target_and_arguments() -> Tuple[str, str, str]:
    if _is_frozen_app():
        target_path = Path(sys.executable).resolve()
        arguments = ["--worker"]
        working_directory = target_path.parent
    else:
        root = _project_root()
        target_path = _python_background_executable()
        run_py = root / "run.py"
        arguments = [str(run_py), "--worker"]
        working_directory = root

    data_dir = _data_dir_from_env()
    if data_dir:
        arguments.extend(["--data-dir", data_dir])

    return str(target_path), subprocess.list2cmdline(arguments), str(working_directory)


def _create_startup_shortcut(
    shortcut_path: Path,
    target_path: str,
    arguments: str,
    working_directory: str,
) -> Tuple[bool, str]:
    ps_script = (
        "$WshShell = New-Object -ComObject WScript.Shell\n"
        f"$Shortcut = $WshShell.CreateShortcut('{_escape_powershell_single_quoted(str(shortcut_path))}')\n"
        f"$Shortcut.TargetPath = '{_escape_powershell_single_quoted(target_path)}'\n"
        f"$Shortcut.Arguments = '{_escape_powershell_single_quoted(arguments)}'\n"
        f"$Shortcut.WorkingDirectory = '{_escape_powershell_single_quoted(working_directory)}'\n"
        "$Shortcut.WindowStyle = 7\n"
        f"$Shortcut.IconLocation = '{_escape_powershell_single_quoted(target_path)},0'\n"
        "$Shortcut.Save()\n"
    )

    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            ps_script,
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode != 0:
        error_output = (result.stderr or result.stdout or "").strip()
        return False, error_output or "PowerShell could not create startup shortcut."
    return True, ""


def is_background_startup_enabled() -> bool:
    if not is_windows_platform():
        return False
    return _startup_shortcut_path().exists() or any(
        path.exists() for path in _legacy_startup_script_paths()
    )


def has_legacy_background_startup() -> bool:
    if not is_windows_platform():
        return False
    return any(path.exists() for path in _legacy_startup_script_paths())


def enable_background_startup() -> Tuple[bool, str]:
    if not is_windows_platform():
        return False, "Windows startup is supported only on Windows."

    try:
        startup_folder = _startup_folder()
        startup_folder.mkdir(parents=True, exist_ok=True)

        shortcut_path = _startup_shortcut_path()
        target_path, arguments, working_directory = _startup_target_and_arguments()
        ok, error_message = _create_startup_shortcut(
            shortcut_path=shortcut_path,
            target_path=target_path,
            arguments=arguments,
            working_directory=working_directory,
        )
        if not ok:
            return False, f"Could not enable Windows startup: {error_message}"

        for legacy_path in _legacy_startup_script_paths():
            if legacy_path.exists():
                legacy_path.unlink()

        return True, f"Windows startup enabled: {shortcut_path}"
    except Exception as exc:
        return False, f"Could not enable Windows startup: {exc}"


def disable_background_startup() -> Tuple[bool, str]:
    if not is_windows_platform():
        return False, "Windows startup is supported only on Windows."

    try:
        removed = []
        for script_path in (_startup_shortcut_path(), *_legacy_startup_script_paths()):
            if script_path.exists():
                script_path.unlink()
                removed.append(str(script_path))

        if removed:
            return True, "Windows startup disabled."
        return True, "Windows startup already disabled."
    except Exception as exc:
        return False, f"Could not disable Windows startup: {exc}"
