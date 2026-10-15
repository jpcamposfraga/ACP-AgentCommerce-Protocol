import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Float, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base

class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    wallet_id = Column(String(36), ForeignKey("wallets.id"), nullable=False, index=True)
    amount = Column(Float, nullable=False)
    platform_fee = Column(Float, nullable=False, default=0.0)
    net_amount = Column(Float, nullable=False)
    type = Column(String(32), nullable=False)  # "TOPUP", "DEBIT_PURCHASE", "REFUND"
    status = Column(String(32), nullable=False, default="COMPLETED")  # "COMPLETED", "FAILED"
    reference_id = Column(String(128), nullable=True)
    description = Column(String(255), nullable=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    wallet = relationship("Wallet", back_populates="transactions")
