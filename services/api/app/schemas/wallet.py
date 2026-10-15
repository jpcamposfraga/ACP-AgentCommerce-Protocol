from datetime import datetime
from pydantic import BaseModel, Field, ConfigDict

class WalletBase(BaseModel):
    max_per_order: float = Field(default=1000.0, gt=0, description="Teto máximo por ordem")
    daily_limit: float = Field(default=5000.0, gt=0, description="Limite diário de compras")

class WalletCreate(WalletBase):
    user_id: str = Field(..., min_length=1, max_length=64)

class WalletResponse(WalletBase):
    id: str
    user_id: str
    balance: float
    currency: str
    spent_today: float
    is_active: bool
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)

class TopupRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Valor do crédito a recarregar")
    reference_id: str | None = Field(default=None, description="Identificador externo Pix/BaaS")

class DebitRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Valor líquido da compra a pagar ao lojista")
    reference_id: str | None = Field(default=None, description="ID do pedido ou transação externa")
    description: str | None = Field(default=None, description="Descrição do produto ou lote")

class DebitResponse(BaseModel):
    success: bool
    transaction_id: str
    amount: float
    platform_fee: float
    total_debited: float
    remaining_balance: float
    reference_id: str | None
