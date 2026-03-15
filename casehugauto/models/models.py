from sqlalchemy import Column, Integer, String, Text, DateTime, Float, Boolean, ForeignKey, JSON, func
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()


class Account(Base):
    """Model for storing account information with Steam profile data"""
    __tablename__ = "accounts"
    
    id = Column(Integer, primary_key=True, index=True)
    account_name = Column(String(255), unique=True, nullable=False, index=True)
    steam_username = Column(String(255), nullable=True)
    steam_id = Column(String(255), nullable=True, index=True)
    steam_avatar_url = Column(Text, nullable=True)
    steam_nickname = Column(String(255), nullable=True)
    browser_profile_path = Column(String(500), nullable=True)
    
    # Persistent cookies for auto-login (stored as JSON)
    cookies = Column(JSON, nullable=True, default={})
    
    # Account status
    is_active = Column(Boolean, default=True)
    last_login = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationships
    skins = relationship("Skin", back_populates="account", cascade="all, delete-orphan")
    sessions = relationship("LoginSession", back_populates="account", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Account(id={self.id}, account_name={self.account_name}, steam_nickname={self.steam_nickname})>"


class Skin(Base):
    """Model for tracking skins per account"""
    __tablename__ = "skins"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    
    # Skin information
    skin_name = Column(String(500), nullable=False, index=True)
    skin_image_url = Column(Text, nullable=True)
    rarity = Column(String(100), nullable=True)  # e.g., "Ordinary", "Rare", "Legendary"
    estimated_price = Column(Float, nullable=True)
    market_price = Column(Float, nullable=True)
    
    # Metadata
    obtained_date = Column(DateTime, nullable=True)
    case_source = Column(String(255), nullable=True)  # Which case it came from
    condition = Column(String(100), nullable=True)  # Condition if applicable
    
    # Tracking
    is_new = Column(Boolean, default=True)  # Flag for newly obtained skins
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Relationship
    account = relationship("Account", back_populates="skins")
    
    def __repr__(self):
        return f"<Skin(id={self.id}, name={self.skin_name}, price={self.estimated_price})>"


class LoginSession(Base):
    """Model for managing temporary login sessions"""
    __tablename__ = "login_sessions"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=False, index=True)
    
    # Session info
    session_token = Column(String(500), nullable=True)
    steam_qr_url = Column(Text, nullable=True)  # QR code URL for Steam login
    status = Column(String(50), default="pending")  # pending, in_progress, completed, failed
    
    # Timing
    started_at = Column(DateTime, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    expires_at = Column(DateTime, nullable=True)
    
    # Account relationship
    account = relationship("Account", back_populates="sessions")
    
    def __repr__(self):
        return f"<LoginSession(id={self.id}, account_id={self.account_id}, status={self.status})>"


class BotStatus(Base):
    """Model for tracking bot execution status"""
    __tablename__ = "bot_status"
    
    id = Column(Integer, primary_key=True, index=True)
    account_id = Column(Integer, ForeignKey("accounts.id"), nullable=True, index=True)
    
    # Bot execution
    status = Column(String(50), default="stopped")  # running, stopped, completed, error
    last_run = Column(DateTime, nullable=True)
    next_scheduled_run = Column(DateTime, nullable=True)
    last_case_check_at = Column(DateTime, nullable=True)
    last_cases_opened_at = Column(DateTime, nullable=True)
    
    # Execution stats
    cases_opened_total = Column(Integer, default=0)
    skins_obtained = Column(Integer, default=0)
    total_value_obtained = Column(Float, default=0.0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<BotStatus(id={self.id}, status={self.status}, cases_opened={self.cases_opened_total})>"
