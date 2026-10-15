import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, Boolean, DateTime, Date
from sqlalchemy.orm import relationship
from app.core.database import Base

class Wallet(Base):
    __tablename__ = "wallets"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(64), nullable=False, index=True)
    balance = Column(Float, nullable=False, default=0.0)
    currency = Column(String(3), nullable=False, default="BRL")
    max_per_order = Column(Float, nullable=False, default=1000.0)
    daily_limit = Column(Float, nullable=False, default=5000.0)
    spent_today = Column(Float, nullable=False, default=0.0)
    last_spend_date = Column(Date, default=lambda: datetime.now(timezone.utc).date())
    is_active = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    transactions = relationship("Transaction", back_populates="wallet", cascade="all, delete-orphan")
