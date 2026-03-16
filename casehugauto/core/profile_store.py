"""Helpers for per-account persistent browser profiles."""

from __future__ import annotations

import os
import re
import shutil
from pathlib import Path
from typing import Optional, Tuple

from .data_paths import current_data_dir

PROFILE_DIR_ENV = "CASEHUGAUTO_PROFILES_DIR"
PROFILE_DIR_OVERRIDE_FILENAME = "profiles_dir_override.txt"
DEFAULT_PROFILE_DIRNAME = "profiles"


def slugify_account_name(account_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", account_name.strip())
    normalized = normalized.strip("._-")
    return normalized or "account"


def default_profile_root() -> Path:
    return (current_data_dir() / DEFAULT_PROFILE_DIRNAME).resolve()


def profile_root_override_file() -> Path:
    return current_data_dir() / PROFILE_DIR_OVERRIDE_FILENAME


def read_profile_root_override() -> Optional[Path]:
    marker = profile_root_override_file()
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


def resolve_profile_root(cli_value: str | None = None) -> Path:
    if cli_value and str(cli_value).strip():
        return Path(str(cli_value).strip()).expanduser().resolve()

    env_value = os.getenv(PROFILE_DIR_ENV, "").strip()
    if env_value:
        return Path(env_value).expanduser().resolve()

    override = read_profile_root_override()
    if override is not None:
        return override

    return default_profile_root()


def get_profile_root() -> Path:
    root = resolve_profile_root()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_profile_path(account_name: str) -> str:
    profile_dir = get_profile_root() / slugify_account_name(account_name)
    return str(profile_dir.resolve())


def ensure_profile_path(account_name: str) -> str:
    profile_dir = Path(get_profile_path(account_name))
    profile_dir.mkdir(parents=True, exist_ok=True)
    return str(profile_dir.resolve())


def get_pending_add_root() -> Path:
    pending_root = get_profile_root() / "_pending_add"
    pending_root.mkdir(parents=True, exist_ok=True)
    return pending_root


def _write_profile_root_override(target_dir: Path) -> Tuple[bool, str]:
    marker = profile_root_override_file()
    try:
        marker.parent.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(target_dir.resolve()), encoding="utf-8")
        return True, "Profile folder override saved."
    except Exception as exc:
        return False, f"Could not save profile folder override: {exc}"


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


def apply_profile_root_change(
    new_dir: str,
    source_root: Optional[Path] = None,
) -> Tuple[bool, str, Path]:
    candidate = str(new_dir or "").strip()
    source = (source_root or resolve_profile_root()).expanduser().resolve()

    if not candidate:
        return False, "Profiles folder path cannot be empty.", source

    target = Path(candidate).expanduser().resolve()

    if target == source:
        return True, "Profiles folder is already set to this location.", target

    try:
        source.relative_to(target)
        return False, "Invalid destination: source is inside destination.", source
    except Exception:
        pass

    try:
        target.relative_to(source)
        return False, "Invalid destination: destination is inside source.", source
    except Exception:
        pass

    try:
        target.mkdir(parents=True, exist_ok=True)
        _copy_tree_contents(source, target)
    except Exception as exc:
        return False, f"Could not migrate profiles to new folder: {exc}", source

    ok, message = _write_profile_root_override(target)
    if not ok:
        return False, message, source

    os.environ[PROFILE_DIR_ENV] = str(target)
    return (
        True,
        "Profiles folder changed. Existing profiles were copied. Restart active bots to use the new path.",
        target,
    )
