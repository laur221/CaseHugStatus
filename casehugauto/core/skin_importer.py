"""Manual skin import helpers (incremental, no destructive delete)."""

from __future__ import annotations

from datetime import datetime
import html
import re
from typing import Any

from sqlalchemy.orm import Session

from ..database.crud import SkinCRUD
from .rarity import rarity_from_color


_CARD_SPLIT_TOKEN = 'data-testid="skin-card"'


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


def parse_casehug_skins_html(page_html: str) -> list[dict[str, Any]]:
    """Parse casehug /user-account HTML into normalized skin rows.

    Includes all visible cards (not only NEW), deduplicated by item_id/signature.
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
        item_id = _text(r'(?:/upgrader\?item=|/skin-changer\?item=)(\d+)', block) or None
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


def import_skins_from_html(db: Session, account_id: int, page_html: str) -> dict[str, Any]:
    """Import skins from copied CaseHug HTML into DB.

    Non-destructive: does not delete existing rows; uses upsert to avoid duplicates.
    """
    parsed_rows = parse_casehug_skins_html(page_html)

    if not parsed_rows:
        return {
            "imported": False,
            "message": "No skin cards found in provided HTML. Open casehug.com/user-account and copy the cards HTML.",
            "parsed": 0,
            "created": 0,
            "updated": 0,
            "skipped": 0,
        }

    created = 0
    updated = 0
    skipped = 0

    for row in parsed_rows:
        skin_name = str(row.get("skin_name") or "").strip()
        if not skin_name:
            skipped += 1
            continue

        _, was_created = SkinCRUD.upsert_imported(
            db,
            account_id=account_id,
            skin_name=skin_name,
            external_item_id=row.get("external_item_id"),
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

    return {
        "imported": True,
        "message": "Import completed successfully.",
        "parsed": len(parsed_rows),
        "created": created,
        "updated": updated,
        "skipped": skipped,
    }
