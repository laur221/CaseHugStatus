"""Shared runtime data-directory helpers."""

from __future__ import annotations

from pathlib import Path
import os
import shutil
import time
from typing import Optional, Tuple

APP_NAME = "CaseHugAuto"
DATA_DIR_ENV = "CASEHUGAUTO_HOME"
DATA_DIR_OVERRIDE_FILENAME = "data_dir_override.txt"


def default_data_dir() -> Path:
    if os.name == "nt":
        appdata = os.getenv("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME

    if os.sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    xdg_data_home = os.getenv("XDG_DATA_HOME", "").strip()
    if xdg_data_home:
        return Path(xdg_data_home) / APP_NAME
    return Path.home() / ".local" / "share" / APP_NAME


def _override_anchor_dir() -> Path:
    # Keep the override marker in a stable location so we can discover
    # the chosen data directory before runtime chdir happens.
    if os.name == "nt":
        appdata = os.getenv("APPDATA", "").strip()
        if appdata:
            return Path(appdata) / APP_NAME
        return Path.home() / "AppData" / "Roaming" / APP_NAME
    return default_data_dir()


def data_dir_override_file() -> Path:
    return _override_anchor_dir() / DATA_DIR_OVERRIDE_FILENAME


def read_data_dir_override() -> Optional[Path]:
    marker = data_dir_override_file()
    if not marker.exists():
        return None

    try:
        raw = marker.read_text(encoding="utf-8").strip()
    except Exception:
        return None
    if not raw:
        return None

    try:
        return Path(raw).expanduser().resolve()
    except Exception:
        return None


def resolve_data_dir(cli_value: str | None = None) -> Path:
    if cli_value and str(cli_value).strip():
        return Path(str(cli_value).strip()).expanduser().resolve()

    env_value = os.getenv(DATA_DIR_ENV, "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()

    override = read_data_dir_override()
    if override is not None:
        return override

    return default_data_dir().resolve()


def current_data_dir() -> Path:
    env_value = os.getenv(DATA_DIR_ENV, "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()
    return resolve_data_dir()


def ensure_runtime_dirs(data_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    for dirname in ("logs", "profiles", "temp_qr_codes"):
        (data_dir / dirname).mkdir(parents=True, exist_ok=True)


def cleanup_old_logs(logs_dir: Optional[Path] = None, retention_days: int = 7) -> Tuple[int, int]:
    """Delete log files older than retention_days and prune empty log folders."""
    try:
        days = int(retention_days)
    except Exception:
        days = 7
    days = max(1, days)

    root = (logs_dir or (current_data_dir() / "logs")).expanduser().resolve()
    if not root.exists() or not root.is_dir():
        return 0, 0

    cutoff_ts = time.time() - (days * 24 * 60 * 60)
    removed_files = 0
    removed_dirs = 0

    for path in sorted(root.rglob("*"), key=lambda p: len(p.parts), reverse=True):
        if not path.exists():
            continue

        if path.is_file():
            try:
                if path.stat().st_mtime < cutoff_ts:
                    path.unlink()
                    removed_files += 1
            except Exception:
                continue
            continue

        if path.is_dir():
            try:
                if not any(path.iterdir()):
                    path.rmdir()
                    removed_dirs += 1
            except Exception:
                continue

    return removed_files, removed_dirs


def _write_data_dir_override(target_dir: Path) -> Tuple[bool, str]:
    marker = data_dir_override_file()
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(target_dir.resolve()), encoding="utf-8")
        return True, "Data directory override saved."
    except Exception as exc:
        return False, f"Could not save data directory override: {exc}"


def _copy_tree_contents(src_dir: Path, dst_dir: Path) -> None:
    if not src_dir.exists() or not src_dir.is_dir():
        return

    for item in src_dir.iterdir():
        destination = dst_dir / item.name
        if item.is_dir():
            shutil.copytree(item, destination, dirs_exist_ok=True)
        else:
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(item, destination)


def apply_data_dir_change(new_dir: str, source_dir: Optional[Path] = None) -> Tuple[bool, str, Path]:
    candidate = str(new_dir or "").strip()
    source = (source_dir or current_data_dir()).expanduser().resolve()

    if not candidate:
        return False, "Data folder path cannot be empty.", source

    target = Path(candidate).expanduser().resolve()

    if target == source:
        return True, "Data folder is already set to this location.", target

    try:
        source.relative_to(target)
        return False, "Invalid destination: source is inside destination.", source
    except Exception:
        pass
    try:
        target.relative_to(source)
        return False, "Invalid destination: destination is inside current data folder.", source
    except Exception:
        pass

    try:
        ensure_runtime_dirs(target)
        _copy_tree_contents(source, target)
    except Exception as exc:
        return False, f"Could not migrate data to new folder: {exc}", source

    ok, message = _write_data_dir_override(target)
    if not ok:
        return False, message, source

    os.environ[DATA_DIR_ENV] = str(target)
    return True, "Data folder changed. Restart the app to fully apply.", target
