from __future__ import annotations

import logging
import os
from pathlib import Path
import signal
import threading
import time
from typing import Dict

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover - optional dependency fallback
    def load_dotenv(*_args, **_kwargs):
        return False

from .core.bot_runner import bot_runner
from .database.crud import AccountCRUD
from .database.db import SessionLocal, init_db

CHECK_INTERVAL_SECONDS = 30
RESTART_BACKOFF_SECONDS = 120
LOCK_FILE = Path("background_worker.lock")


def _setup_logging() -> None:
    os.makedirs("logs", exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=[
            logging.StreamHandler(),
            logging.FileHandler("logs/background_worker.log", encoding="utf-8"),
        ],
        force=True,
    )


def _active_accounts() -> Dict[int, str]:
    db = SessionLocal()
    try:
        accounts = AccountCRUD.get_active(db)
        return {
            int(account.id): (account.account_name or "").strip() or str(account.id)
            for account in accounts
            if account.id is not None
        }
    finally:
        db.close()


def _is_pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def run_background_worker() -> int:
    load_dotenv()
    _setup_logging()
    logger = logging.getLogger(__name__)

    if not init_db():
        logger.error("Database initialization failed. Background worker cannot start.")
        return 1

    logger.info("CaseHugAuto background worker started.")

    # Single-instance guard.
    if LOCK_FILE.exists():
        try:
            existing_pid = int((LOCK_FILE.read_text(encoding="utf-8") or "0").strip())
        except Exception:
            existing_pid = 0

        if _is_pid_running(existing_pid):
            logger.info("Background worker already running (PID %s). Exiting.", existing_pid)
            return 0

        try:
            LOCK_FILE.unlink()
        except Exception:
            pass

    try:
        LOCK_FILE.write_text(str(os.getpid()), encoding="utf-8")
    except Exception:
        logger.warning("Could not write lock file: %s", LOCK_FILE)

    stop_event = threading.Event()
    restart_after: Dict[int, float] = {}

    def _handle_stop_signal(signum, _frame):
        logger.info("Received signal %s. Stopping worker...", signum)
        stop_event.set()

    try:
        signal.signal(signal.SIGINT, _handle_stop_signal)
        signal.signal(signal.SIGTERM, _handle_stop_signal)
    except Exception:
        # SIGTERM may not be available in all environments.
        pass

    try:
        while not stop_event.is_set():
            active = _active_accounts()
            active_ids = set(active.keys())
            running_ids = set(bot_runner.get_running_account_ids())
            now_monotonic = time.monotonic()

            # Start workers for newly active / stopped accounts.
            for account_id in sorted(active_ids):
                if account_id in running_ids:
                    continue

                retry_due = restart_after.get(account_id, 0.0)
                if now_monotonic < retry_due:
                    continue

                ok, message = bot_runner.start_account(account_id)
                account_label = active.get(account_id, str(account_id))
                if ok:
                    restart_after.pop(account_id, None)
                    logger.info("Started account worker: %s (id=%s)", account_label, account_id)
                else:
                    restart_after[account_id] = now_monotonic + RESTART_BACKOFF_SECONDS
                    logger.warning(
                        "Could not start account worker %s (id=%s): %s",
                        account_label,
                        account_id,
                        message,
                    )

            # Stop workers for accounts no longer active.
            for account_id in sorted(running_ids - active_ids):
                ok, message = bot_runner.stop_account(account_id)
                if ok:
                    logger.info("Stopped worker for inactive account id=%s", account_id)
                else:
                    logger.warning("Could not stop worker for account id=%s: %s", account_id, message)

            # Keep backoff map clean.
            for account_id in list(restart_after.keys()):
                if account_id not in active_ids:
                    restart_after.pop(account_id, None)

            stop_event.wait(CHECK_INTERVAL_SECONDS)
    finally:
        bot_runner.stop_all()
        logger.info("CaseHugAuto background worker stopped.")
        try:
            if LOCK_FILE.exists():
                LOCK_FILE.unlink()
        except Exception:
            pass

    return 0


if __name__ == "__main__":
    raise SystemExit(run_background_worker())
