from sqlalchemy.orm import Session, joinedload
from sqlalchemy import func
from datetime import datetime, timedelta, timezone
from ..models.models import Account, Skin, LoginSession, BotStatus
from typing import List, Optional, Dict
import logging

from ..core.profile_store import ensure_profile_path

logger = logging.getLogger(__name__)
CASE_COOLDOWN_HOURS = 24


# ==================== ACCOUNT CRUD ====================

class AccountCRUD:
    @staticmethod
    def create(db: Session, account_name: str, steam_username: Optional[str] = None,
               steam_id: Optional[str] = None, steam_nickname: Optional[str] = None,
               steam_avatar_url: Optional[str] = None, cookies: Optional[Dict] = None) -> Account:
        """Create new account with optional Steam profile data"""
        profile_path = ensure_profile_path(account_name)
        account = Account(
            account_name=account_name,
            steam_username=steam_username or steam_nickname,
            steam_id=steam_id,
            steam_nickname=steam_nickname,
            steam_avatar_url=steam_avatar_url,
            browser_profile_path=profile_path,
            cookies=cookies,
        )
        db.add(account)
        db.commit()
        db.refresh(account)
        return account
    
    @staticmethod
    def get_by_id(db: Session, account_id: int) -> Optional[Account]:
        """Get account by ID"""
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            AccountCRUD.ensure_profile_path(db, account)
        return account
    
    @staticmethod
    def get_by_name(db: Session, account_name: str) -> Optional[Account]:
        """Get account by name"""
        account = db.query(Account).filter(Account.account_name == account_name).first()
        if account:
            AccountCRUD.ensure_profile_path(db, account)
        return account

    @staticmethod
    def get_by_steam_id(db: Session, steam_id: Optional[str]) -> Optional[Account]:
        """Get most recent account by Steam ID."""
        value = str(steam_id or "").strip()
        if not value:
            return None
        account = (
            db.query(Account)
            .filter(Account.steam_id == value)
            .order_by(Account.id.asc())
            .first()
        )
        if account:
            AccountCRUD.ensure_profile_path(db, account)
        return account
    
    @staticmethod
    def get_all(db: Session) -> List[Account]:
        """Get all accounts"""
        try:
            accounts = db.query(Account).all()
            changed = False
            for account in accounts:
                changed = AccountCRUD.ensure_profile_path(db, account, commit=False) or changed
            if changed:
                db.commit()
                for account in accounts:
                    db.refresh(account)
            return accounts
        except Exception as e:
            logger.warning(f"Error fetching accounts: {e}")
            return []
    
    @staticmethod
    def get_active(db: Session) -> List[Account]:
        """Get all active accounts"""
        try:
            accounts = db.query(Account).filter(Account.is_active == True).all()
            changed = False
            for account in accounts:
                changed = AccountCRUD.ensure_profile_path(db, account, commit=False) or changed
            if changed:
                db.commit()
                for account in accounts:
                    db.refresh(account)
            return accounts
        except Exception as e:
            logger.warning(f"Error fetching active accounts: {e}")
            return []

    @staticmethod
    def ensure_profile_path(db: Session, account: Account, commit: bool = True) -> bool:
        """Ensure the account has a persistent browser profile path."""
        profile_path = ensure_profile_path(account.account_name)
        if account.browser_profile_path == profile_path:
            return False

        account.browser_profile_path = profile_path
        if commit:
            db.commit()
            db.refresh(account)
        return True

    @staticmethod
    def rebind_profile_paths(db: Session) -> int:
        """Recompute browser_profile_path for all accounts based on current profile root."""
        accounts = db.query(Account).all()
        changed = 0
        for account in accounts:
            changed += 1 if AccountCRUD.ensure_profile_path(db, account, commit=False) else 0

        if changed:
            db.commit()

        return changed
    
    @staticmethod
    def update_steam_profile(db: Session, account_id: int, steam_id: str, avatar_url: str, nickname: str) -> Account:
        """Update Steam profile information"""
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            account.steam_id = steam_id
            account.steam_avatar_url = avatar_url
            account.steam_nickname = nickname
            account.last_login = datetime.utcnow()
            db.commit()
            db.refresh(account)
        return account
    
    @staticmethod
    def update_cookies(db: Session, account_id: int, cookies: dict) -> Account:
        """Update cookies for persistent login"""
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            account.cookies = cookies
            db.commit()
            db.refresh(account)
        return account
    
    @staticmethod
    def delete(db: Session, account_id: int) -> bool:
        """Delete account and all related data"""
        try:
            # Delete related BotStatus records first
            db.query(BotStatus).filter(BotStatus.account_id == account_id).delete(synchronize_session=False)
            
            # Delete related Skin records
            db.query(Skin).filter(Skin.account_id == account_id).delete(synchronize_session=False)
            
            # Delete related LoginSession records if they exist
            if hasattr(db, 'LoginSession'):
                db.query(db.LoginSession).filter(db.LoginSession.account_id == account_id).delete(synchronize_session=False)
            
            # Finally delete the account
            account = db.query(Account).filter(Account.id == account_id).first()
            if account:
                db.delete(account)
            
            db.commit()
            return True
        except Exception as e:
            db.rollback()
            logger.error(f"Error deleting account {account_id}: {e}")
            return False
    
    @staticmethod
    def toggle_active(db: Session, account_id: int) -> Optional[Account]:
        """Toggle account active status"""
        account = db.query(Account).filter(Account.id == account_id).first()
        if account:
            account.is_active = not account.is_active
            db.commit()
            db.refresh(account)
        return account
    
    @staticmethod
    def import_profiles_from_folder(db: Session) -> dict:
        """
        Import all discovered profiles from profiles/ folder
        Returns dict with import results
        """
        from ..core.profile_importer import ProfileImporter
        return ProfileImporter.import_profiles(db, AccountCRUD)
    
    @staticmethod
    def get_available_profiles_to_import() -> List[Dict]:
        """
        Get list of profiles available for import
        Returns list of dicts with 'name' and 'path'
        """
        from ..core.profile_importer import ProfileImporter
        return ProfileImporter.scan_profiles()


# ==================== SKIN CRUD ====================

class SkinCRUD:
    @staticmethod
    def create(db: Session, account_id: int, skin_name: str, **kwargs) -> Skin:
        """Create new skin"""
        skin = Skin(
            account_id=account_id,
            skin_name=skin_name,
            **kwargs
        )
        db.add(skin)
        db.commit()
        db.refresh(skin)
        return skin

    @staticmethod
    def find_recent_duplicate(
        db: Session,
        account_id: int,
        skin_name: str,
        case_source: Optional[str],
        estimated_price: Optional[float],
        window_minutes: int = 20,
    ) -> Optional[Skin]:
        """Find a very recent duplicate drop with same account/name/case/price."""
        cutoff = datetime.utcnow() - timedelta(minutes=max(1, int(window_minutes)))
        query = db.query(Skin).filter(
            Skin.account_id == account_id,
            Skin.skin_name == skin_name,
            Skin.created_at >= cutoff,
        )

        if case_source is None:
            query = query.filter(Skin.case_source.is_(None))
        else:
            query = query.filter(Skin.case_source == case_source)

        if estimated_price is None:
            query = query.filter(Skin.estimated_price.is_(None))
        else:
            # Float-safe comparison in SQL.
            query = query.filter(
                func.abs(func.coalesce(Skin.estimated_price, 0.0) - float(estimated_price)) < 0.0001
            )

        return query.order_by(Skin.created_at.desc()).first()

    @staticmethod
    def find_by_external_item_id(
        db: Session,
        account_id: int,
        external_item_id: str | None,
    ) -> Optional[Skin]:
        item_id = str(external_item_id or "").strip()
        if not item_id:
            return None
        return (
            db.query(Skin)
            .filter(
                Skin.account_id == account_id,
                Skin.external_item_id == item_id,
            )
            .order_by(Skin.created_at.desc())
            .first()
        )

    @staticmethod
    def find_duplicate_by_signature(
        db: Session,
        account_id: int,
        skin_name: str,
        case_source: Optional[str],
        estimated_price: Optional[float],
        obtained_date: Optional[datetime],
        time_tolerance_seconds: int = 2,
    ) -> Optional[Skin]:
        query = db.query(Skin).filter(
            Skin.account_id == account_id,
            Skin.skin_name == skin_name,
        )

        if case_source is None:
            query = query.filter(Skin.case_source.is_(None))
        else:
            query = query.filter(Skin.case_source == case_source)

        if estimated_price is None:
            query = query.filter(Skin.estimated_price.is_(None))
        else:
            query = query.filter(
                func.abs(func.coalesce(Skin.estimated_price, 0.0) - float(estimated_price)) < 0.0001
            )

        if isinstance(obtained_date, datetime):
            tol = max(0, int(time_tolerance_seconds))
            lower = obtained_date - timedelta(seconds=tol)
            upper = obtained_date + timedelta(seconds=tol)
            query = query.filter(Skin.obtained_date >= lower, Skin.obtained_date <= upper)

        return query.order_by(Skin.created_at.desc()).first()

    @staticmethod
    def upsert_imported(
        db: Session,
        account_id: int,
        skin_name: str,
        *,
        external_item_id: Optional[str] = None,
        estimated_price: Optional[float] = None,
        case_source: Optional[str] = None,
        rarity: Optional[str] = None,
        condition: Optional[str] = None,
        skin_image_url: Optional[str] = None,
        obtained_date: Optional[datetime] = None,
        is_new: bool = True,
    ) -> tuple[Skin, bool]:
        """Create or update a skin record without deleting existing account history.

        Returns tuple: (skin, created_flag)
        """
        item_id = str(external_item_id or "").strip() or None
        existing = SkinCRUD.find_by_external_item_id(db, account_id, item_id) if item_id else None

        if not existing:
            existing = SkinCRUD.find_duplicate_by_signature(
                db,
                account_id=account_id,
                skin_name=skin_name,
                case_source=case_source,
                estimated_price=estimated_price,
                obtained_date=obtained_date,
            )

        if existing:
            changed = False

            if item_id and item_id != (existing.external_item_id or ""):
                existing.external_item_id = item_id
                changed = True

            update_values = {
                "estimated_price": estimated_price,
                "case_source": case_source,
                "rarity": rarity,
                "condition": condition,
                "skin_image_url": skin_image_url,
                "obtained_date": obtained_date,
            }
            for field, value in update_values.items():
                if value is None:
                    continue
                if getattr(existing, field) != value:
                    setattr(existing, field, value)
                    changed = True

            # Never auto-clear the NEW marker during import.
            if is_new and not bool(existing.is_new):
                existing.is_new = True
                changed = True

            if changed:
                db.commit()
                db.refresh(existing)
            return existing, False

        skin = Skin(
            account_id=account_id,
            skin_name=skin_name,
            external_item_id=item_id,
            estimated_price=estimated_price,
            case_source=case_source,
            rarity=rarity,
            condition=condition,
            skin_image_url=skin_image_url,
            obtained_date=obtained_date,
            is_new=bool(is_new),
        )
        db.add(skin)
        db.commit()
        db.refresh(skin)
        return skin, True
    
    @staticmethod
    def get_by_id(db: Session, skin_id: int) -> Optional[Skin]:
        """Get skin by ID"""
        return db.query(Skin).filter(Skin.id == skin_id).first()
    
    @staticmethod
    def get_by_account(db: Session, account_id: int) -> List[Skin]:
        """Get all skins for account"""
        return (
            db.query(Skin)
            .options(joinedload(Skin.account))
            .filter(Skin.account_id == account_id)
            .order_by(
                func.coalesce(Skin.obtained_date, Skin.created_at).desc(),
                Skin.created_at.desc(),
            )
            .all()
        )

    @staticmethod
    def get_all(db: Session) -> List[Skin]:
        """Get all skins from all accounts"""
        return (
            db.query(Skin)
            .options(joinedload(Skin.account))
            .order_by(
                func.coalesce(Skin.obtained_date, Skin.created_at).desc(),
                Skin.created_at.desc(),
            )
            .all()
        )
    
    @staticmethod
    def get_new_skins(db: Session, account_id: int) -> List[Skin]:
        """Get new (not seen by user) skins"""
        return (
            db.query(Skin)
            .filter(
                Skin.account_id == account_id,
                Skin.is_new == True,
            )
            .order_by(
                func.coalesce(Skin.obtained_date, Skin.created_at).desc(),
                Skin.created_at.desc(),
            )
            .all()
        )
    
    @staticmethod
    def get_by_rarity(db: Session, account_id: int, rarity: str) -> List[Skin]:
        """Get skins by rarity"""
        return db.query(Skin).filter(
            Skin.account_id == account_id,
            Skin.rarity == rarity
        ).all()
    
    @staticmethod
    def mark_as_seen(db: Session, skin_id: int) -> Optional[Skin]:
        """Mark skin as seen"""
        skin = db.query(Skin).filter(Skin.id == skin_id).first()
        if skin:
            skin.is_new = False
            db.commit()
            db.refresh(skin)
        return skin
    
    @staticmethod
    def mark_all_as_seen(db: Session, account_id: int):
        """Mark all skins for account as seen"""
        db.query(Skin).filter(
            Skin.account_id == account_id,
            Skin.is_new == True
        ).update({"is_new": False})
        db.commit()
    
    @staticmethod
    def delete(db: Session, skin_id: int) -> bool:
        """Delete skin"""
        skin = db.query(Skin).filter(Skin.id == skin_id).first()
        if skin:
            db.delete(skin)
            db.commit()
            return True
        return False
    
    @staticmethod
    def get_stats(db: Session, account_id: int) -> dict:
        """Get stats for account skins"""
        skins = db.query(Skin).filter(Skin.account_id == account_id).all()
        total_value = sum(skin.estimated_price or 0 for skin in skins)
        new_count = len([s for s in skins if s.is_new])
        
        return {
            "total_skins": len(skins),
            "new_skins": new_count,
            "total_value": round(total_value, 2),
            "average_price": round(total_value / len(skins), 2) if skins else 0
        }


# ==================== LOGIN SESSION CRUD ====================

class LoginSessionCRUD:
    @staticmethod
    def create(db: Session, account_id: int, steam_qr_url: Optional[str] = None) -> LoginSession:
        """Create new login session"""
        session = LoginSession(
            account_id=account_id,
            steam_qr_url=steam_qr_url,
            expires_at=datetime.utcnow() + timedelta(hours=1)
        )
        db.add(session)
        db.commit()
        db.refresh(session)
        return session
    
    @staticmethod
    def get_by_id(db: Session, session_id: int) -> Optional[LoginSession]:
        """Get session by ID"""
        return db.query(LoginSession).filter(LoginSession.id == session_id).first()
    
    @staticmethod
    def get_active_session(db: Session, account_id: int) -> Optional[LoginSession]:
        """Get active session for account"""
        return db.query(LoginSession).filter(
            LoginSession.account_id == account_id,
            LoginSession.status != "completed",
            LoginSession.status != "failed"
        ).order_by(LoginSession.started_at.desc()).first()
    
    @staticmethod
    def update_status(db: Session, session_id: int, status: str) -> Optional[LoginSession]:
        """Update session status"""
        session = db.query(LoginSession).filter(LoginSession.id == session_id).first()
        if session:
            session.status = status
            if status == "completed":
                session.completed_at = datetime.utcnow()
            db.commit()
            db.refresh(session)
        return session
    
    @staticmethod
    def cleanup_expired(db: Session):
        """Delete expired sessions"""
        db.query(LoginSession).filter(
            LoginSession.expires_at < datetime.utcnow()
        ).delete()
        db.commit()


# ==================== BOT STATUS CRUD ====================

class BotStatusCRUD:
    @staticmethod
    def get_or_create(db: Session, account_id: int) -> BotStatus:
        """Get or create bot status for account"""
        status = db.query(BotStatus).filter(BotStatus.account_id == account_id).first()
        if not status:
            status = BotStatus(account_id=account_id)
            db.add(status)
            db.commit()
            db.refresh(status)
        return status
    
    @staticmethod
    def update_status(db: Session, account_id: int, status: str) -> BotStatus:
        """Update bot status"""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        bot_status.status = status
        db.commit()
        db.refresh(bot_status)
        return bot_status

    @staticmethod
    def record_case_check(db: Session, account_id: int) -> BotStatus:
        """Store timestamp of the latest cooldown check for this account."""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        bot_status.last_case_check_at = datetime.utcnow()
        db.commit()
        db.refresh(bot_status)
        return bot_status

    @staticmethod
    def record_cases_opened_at(db: Session, account_id: int) -> BotStatus:
        """Store timestamp when at least one case was opened for this account."""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        bot_status.last_cases_opened_at = datetime.utcnow()
        db.commit()
        db.refresh(bot_status)
        return bot_status

    @staticmethod
    def schedule_next_check(db: Session, account_id: int, seconds_from_now: int) -> BotStatus:
        """Persist next cooldown-check timestamp for this account."""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        delay = max(1, int(seconds_from_now))
        now = datetime.utcnow()

        cooldown_due_at = None
        if bot_status.last_cases_opened_at:
            cooldown_due_at = bot_status.last_cases_opened_at + timedelta(hours=CASE_COOLDOWN_HOURS)

        if cooldown_due_at and cooldown_due_at > now:
            bot_status.next_scheduled_run = cooldown_due_at
        else:
            bot_status.next_scheduled_run = now + timedelta(seconds=delay)

        db.commit()
        db.refresh(bot_status)
        return bot_status

    @staticmethod
    def schedule_next_run_at(db: Session, account_id: int, run_at: datetime) -> BotStatus:
        """Persist exact UTC timestamp for the next eligible run."""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        if run_at.tzinfo is not None:
            run_at = run_at.astimezone(timezone.utc).replace(tzinfo=None)
        now = datetime.utcnow()
        bot_status.next_scheduled_run = run_at if run_at >= now else now
        db.commit()
        db.refresh(bot_status)
        return bot_status

    @staticmethod
    def clear_next_check(db: Session, account_id: int) -> BotStatus:
        """Clear scheduled next check timestamp for this account."""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        bot_status.next_scheduled_run = None
        db.commit()
        db.refresh(bot_status)
        return bot_status
    
    @staticmethod
    def record_execution(db: Session, account_id: int, cases_opened: int, skins_obtained: int, total_value: float):
        """Record bot execution results"""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        now = datetime.utcnow()
        bot_status.last_run = now
        bot_status.cases_opened_total += cases_opened
        bot_status.skins_obtained += skins_obtained
        bot_status.total_value_obtained += total_value
        if int(cases_opened or 0) > 0:
            bot_status.last_cases_opened_at = now
        db.commit()
        db.refresh(bot_status)
        return bot_status
    
    @staticmethod
    def set_error(db: Session, account_id: int, error_message: str):
        """Set error status"""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        bot_status.status = "error"
        bot_status.error_message = error_message
        db.commit()
        db.refresh(bot_status)
