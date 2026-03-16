"""Bot runner service used by the desktop GUI.

This module intentionally contains only a safe execution scaffold:
- account start/stop lifecycle
- status updates in DB
- periodic heartbeat for active workers

Website automation and anti-bot bypass logic are NOT implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
import json
import logging
from pathlib import Path
import threading
from typing import Callable, Dict, Mapping, Optional, Tuple, TypedDict, cast

from ..database.db import SessionLocal
from ..database.crud import AccountCRUD, BotStatusCRUD
from ..models.models import BotStatus
from .bot_logic import AutomationLogic
from .windows_startup import (
    disable_background_startup,
    enable_background_startup,
    has_legacy_background_startup,
    is_background_startup_enabled,
    is_windows_platform,
)

logger = logging.getLogger(__name__)

CASE_COOLDOWN_HOURS = 24



class BotConfig(TypedDict):
    case_open_interval_seconds: int
    max_retries: int
    auto_start_new_accounts: bool
    auto_start_active_accounts_on_launch: bool
    start_with_windows_headless: bool
    telegram_bot_token: str
    telegram_chat_id: str
    telegram_notify_on_skin: bool
    telegram_notify_on_error: bool
    steam_login_max_retries: int


class StatusPayload(TypedDict):
    account_id: int
    account_name: str
    message: str
    status: str
    timestamp: str


DEFAULT_BOT_CONFIG: BotConfig = {
    "case_open_interval_seconds": 60,
    "max_retries": 3,
    "auto_start_new_accounts": False,
    "auto_start_active_accounts_on_launch": False,
    "start_with_windows_headless": False,
    "telegram_bot_token": "",
    "telegram_chat_id": "",
    "telegram_notify_on_skin": True,
    "telegram_notify_on_error": True,
    "steam_login_max_retries": 1,
}

CONFIG_PATH = Path("bot_settings.json")

StatusCallback = Callable[[StatusPayload], None]


@dataclass
class RunningBot:
    account_id: int
    thread: threading.Thread
    stop_event: threading.Event


class BotRunner:
    """Manage one background worker per account."""

    def __init__(self):
        self._running: Dict[int, RunningBot] = {}
        self._lock = threading.Lock()
        self._status_callback: Optional[StatusCallback] = None
        self._config = self._load_config()
        self._sync_windows_startup_from_config()

    def _sync_windows_startup_from_config(self):
        if not is_windows_platform():
            return

        desired = bool(self._config.get("start_with_windows_headless", False))
        installed = is_background_startup_enabled()
        legacy_installed = has_legacy_background_startup()

        if desired and (not installed or legacy_installed):
            ok, message = enable_background_startup()
            if not ok:
                logger.warning("Could not enable startup from config: %s", message)
        elif not desired and (installed or legacy_installed):
            ok, message = disable_background_startup()
            if not ok:
                logger.warning("Could not disable startup from config: %s", message)

    # -------------------- callbacks & config --------------------
    def set_status_callback(self, callback: StatusCallback):
        self._status_callback = callback

    def _emit_status(
        self,
        account_id: int,
        message: str,
        status: str = "info",
        account_name: str | None = None,
    ):
        label = (account_name or "").strip() or str(account_id)
        payload: StatusPayload = {
            "account_id": account_id,
            "account_name": label,
            "message": message,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._status_callback:
            self._status_callback(payload)
        logger.info(f"[BOT:{label}][{status.upper()}] {message}")

    def _load_config(self) -> BotConfig:
        if not CONFIG_PATH.exists():
            return DEFAULT_BOT_CONFIG.copy()

        try:
            with open(CONFIG_PATH, "r", encoding="utf-8") as f:
                loaded_raw = json.load(f)

            loaded: Mapping[str, object]
            if isinstance(loaded_raw, dict):
                loaded = cast(Mapping[str, object], loaded_raw)
            else:
                loaded = {}

            cfg: BotConfig = DEFAULT_BOT_CONFIG.copy()
            cfg.update(
                {
                    "case_open_interval_seconds": self._to_int(
                        loaded.get(
                            "case_open_interval_seconds",
                            DEFAULT_BOT_CONFIG["case_open_interval_seconds"],
                        ),
                        DEFAULT_BOT_CONFIG["case_open_interval_seconds"],
                    ),
                    "max_retries": self._to_int(
                        loaded.get("max_retries", DEFAULT_BOT_CONFIG["max_retries"]),
                        DEFAULT_BOT_CONFIG["max_retries"],
                    ),
                    "auto_start_new_accounts": bool(
                        loaded.get(
                            "auto_start_new_accounts",
                            DEFAULT_BOT_CONFIG["auto_start_new_accounts"],
                        )
                    ),
                    "auto_start_active_accounts_on_launch": bool(
                        loaded.get(
                            "auto_start_active_accounts_on_launch",
                            DEFAULT_BOT_CONFIG["auto_start_active_accounts_on_launch"],
                        )
                    ),
                    "start_with_windows_headless": bool(
                        loaded.get(
                            "start_with_windows_headless",
                            DEFAULT_BOT_CONFIG["start_with_windows_headless"],
                        )
                    ),
                    "telegram_bot_token": str(
                        loaded.get(
                            "telegram_bot_token",
                            DEFAULT_BOT_CONFIG["telegram_bot_token"],
                        )
                        or ""
                    ).strip(),
                    "telegram_chat_id": str(
                        loaded.get(
                            "telegram_chat_id",
                            DEFAULT_BOT_CONFIG["telegram_chat_id"],
                        )
                        or ""
                    ).strip(),
                    "telegram_notify_on_skin": bool(
                        loaded.get(
                            "telegram_notify_on_skin",
                            DEFAULT_BOT_CONFIG["telegram_notify_on_skin"],
                        )
                    ),
                    "telegram_notify_on_error": bool(
                        loaded.get(
                            "telegram_notify_on_error",
                            DEFAULT_BOT_CONFIG["telegram_notify_on_error"],
                        )
                    ),
                    "steam_login_max_retries": max(
                        0,
                        self._to_int(
                            loaded.get(
                                "steam_login_max_retries",
                                DEFAULT_BOT_CONFIG["steam_login_max_retries"],
                            ),
                            DEFAULT_BOT_CONFIG["steam_login_max_retries"],
                        ),
                    ),
                }
            )
            return cfg
        except Exception as exc:
            logger.warning(f"Failed loading bot config from {CONFIG_PATH}: {exc}")
            return DEFAULT_BOT_CONFIG.copy()

    @staticmethod
    def _to_int(value: object, default: int) -> int:
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, (int, float, str)):
            try:
                return int(value)
            except ValueError:
                return default
        return default

    @staticmethod
    def _to_bool(value: object, default: bool) -> bool:
        if isinstance(value, bool):
            return value
        if value is None:
            return default
        return str(value).strip().lower() in {"1", "true", "yes", "on"}

    def _save_config(self) -> bool:
        try:
            with open(CONFIG_PATH, "w", encoding="utf-8") as f:
                json.dump(self._config, f, indent=2, ensure_ascii=False)
            return True
        except Exception as exc:
            logger.error(f"Failed saving bot config to {CONFIG_PATH}: {exc}")
            return False

    def get_config(self) -> BotConfig:
        return self._config.copy()

    def update_config(self, updates: Mapping[str, object]) -> Tuple[bool, str]:
        interval_raw = updates.get(
            "case_open_interval_seconds", self._config["case_open_interval_seconds"]
        )
        retries_raw = updates.get("max_retries", self._config["max_retries"])
        auto_start_raw = updates.get(
            "auto_start_new_accounts", self._config["auto_start_new_accounts"]
        )
        auto_start_launch_raw = updates.get(
            "auto_start_active_accounts_on_launch",
            self._config["auto_start_active_accounts_on_launch"],
        )
        windows_start_raw = updates.get(
            "start_with_windows_headless",
            self._config["start_with_windows_headless"],
        )
        telegram_token_raw = updates.get(
            "telegram_bot_token",
            self._config["telegram_bot_token"],
        )
        telegram_chat_id_raw = updates.get(
            "telegram_chat_id",
            self._config["telegram_chat_id"],
        )
        telegram_notify_skin_raw = updates.get(
            "telegram_notify_on_skin",
            self._config["telegram_notify_on_skin"],
        )
        telegram_notify_error_raw = updates.get(
            "telegram_notify_on_error",
            self._config["telegram_notify_on_error"],
        )
        steam_login_max_retries_raw = updates.get(
            "steam_login_max_retries",
            self._config["steam_login_max_retries"],
        )

        interval = self._to_int(interval_raw, self._config["case_open_interval_seconds"])
        retries = self._to_int(retries_raw, self._config["max_retries"])

        auto_start = self._to_bool(auto_start_raw, self._config["auto_start_new_accounts"])
        auto_start_launch = self._to_bool(
            auto_start_launch_raw,
            self._config["auto_start_active_accounts_on_launch"],
        )
        windows_start_enabled = self._to_bool(
            windows_start_raw,
            self._config["start_with_windows_headless"],
        )
        telegram_notify_skin = self._to_bool(
            telegram_notify_skin_raw,
            self._config["telegram_notify_on_skin"],
        )
        telegram_notify_error = self._to_bool(
            telegram_notify_error_raw,
            self._config["telegram_notify_on_error"],
        )
        telegram_bot_token = str(telegram_token_raw or "").strip()
        telegram_chat_id = str(telegram_chat_id_raw or "").strip()
        steam_login_max_retries = max(
            0,
            self._to_int(
                steam_login_max_retries_raw,
                self._config["steam_login_max_retries"],
            ),
        )
        auto_start_launch_forced_off = False

        # Avoid duplicate automation processes: GUI auto-start and headless worker
        # should not run at the same time.
        if windows_start_enabled and auto_start_launch:
            auto_start_launch = False
            auto_start_launch_forced_off = True

        if interval < 60:
            return False, "Interval must be at least 1 minute."
        if retries < 1:
            return False, "Max retries must be at least 1."

        previous_windows_start = bool(self._config.get("start_with_windows_headless", False))

        self._config.update(
            {
                "case_open_interval_seconds": interval,
                "max_retries": retries,
                "auto_start_new_accounts": auto_start,
                "auto_start_active_accounts_on_launch": auto_start_launch,
                "start_with_windows_headless": windows_start_enabled,
                "telegram_bot_token": telegram_bot_token,
                "telegram_chat_id": telegram_chat_id,
                "telegram_notify_on_skin": telegram_notify_skin,
                "telegram_notify_on_error": telegram_notify_error,
                "steam_login_max_retries": steam_login_max_retries,
            }
        )

        if not self._save_config():
            return False, "Failed to save bot settings."

        if (
            "start_with_windows_headless" in updates
            and windows_start_enabled != previous_windows_start
        ):
            ok, startup_msg = self.configure_windows_startup(
                windows_start_enabled,
                persist=False,
            )
            if not ok:
                self._config["start_with_windows_headless"] = previous_windows_start
                self._save_config()
                return False, startup_msg
            suffix = (
                " GUI auto-start was disabled because headless startup is enabled."
                if auto_start_launch_forced_off
                else ""
            )
            return True, f"Bot settings updated. {startup_msg}{suffix}"

        if auto_start_launch_forced_off:
            return (
                True,
                "Bot settings updated. GUI auto-start was disabled because headless startup is enabled.",
            )

        return True, "Bot settings updated."

    def get_windows_startup_state(self) -> bool:
        if not is_windows_platform():
            return False
        return is_background_startup_enabled()

    def configure_windows_startup(self, enabled: bool, *, persist: bool = True) -> Tuple[bool, str]:
        enabled = bool(enabled)

        if enabled:
            ok, message = enable_background_startup()
        else:
            ok, message = disable_background_startup()

        if ok and persist:
            self._config["start_with_windows_headless"] = enabled
            self._save_config()

        return ok, message

    # -------------------- lifecycle --------------------
    def _cleanup_finished_workers(self):
        to_remove = [
            account_id
            for account_id, worker in self._running.items()
            if not worker.thread.is_alive()
        ]
        for account_id in to_remove:
            self._running.pop(account_id, None)

    def is_running(self, account_id: int) -> bool:
        with self._lock:
            self._cleanup_finished_workers()
            worker = self._running.get(account_id)
            return bool(worker and worker.thread.is_alive())

    def get_running_account_ids(self):
        with self._lock:
            self._cleanup_finished_workers()
            return list(self._running.keys())

    def start_active_accounts(self) -> Tuple[int, int, list[str]]:
        started_count = 0
        already_running_count = 0
        errors: list[str] = []

        db = SessionLocal()
        try:
            active_accounts = AccountCRUD.get_active(db)
        finally:
            db.close()

        for account in active_accounts:
            ok, message = self.start_account(account.id)
            if ok:
                started_count += 1
                continue

            if "already running" in message.lower():
                already_running_count += 1
            else:
                account_label = (account.account_name or "").strip() or str(account.id)
                errors.append(f"{account_label}: {message}")

        return started_count, already_running_count, errors

    def start_account(self, account_id: int) -> Tuple[bool, str]:
        with self._lock:
            self._cleanup_finished_workers()
            if account_id in self._running:
                return False, "Bot is already running for this account."

            stop_event = threading.Event()
            thread = threading.Thread(
                target=self._account_worker,
                args=(account_id, stop_event),
                daemon=True,
                name=f"bot-account-{account_id}",
            )
            self._running[account_id] = RunningBot(
                account_id=account_id,
                thread=thread,
                stop_event=stop_event,
            )
            thread.start()

        return True, "Bot started."

    def stop_account(self, account_id: int) -> Tuple[bool, str]:
        with self._lock:
            self._cleanup_finished_workers()
            worker = self._running.get(account_id)
            if not worker:
                return False, "Bot is not running for this account."
            worker.stop_event.set()

        return True, "Stop signal sent."

    def stop_all(self):
        with self._lock:
            workers = list(self._running.values())
        for worker in workers:
            worker.stop_event.set()

    # -------------------- worker --------------------
    def _account_worker(self, account_id: int, stop_event: threading.Event):
        db = SessionLocal()
        max_retries = int(self._config.get("max_retries", 3))
        interval_seconds = int(self._config.get("case_open_interval_seconds", 60))
        interval_minutes = max(1, int(round(interval_seconds / 60)))
        retry_count = 0
        worker_account_name: str | None = None
        automation = None

        try:
            account = AccountCRUD.get_by_id(db, account_id)
            if not account:
                self._emit_status(account_id, "Account not found.", "error")
                return
            worker_account_name = (account.account_name or "").strip() or None

            def _status_cb(aid: int, message: str, status: str = "info"):
                self._emit_status(aid, message, status, account_name=worker_account_name)

            BotStatusCRUD.update_status(db, account_id, "running")
            BotStatusCRUD.get_or_create(db, account_id)
            db.query(BotStatus).filter(BotStatus.account_id == account_id).update(
                {BotStatus.error_message: None}, synchronize_session=False
            )
            db.commit()

            _status_cb(account_id, f"Worker started for {account.account_name}.", "started")
            _status_cb(
                account_id,
                (
                    f"Auto-loop enabled. Cooldown is checked every {interval_minutes} minute(s). "
                    f"Automation runs automatically once {CASE_COOLDOWN_HOURS}h pass "
                    "from the last opened case."
                ),
                "info",
            )

            # Continuous polling loop:
            # - if 24h cooldown is not passed yet -> recheck only every interval
            # - if 24h cooldown is passed -> run automation immediately
            while not stop_event.is_set():
                try:
                    bot_status = BotStatusCRUD.get_or_create(db, account_id)
                    now_utc = datetime.utcnow()
                    last_opened_at = bot_status.last_cases_opened_at
                    if last_opened_at:
                        cooldown_due_at = last_opened_at + timedelta(hours=CASE_COOLDOWN_HOURS)
                        if cooldown_due_at > now_utc:
                            remaining_seconds = max(
                                0, int((cooldown_due_at - now_utc).total_seconds())
                            )
                            remaining_minutes = max(1, int((remaining_seconds + 59) // 60))
                            due_label = cooldown_due_at.strftime("%Y-%m-%d %H:%M:%S UTC")
                            _status_cb(
                                account_id,
                                (
                                    f"24h cooldown not passed yet. Remaining ~{remaining_minutes} "
                                    f"minute(s). Eligible at {due_label}. "
                                    f"Rechecking in {interval_minutes} minute(s)."
                                ),
                                "info",
                            )
                            try:
                                BotStatusCRUD.schedule_next_run_at(db, account_id, cooldown_due_at)
                            except Exception as exc:
                                logger.debug(
                                    "Could not persist cooldown due timestamp for account %s: %s",
                                    account_id,
                                    exc,
                                )
                            if stop_event.wait(interval_seconds):
                                _status_cb(account_id, "Worker stopped.", "stopped")
                                break
                            continue

                    # Cooldown is passed (or account has no recorded last open).
                    # Remove stale next-check marker so UI doesn't show an outdated future run.
                    try:
                        BotStatusCRUD.clear_next_check(db, account_id)
                    except Exception as exc:
                        logger.debug(
                            "Could not clear next_scheduled_run for account %s: %s",
                            account_id,
                            exc,
                        )
                except Exception as exc:
                    logger.debug(
                        "Could not evaluate 24h cooldown for account %s: %s",
                        account_id,
                        exc,
                    )
                    if stop_event.wait(interval_seconds):
                        _status_cb(account_id, "Worker stopped.", "stopped")
                        break
                    continue

                automation = AutomationLogic(db, account_id, stop_event, _status_cb, runtime_config=self._config.copy())
                automation.run()
                cycle_status = getattr(automation, "last_result_status", "unknown")

                if stop_event.is_set() or cycle_status == "stopped":
                    _status_cb(account_id, "Worker stopped.", "stopped")
                    break

                if cycle_status == "completed":
                    retry_count = 0
                    opened_cases_count = int(
                        getattr(automation, "last_opened_cases_count", 0) or 0
                    )
                    if opened_cases_count > 0:
                        try:
                            status_after_run = BotStatusCRUD.get_or_create(db, account_id)
                            cooldown_anchor = status_after_run.last_cases_opened_at or datetime.utcnow()
                            BotStatusCRUD.schedule_next_run_at(
                                db,
                                account_id,
                                cooldown_anchor + timedelta(hours=CASE_COOLDOWN_HOURS),
                            )
                        except Exception as exc:
                            logger.debug(
                                "Could not persist cooldown reset timestamp for account %s: %s",
                                account_id,
                                exc,
                            )
                        _status_cb(
                            account_id,
                            (
                                f"Opened {opened_cases_count} case(s). "
                                f"Cooldown reset ({CASE_COOLDOWN_HOURS}h). "
                                f"Rechecking in {interval_minutes} minute(s)."
                            ),
                            "success",
                        )
                        # Skip immediate extra sleep; next loop will hit cooldown gate and sleep once.
                        continue
                    else:
                        try:
                            # Keep scheduler heartbeat in sync with periodic polling.
                            BotStatusCRUD.schedule_next_check(db, account_id, interval_seconds)
                        except Exception as exc:
                            logger.debug(
                                "Could not persist next_scheduled_run for account %s: %s",
                                account_id,
                                exc,
                            )
                        _status_cb(
                            account_id,
                            f"Cycle completed. Rechecking in {interval_minutes} minute(s)...",
                            "info",
                        )
                        if stop_event.wait(interval_seconds):
                            _status_cb(account_id, "Worker stopped.", "stopped")
                            break
                else:
                    retry_count += 1
                    try:
                        BotStatusCRUD.schedule_next_check(db, account_id, interval_seconds)
                    except Exception as exc:
                        logger.debug(
                            "Could not persist next_scheduled_run for failed cycle account %s: %s",
                            account_id,
                            exc,
                        )
                    _status_cb(
                        account_id,
                        f"Cycle failed (status={cycle_status}, retry {retry_count}/{max_retries}).",
                        "warning",
                    )
                    if retry_count >= max_retries:
                        _status_cb(
                            account_id,
                            "Maximum retries reached. Worker stopped.",
                            "error",
                        )
                        break
                    if stop_event.wait(interval_seconds):
                        _status_cb(account_id, "Worker stopped.", "stopped")
                        break
                 
        except Exception as exc:
            db.rollback()
            logger.error(f"Unexpected worker failure for account {account_id}: {exc}", exc_info=True)
            try:
                BotStatusCRUD.set_error(db, account_id, str(exc))
            except Exception:
                pass
            self._emit_status(
                account_id,
                f"Fatal worker error: {exc}",
                "error",
                account_name=worker_account_name,
            )
        finally:
            # Final status update
            if stop_event.is_set():
                final_status = "stopped"
            elif automation and getattr(automation, "last_result_status", "") == "completed":
                final_status = "completed"
            else:
                final_status = "error"
            try:
                BotStatusCRUD.update_status(db, account_id, final_status)
                if final_status in {"stopped", "error"}:
                    BotStatusCRUD.clear_next_check(db, account_id)
            except Exception:
                pass

            db.close()
            with self._lock:
                self._running.pop(account_id, None)

    # compatibility wrappers
    def run_account_in_thread(self, account_id: int):
        """Backward-compatible wrapper used by older GUI code."""
        ok, _ = self.start_account(account_id)
        if not ok:
            return None
        with self._lock:
            worker = self._running.get(account_id)
            return worker.thread if worker else None

    def stop(self):
        """Backward-compatible stop method."""
        self.stop_all()


bot_runner = BotRunner()
