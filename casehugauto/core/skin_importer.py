"""Manual and automated skin sync helpers."""

from __future__ import annotations

from datetime import datetime
import html
import logging
import os
import re
import time
from typing import Any

from sqlalchemy.orm import Session

from ..database.crud import SkinCRUD
from .rarity import rarity_from_color

logger = logging.getLogger(__name__)

_CARD_SPLIT_TOKEN = 'data-testid="skin-card"'
_LOGIN_HINTS = (
    "steam login",
    "log in to open cases for free",
    "data-testid=\"login-steam-button\"",
)
_CLOUDFLARE_HINTS = (
    "checking your browser",
    "just a moment",
    "cloudflare",
    "turnstile",
)


def _text(pattern: str, chunk: str, flags: int = re.IGNORECASE) -> str:
    match = re.search(pattern, chunk, flags)
    if not match:
        return ""
    return html.unescape((match.group(1) or "").strip())


def _parse_obtained_datetime(date_raw: str, time_raw: str) -> datetime:
    date_raw = (date_raw or "").strip()
    time_raw = (time_raw or "").strip()
    if date_raw and time_raw:
        for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M"):
            try:
                return datetime.strptime(f"{date_raw} {time_raw}", fmt)
            except Exception:
                continue
    return datetime.utcnow()


def _parse_price(value: str) -> float:
    try:
        return float(re.sub(r"[^\d.]", "", str(value or "")))
    except Exception:
        return 0.0


def _normalize_item_id(value: str | None) -> str | None:
    normalized = str(value or "").strip()
    return normalized or None


def parse_casehug_skins_html(page_html: str) -> list[dict[str, Any]]:
    """Parse casehug /user-account HTML into normalized skin rows.

    Includes all visible cards, deduplicated by item_id/signature.
    """
    raw = str(page_html or "")
    if not raw:
        return []

    chunks = raw.split(_CARD_SPLIT_TOKEN)
    if len(chunks) <= 1:
        return []

    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for chunk in chunks[1:]:
        # Keep parser bounded for speed and to avoid crossing too many cards.
        block = chunk[:20000]

        skin_name = _text(r'data-testid="your-drop-name"[^>]*>([^<]+)<', block)
        skin_category = _text(r'data-testid="your-drop-category"[^>]*>([^<]+)<', block)
        price_text = _text(r'data-testid="your-drop-price"[^>]*>([^<]+)<', block)
        if not skin_name or not skin_category or not price_text:
            continue

        case_source = _text(r'data-testid="your-drops-hover-date"[^>]*>([^<]+)<', block).lower() or "unknown"
        obtained_date_raw = _text(
            r'data-testid="your-drops-hover-date"[^>]*>[^<]*</div>\s*<div>([^<]+)</div>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )
        obtained_time_raw = _text(
            r'data-testid="your-drops-hover-is-drawn"[^>]*>\s*<div>[^<]*</div>\s*<div>([^<]+)</div>',
            block,
            flags=re.IGNORECASE | re.DOTALL,
        )

        condition = _text(r'data-testid="your-drop-card-condition"[^>]*>([^<]+)<', block).upper() or None
        item_id = _normalize_item_id(_text(r'(?:/upgrader\?item=|/skin-changer\?item=)(\d+)', block))
        image_url = _text(r'data-testid="your-drop-skin-image"[^>]+src="([^"]+)"', block) or None

        rarity_color = _text(
            r'stop\s+offset="40%"\s+stop-color="(#[0-9A-Fa-f]{6})"',
            block,
        )
        rarity_label = rarity_from_color(rarity_color) or "Unknown"

        is_new_label = _text(r'data-testid="your-drop-card-label"[^>]*>([^<]+)<', block).lower()
        is_new = is_new_label == "new"

        obtained_dt = _parse_obtained_datetime(obtained_date_raw, obtained_time_raw)
        skin_full_name = f"{skin_name} | {skin_category}".strip()
        signature = item_id or "|".join(
            [
                case_source,
                skin_full_name.lower(),
                str(round(_parse_price(price_text), 4)),
                obtained_dt.strftime("%Y-%m-%d %H:%M:%S"),
            ]
        )
        if signature in seen:
            continue
        seen.add(signature)

        out.append(
            {
                "skin_name": skin_full_name,
                "external_item_id": item_id,
                "estimated_price": _parse_price(price_text),
                "case_source": case_source,
                "rarity": rarity_label,
                "condition": condition,
                "skin_image_url": image_url,
                "obtained_date": obtained_dt,
                "is_new": is_new,
            }
        )

    out.sort(key=lambda row: row.get("obtained_date") or datetime.utcnow(), reverse=True)
    return out


def sync_skins_from_html(
    db: Session,
    account_id: int,
    page_html: str,
    *,
    delete_missing: bool,
) -> dict[str, Any]:
    """Sync account skins from a CaseHug HTML snapshot.

    - Upserts current skins from snapshot.
    - Optionally deletes DB skins missing from snapshot.
    """
    parsed_rows = parse_casehug_skins_html(page_html)

    if not parsed_rows:
        return {
            "imported": False,
            "message": "No skin cards found in provided HTML. Open casehug.com/user-account and copy the cards HTML.",
            "parsed": 0,
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
        }

    created = 0
    updated = 0
    skipped = 0
    snapshot_item_ids: set[str] = set()
    snapshot_signatures: set[str] = set()

    for row in parsed_rows:
        skin_name = str(row.get("skin_name") or "").strip()
        if not skin_name:
            skipped += 1
            continue

        item_id = _normalize_item_id(row.get("external_item_id"))
        if item_id:
            snapshot_item_ids.add(item_id)

        signature = SkinCRUD.snapshot_signature(
            skin_name=skin_name,
            case_source=row.get("case_source"),
            estimated_price=row.get("estimated_price"),
            obtained_date=row.get("obtained_date"),
        )
        snapshot_signatures.add(signature)

        _, was_created = SkinCRUD.upsert_imported(
            db,
            account_id=account_id,
            skin_name=skin_name,
            external_item_id=item_id,
            estimated_price=row.get("estimated_price"),
            case_source=row.get("case_source"),
            rarity=row.get("rarity"),
            condition=row.get("condition"),
            skin_image_url=row.get("skin_image_url"),
            obtained_date=row.get("obtained_date"),
            is_new=bool(row.get("is_new", False)),
        )
        if was_created:
            created += 1
        else:
            updated += 1

    deleted = 0
    if delete_missing:
        deleted = SkinCRUD.delete_missing_from_snapshot(
            db,
            account_id,
            item_ids=snapshot_item_ids,
            signatures=snapshot_signatures,
        )

    return {
        "imported": True,
        "message": "Sync completed successfully." if delete_missing else "Import completed successfully.",
        "parsed": len(parsed_rows),
        "created": created,
        "updated": updated,
        "deleted": deleted,
        "skipped": skipped,
    }


def import_skins_from_html(db: Session, account_id: int, page_html: str) -> dict[str, Any]:
    """Import skins from copied CaseHug HTML into DB (non-destructive)."""
    return sync_skins_from_html(
        db,
        account_id,
        page_html,
        delete_missing=False,
    )


def fetch_user_account_html_with_profile(
    profile_path: str,
    timeout_seconds: int = 45,
) -> tuple[bool, str, str]:
    """Open casehug.com/user-account with account profile and return page HTML."""
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options as ChromeOptions
    from selenium.webdriver.chrome.service import Service as ChromeService

    normalized_profile = str(profile_path or "").strip()
    if not normalized_profile:
        return False, "Missing browser profile path for this account.", ""

    os.makedirs(normalized_profile, exist_ok=True)

    options = ChromeOptions()
    options.add_argument(f"--user-data-dir={normalized_profile}")
    options.add_argument("--headless=new")
    options.add_argument("--window-size=1920,1080")
    options.add_argument("--window-position=-32000,-32000")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-component-update")
    options.add_argument("--disable-sync")
    options.add_argument("--log-level=3")
    options.add_experimental_option("excludeSwitches", ["enable-logging"])

    driver = None
    try:
        driver = webdriver.Chrome(options=options, service=ChromeService(log_output=os.devnull))
        driver.set_page_load_timeout(max(20, int(timeout_seconds)))
        driver.get("https://casehug.com/user-account")

        deadline = time.time() + max(12, int(timeout_seconds))
        last_html = ""
        while time.time() < deadline:
            page_html = str(driver.page_source or "")
            if page_html:
                last_html = page_html

            if _CARD_SPLIT_TOKEN in page_html:
                return True, "Snapshot fetched.", page_html

            lower = page_html.lower()
            if any(token in lower for token in _LOGIN_HINTS):
                return False, "Steam session is not authenticated in this browser profile. Please sign in once and retry.", page_html

            if any(token in lower for token in _CLOUDFLARE_HINTS):
                time.sleep(1.0)
                continue

            time.sleep(0.8)

        if last_html:
            return False, "Could not detect skin cards on user-account page.", last_html
        return False, "Could not fetch user-account page HTML.", ""
    except Exception as exc:
        return False, f"Could not open profile browser for sync: {exc}", ""
    finally:
        if driver:
            try:
                driver.quit()
            except Exception:
                pass


def sync_skins_from_site(
    db: Session,
    account_id: int,
    profile_path: str,
) -> dict[str, Any]:
    """Sync skins directly from casehug.com/user-account for one account profile."""
    ok, message, page_html = fetch_user_account_html_with_profile(profile_path)
    if not ok:
        return {
            "imported": False,
            "message": message,
            "parsed": 0,
            "created": 0,
            "updated": 0,
            "deleted": 0,
            "skipped": 0,
        }

    report = sync_skins_from_html(
        db,
        account_id,
        page_html,
        delete_missing=True,
    )
    if report.get("imported"):
        report["message"] = "Sync completed successfully from website snapshot."
    return report
