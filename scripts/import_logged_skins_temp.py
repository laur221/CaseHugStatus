"""
Temporary utility: import all skins from currently logged-in CaseHug accounts.

How it works:
1. Reads accounts from PostgreSQL.
2. Opens each account's persistent Chrome profile.
3. If account is still logged in on casehug.com, scrapes all visible/infinite-scroll skins.
4. Saves them in DB.

Examples:
  python scripts/import_logged_skins_temp.py --dry-run
  python scripts/import_logged_skins_temp.py --replace-existing
  python scripts/import_logged_skins_temp.py --account-id 18 --replace-existing
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import re
import sys
import threading
import time
from dataclasses import dataclass
from datetime import datetime, UTC
from pathlib import Path

import nodriver as uc

# Allow running this temporary script directly via "python scripts/....py".
PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

from casehugauto.core.bot_logic import (
    AutomationLogic,
    _apply_nodriver_websocket_compat_patch,
    _cleanup_stale_profile_locks,
    _kill_profile_chrome_processes,
)
from casehugauto.core.rarity import rarity_from_color
from casehugauto.core.profile_store import ensure_profile_path
from casehugauto.database.crud import AccountCRUD
from casehugauto.database.db import SessionLocal, init_db
from casehugauto.models.models import Skin

logger = logging.getLogger("import_logged_skins_temp")

_CF_KEYWORDS = (
    "just a moment",
    "checking your browser",
    "cloudflare",
    "turnstile",
)

_JS_EXTRACT_DROPS = r"""
(() => {
  const txt = (el) => (el && el.textContent ? el.textContent.trim() : "");
  const toHex = (color) => {
    if (!color) return "";
    const c = String(color).trim();
    if (c.startsWith("#")) return c.toUpperCase();
    const m = c.match(/rgba?\(\s*(\d+)\s*,\s*(\d+)\s*,\s*(\d+)/i);
    if (!m) return "";
    const to2 = (n) => Math.max(0, Math.min(255, parseInt(n, 10))).toString(16).padStart(2, "0");
    return ("#" + to2(m[1]) + to2(m[2]) + to2(m[3])).toUpperCase();
  };

  const names = Array.from(document.querySelectorAll('[data-testid="your-drop-name"]'));
  const categoriesByIndex = Array.from(document.querySelectorAll('[data-testid="your-drop-category"]')).map(txt);
  const pricesByIndex = Array.from(document.querySelectorAll('[data-testid="your-drop-price"]')).map(txt);
  const casesByIndex = Array.from(document.querySelectorAll('[data-testid="your-drops-hover-date"]')).map(txt);
  const labelsByIndex = Array.from(document.querySelectorAll('[data-testid="your-drop-card-label"]')).map(txt);

  const out = [];
  for (let i = 0; i < names.length; i++) {
    const nameEl = names[i];

    // Use the full skin card to capture all fields (image/condition/category).
    let card = nameEl.closest ? nameEl.closest('[data-testid="skin-card"]') : null;
    if (!card) {
      // Fallback for older layouts without a reliable closest path.
      card = nameEl;
      for (let step = 0; step < 12 && card; step++) {
        if (card.querySelector && card.querySelector('[data-testid="your-drop-price"]')) {
          break;
        }
        card = card.parentElement;
      }
    }

    const q = (selector) => {
      if (card && card.querySelector) {
        const el = card.querySelector(selector);
        if (el) return txt(el);
      }
      return "";
    };

    const categoryEl = card && card.querySelector ? card.querySelector('[data-testid="your-drop-category"]') : null;
    const caseEl = card && card.querySelector ? card.querySelector('[data-testid="your-drops-hover-date"]') : null;
    const obtainedWrap = card && card.querySelector ? card.querySelector('[data-testid="your-drops-hover-is-drawn"]') : null;
    const upgraderHref = card && card.querySelector ? (card.querySelector('[data-testid="upgrader-button"]')?.getAttribute("href") || "") : "";
    const exchangeHref = card && card.querySelector ? (card.querySelector('[data-testid="exchange-button"]')?.getAttribute("href") || "") : "";
    const hrefForId = upgraderHref || exchangeHref || "";
    const itemMatch = hrefForId.match(/item=(\d+)/i);
    const img = card && card.querySelector ? card.querySelector('[data-testid="your-drop-skin-image"]') : null;
    const obtainedTime = obtainedWrap && obtainedWrap.children && obtainedWrap.children.length > 1
      ? txt(obtainedWrap.children[1])
      : "";
    const obtainedDate = caseEl && caseEl.nextElementSibling
      ? txt(caseEl.nextElementSibling)
      : "";
    out.push({
      index: i,
      name: txt(nameEl),
      category: q('[data-testid="your-drop-category"]') || categoriesByIndex[i] || "",
      price: q('[data-testid="your-drop-price"]') || pricesByIndex[i] || "",
      case_source: q('[data-testid="your-drops-hover-date"]') || casesByIndex[i] || "",
      obtained_time: obtainedTime,
      obtained_date: obtainedDate,
      item_id: itemMatch ? itemMatch[1] : "",
      condition: q('[data-testid="your-drop-card-condition"]') || "",
      label: q('[data-testid="your-drop-card-label"]') || labelsByIndex[i] || "",
      image_url: img ? (img.currentSrc || img.src || "") : "",
      category_color: categoryEl ? toHex(getComputedStyle(categoryEl).color) : "",
      rarity_color: (() => {
        const stop = card && card.querySelector ? card.querySelector('linearGradient stop[offset="40%"]') : null;
        return stop ? toHex(stop.getAttribute("stop-color") || "") : "";
      })(),
    });
  }
  return out;
})()
"""


def _parse_price(value: str) -> float:
    try:
        return float(re.sub(r"[^\d.]", "", value or ""))
    except Exception:
        return 0.0


@dataclass
class AccountImportResult:
    account_id: int
    account_name: str
    logged_in: bool
    scraped_count: int
    saved_count: int
    deleted_count: int
    error: str = ""


async def _wait_for_cloudflare(page, timeout_seconds: int = 45) -> bool:
    deadline = time.monotonic() + timeout_seconds
    while time.monotonic() < deadline:
        content = (await page.get_content()).lower()
        if not any(keyword in content for keyword in _CF_KEYWORDS):
            return True
        await asyncio.sleep(2)
    return False


async def _is_casehug_logged_in(page) -> bool:
    try:
        for selector in (
            '[data-testid="header-account-balance"]',
            'a[href="/user-account"]',
        ):
            try:
                node = await page.query_selector(selector)
                if node:
                    return True
            except Exception:
                continue

        unauth = await page.query_selector('[data-testid="header-un-auth-button"]')
        if unauth:
            return False

        content = (await page.get_content()).lower()
        return ('href="/user-account"' in content) and ("header-un-auth-button" not in content)
    except Exception:
        return False


async def _ensure_casehug_logged_in(page, account) -> bool:
    """
    Reuse the same Steam auto-login flow from main bot logic.
    This keeps script behavior identical to the app "Start" flow.
    """
    await page.get("https://casehug.com/free-cases")
    await asyncio.sleep(2.5)
    await _wait_for_cloudflare(page, timeout_seconds=35)

    if await _is_casehug_logged_in(page):
        return True

    db = SessionLocal()
    try:
        def _status_callback(acc_id: int, message: str, status: str):
            logger.info("[main-login:%s][%s] %s", acc_id, status, message)

        logic = AutomationLogic(
            db_session=db,
            account_id=account.id,
            stop_event=threading.Event(),
            status_callback=_status_callback,
        )
        # Rebind to current account/page so we only execute the login step here.
        logic.account = account
        logic.page = page
        await logic._login()
    except Exception as exc:
        logger.info("Main auto-login failed for account %s: %s", account.id, exc)
    finally:
        db.close()

    # Final check on target page.
    await page.get("https://casehug.com/user-account")
    await asyncio.sleep(2.0)
    await _wait_for_cloudflare(page, timeout_seconds=35)
    return await _is_casehug_logged_in(page)


async def _collect_all_drop_rows(page, max_scrolls: int = 80, stable_rounds: int = 5) -> list[dict]:
    last_count = -1
    stable = 0

    for _ in range(max_scrolls):
        rows = await page.evaluate(_JS_EXTRACT_DROPS) or []
        count = len(rows) if isinstance(rows, list) else 0

        if count == last_count:
            stable += 1
        else:
            stable = 0
            last_count = count

        if stable >= stable_rounds:
            break

        await page.evaluate("window.scrollTo(0, document.body.scrollHeight);")
        await asyncio.sleep(0.8)

    final_rows = await page.evaluate(_JS_EXTRACT_DROPS) or []
    if not isinstance(final_rows, list):
        return []
    return final_rows


def _normalize_rows(rows: list[dict]) -> list[dict]:
    normalized = []
    seen: set[str] = set()
    for row in rows:
        name = str((row or {}).get("name", "")).strip()
        category = str((row or {}).get("category", "")).strip()
        if not name:
            continue

        skin_name = name if "|" in name else f"{name} | {category}".strip(" |")
        case_source = str((row or {}).get("case_source", "")).strip().lower() or None
        price_text = str((row or {}).get("price", "")).strip()
        image_url = str((row or {}).get("image_url", "")).strip() or None
        label = str((row or {}).get("label", "")).strip().lower()
        condition = str((row or {}).get("condition", "")).strip().upper() or None
        color = (
            str((row or {}).get("category_color", "")).strip()
            or str((row or {}).get("rarity_color", "")).strip()
            or None
        )
        rarity = rarity_from_color(color) or "Unknown"
        obtained_date_raw = str((row or {}).get("obtained_date", "")).strip()
        obtained_time_raw = str((row or {}).get("obtained_time", "")).strip()
        item_id = str((row or {}).get("item_id", "")).strip() or None
        obtained_dt = datetime.now(UTC).replace(tzinfo=None)
        if obtained_date_raw and obtained_time_raw:
            try:
                obtained_dt = datetime.strptime(
                    f"{obtained_date_raw} {obtained_time_raw}",
                    "%Y-%m-%d %H:%M:%S",
                )
            except Exception:
                pass

        dedupe_key = item_id or "|".join(
            [
                skin_name,
                case_source or "",
                condition or "",
                f"{_parse_price(price_text):.4f}",
                obtained_date_raw,
                obtained_time_raw,
            ]
        )
        if dedupe_key in seen:
            continue
        seen.add(dedupe_key)

        normalized.append(
            {
                "skin_name": skin_name,
                "estimated_price": _parse_price(price_text),
                "case_source": case_source,
                "item_id": item_id,
                "skin_image_url": image_url,
                "rarity": rarity,
                "condition": condition,
                "is_new": label == "new",
                "obtained_date": obtained_dt,
            }
        )
    return normalized


async def _import_account(account, *, replace_existing: bool, dry_run: bool, max_scrolls: int) -> AccountImportResult:
    profile_path = account.browser_profile_path or ensure_profile_path(account.account_name)
    browser = None

    try:
        _kill_profile_chrome_processes(profile_path)
        _cleanup_stale_profile_locks(profile_path)

        browser = await uc.start(
            user_data_dir=profile_path,
            headless=False,
            sandbox=False,
            browser_args=[
                "--window-position=-32000,-32000",
                "--window-size=1920,1080",
                "--no-sandbox",
                "--disable-setuid-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--mute-audio",
                "--no-first-run",
                "--no-default-browser-check",
            ],
        )
        page = browser.main_tab

        logged_in = await _ensure_casehug_logged_in(page, account)
        if not logged_in:
            return AccountImportResult(
                account_id=account.id,
                account_name=account.account_name,
                logged_in=False,
                scraped_count=0,
                saved_count=0,
                deleted_count=0,
            )

        await page.get("https://casehug.com/user-account")
        await asyncio.sleep(2.0)
        await _wait_for_cloudflare(page, timeout_seconds=45)

        rows = await _collect_all_drop_rows(page, max_scrolls=max_scrolls, stable_rounds=5)
        normalized = _normalize_rows(rows)

        if dry_run:
            return AccountImportResult(
                account_id=account.id,
                account_name=account.account_name,
                logged_in=True,
                scraped_count=len(normalized),
                saved_count=0,
                deleted_count=0,
            )

        db = SessionLocal()
        deleted = 0
        saved = 0
        try:
            if replace_existing:
                deleted = (
                    db.query(Skin)
                    .filter(Skin.account_id == account.id)
                    .delete(synchronize_session=False)
                )

            for item in normalized:
                db.add(
                    Skin(
                        account_id=account.id,
                        skin_name=item["skin_name"],
                        estimated_price=item["estimated_price"],
                        case_source=item["case_source"],
                        skin_image_url=item["skin_image_url"],
                        rarity=item["rarity"],
                        condition=item["condition"],
                        is_new=item["is_new"],
                        obtained_date=item["obtained_date"],
                    )
                )
                saved += 1

            db.commit()
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

        return AccountImportResult(
            account_id=account.id,
            account_name=account.account_name,
            logged_in=True,
            scraped_count=len(normalized),
            saved_count=saved,
            deleted_count=deleted,
        )

    except Exception as exc:
        return AccountImportResult(
            account_id=account.id,
            account_name=account.account_name,
            logged_in=False,
            scraped_count=0,
            saved_count=0,
            deleted_count=0,
            error=str(exc),
        )
    finally:
        if browser:
            try:
                browser.stop()
            except Exception:
                pass


async def _run(args) -> int:
    if not init_db():
        print("ERROR: database initialization failed.")
        return 1

    _apply_nodriver_websocket_compat_patch()

    db = SessionLocal()
    try:
        accounts = AccountCRUD.get_all(db)
    finally:
        db.close()

    if args.account_id:
        target_ids = set(args.account_id)
        accounts = [acc for acc in accounts if acc.id in target_ids]

    if not accounts:
        print("No accounts found for import.")
        return 0

    print(f"Accounts selected: {len(accounts)}")
    print(
        f"Mode: {'DRY-RUN' if args.dry_run else 'IMPORT'} | "
        f"{'REPLACE existing skins' if args.replace_existing else 'APPEND new rows'}"
    )
    print("-" * 72)

    results: list[AccountImportResult] = []
    for account in accounts:
        print(f"[{account.id}] {account.account_name}: processing...")
        result = await _import_account(
            account,
            replace_existing=args.replace_existing,
            dry_run=args.dry_run,
            max_scrolls=args.max_scrolls,
        )
        results.append(result)

        if result.error:
            print(f"  -> ERROR: {result.error}")
            continue
        if not result.logged_in:
            print("  -> skipped (account is not logged in on CaseHug).")
            continue
        if args.dry_run:
            print(f"  -> logged in, scraped={result.scraped_count}")
        else:
            print(
                f"  -> logged in, scraped={result.scraped_count}, "
                f"deleted={result.deleted_count}, saved={result.saved_count}"
            )

    print("-" * 72)
    ok = sum(1 for r in results if not r.error and r.logged_in)
    skipped = sum(1 for r in results if not r.error and not r.logged_in)
    failed = sum(1 for r in results if r.error)
    total_saved = sum(r.saved_count for r in results)
    total_deleted = sum(r.deleted_count for r in results)
    total_scraped = sum(r.scraped_count for r in results)

    print(
        f"Done: ok={ok}, skipped_not_logged={skipped}, failed={failed}, "
        f"scraped={total_scraped}, saved={total_saved}, deleted={total_deleted}"
    )
    return 0 if failed == 0 else 2


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Temporary importer for logged-in account skins.")
    parser.add_argument(
        "--account-id",
        type=int,
        action="append",
        help="Import only this account id (can be repeated).",
    )
    parser.add_argument(
        "--replace-existing",
        action="store_true",
        help="Delete existing skins for each imported account before saving snapshot.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Do not write to DB. Only show how many rows would be imported.",
    )
    parser.add_argument(
        "--max-scrolls",
        type=int,
        default=80,
        help="Maximum scroll passes on user-account page (default: 80).",
    )
    return parser


def main():
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s: %(message)s")
    args = _build_parser().parse_args()
    raise SystemExit(asyncio.run(_run(args)))


if __name__ == "__main__":
    main()
