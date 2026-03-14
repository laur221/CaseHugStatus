"""Bot runner service used by the desktop GUI.

This module intentionally contains only a safe execution scaffold:
- account start/stop lifecycle
- status updates in DB
- periodic heartbeat for active workers

Website automation and anti-bot bypass logic are NOT implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
import json
import logging
from pathlib import Path
import threading
from typing import Callable, Dict, Mapping, Optional, Tuple, TypedDict, cast

from ..database.db import SessionLocal
from ..database.crud import AccountCRUD, BotStatusCRUD
from ..models.models import BotStatus
from .bot_logic import AutomationLogic

logger = logging.getLogger(__name__)



class BotConfig(TypedDict):
    case_open_interval_seconds: int
    max_retries: int
    auto_start_new_accounts: bool


class StatusPayload(TypedDict):
    account_id: int
    message: str
    status: str
    timestamp: str


DEFAULT_BOT_CONFIG: BotConfig = {
    "case_open_interval_seconds": 60,
    "max_retries": 3,
    "auto_start_new_accounts": False,
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

    # -------------------- callbacks & config --------------------
    def set_status_callback(self, callback: StatusCallback):
        self._status_callback = callback

    def _emit_status(self, account_id: int, message: str, status: str = "info"):
        payload: StatusPayload = {
            "account_id": account_id,
            "message": message,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
        if self._status_callback:
            self._status_callback(payload)
        logger.info(f"[BOT:{account_id}][{status.upper()}] {message}")

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

        interval = self._to_int(interval_raw, self._config["case_open_interval_seconds"])
        retries = self._to_int(retries_raw, self._config["max_retries"])

        if isinstance(auto_start_raw, bool):
            auto_start = auto_start_raw
        else:
            auto_start = str(auto_start_raw).strip().lower() in {
                "1",
                "true",
                "yes",
                "on",
            }

        if interval < 5:
            return False, "Interval must be at least 5 seconds."
        if retries < 1:
            return False, "Max retries must be at least 1."

        self._config.update(
            {
                "case_open_interval_seconds": interval,
                "max_retries": retries,
                "auto_start_new_accounts": auto_start,
            }
        )

        if not self._save_config():
            return False, "Failed to save bot settings."
        return True, "Bot settings updated."

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
        reached_error_limit = False
        max_retries = int(self._config.get("max_retries", 3))
        interval_seconds = int(self._config.get("case_open_interval_seconds", 60))
        retry_count = 0

        try:
            account = AccountCRUD.get_by_id(db, account_id)
            if not account:
                self._emit_status(account_id, "Account not found.", "error")
                return

            BotStatusCRUD.update_status(db, account_id, "running")
            BotStatusCRUD.get_or_create(db, account_id)
            db.query(BotStatus).filter(BotStatus.account_id == account_id).update(
                {BotStatus.error_message: None}, synchronize_session=False
            )
            db.commit()

            self._emit_status(account_id, f"Worker started for {account.account_name}.", "started")

            # Initialize and run the automation logic
            automation = AutomationLogic(db, account_id, stop_event, self._emit_status)
            automation.run()

            # The rest of the loop is handled within AutomationLogic.
            # This part will be reached after the bot stops or fails.
            if stop_event.is_set():
                 self._emit_status(account_id, "Worker stopped.", "stopped")
            else:
                 self._emit_status(account_id, "Worker finished unexpectedly.", "error")
                 
        except Exception as exc:
            db.rollback()
            logger.error(f"Unexpected worker failure for account {account_id}: {exc}", exc_info=True)
            try:
                BotStatusCRUD.set_error(db, account_id, str(exc))
            except Exception:
                pass
            self._emit_status(account_id, f"Fatal worker error: {exc}", "error")
        finally:
            # Final status update
            final_status = "stopped" if stop_event.is_set() else "error"
            try:
                BotStatusCRUD.update_status(db, account_id, final_status)
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
