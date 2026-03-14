from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from ..models.models import Account, Skin, LoginSession, BotStatus
from typing import List, Optional, Dict
import logging

from ..core.profile_store import ensure_profile_path

logger = logging.getLogger(__name__)


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
    def get_by_id(db: Session, skin_id: int) -> Optional[Skin]:
        """Get skin by ID"""
        return db.query(Skin).filter(Skin.id == skin_id).first()
    
    @staticmethod
    def get_by_account(db: Session, account_id: int) -> List[Skin]:
        """Get all skins for account"""
        return db.query(Skin).filter(Skin.account_id == account_id).all()
    
    @staticmethod
    def get_new_skins(db: Session, account_id: int) -> List[Skin]:
        """Get new (not seen by user) skins"""
        return db.query(Skin).filter(
            Skin.account_id == account_id,
            Skin.is_new == True
        ).all()
    
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
    def record_execution(db: Session, account_id: int, cases_opened: int, skins_obtained: int, total_value: float):
        """Record bot execution results"""
        bot_status = BotStatusCRUD.get_or_create(db, account_id)
        bot_status.last_run = datetime.utcnow()
        bot_status.cases_opened_total += cases_opened
        bot_status.skins_obtained += skins_obtained
        bot_status.total_value_obtained += total_value
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
