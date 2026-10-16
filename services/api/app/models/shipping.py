import uuid
from datetime import datetime, timezone
from sqlalchemy import Column, String, Boolean, DateTime
from app.core.database import Base


class ShippingProfile(Base):
    __tablename__ = "shipping_profiles"

    id = Column(String(36), primary_key=True, default=lambda: f"sp_{uuid.uuid4().hex[:12]}")
    wallet_id = Column(String(36), nullable=False, index=True)
    recipient_name = Column(String(128), nullable=False)
    cpf_cnpj = Column(String(20), nullable=False)
    phone = Column(String(30), nullable=False)
    postal_code = Column(String(12), nullable=False, index=True)
    street = Column(String(200), nullable=False)
    number = Column(String(20), nullable=False)
    complement = Column(String(100), nullable=True)
    neighborhood = Column(String(100), nullable=False)
    city = Column(String(100), nullable=False)
    state = Column(String(4), nullable=False)
    is_default = Column(Boolean, nullable=False, default=True)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
