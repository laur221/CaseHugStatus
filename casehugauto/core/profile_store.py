"""Helpers for per-account persistent browser profiles."""

from __future__ import annotations

import re
from pathlib import Path

PROFILE_ROOT = Path("profiles")


def slugify_account_name(account_name: str) -> str:
    normalized = re.sub(r"[^a-zA-Z0-9._-]+", "_", account_name.strip())
    normalized = normalized.strip("._-")
    return normalized or "account"


def get_profile_path(account_name: str) -> str:
    profile_dir = PROFILE_ROOT / slugify_account_name(account_name)
    return str(profile_dir.resolve())


def ensure_profile_path(account_name: str) -> str:
    profile_dir = Path(get_profile_path(account_name))
    profile_dir.mkdir(parents=True, exist_ok=True)
    return str(profile_dir)
