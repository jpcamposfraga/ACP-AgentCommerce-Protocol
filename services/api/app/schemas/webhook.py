from pydantic import BaseModel, Field


class BaaSPixWebhook(BaseModel):
    event: str = Field(..., description="Tipo do evento recebido do BaaS (ex: pix_received)")
    payment_id: str = Field(..., description="ID da transação no BaaS")
    wallet_id: str = Field(..., description="ID da carteira beneficiária no ACP")
    amount: float = Field(..., gt=0.0, description="Valor do Pix recebido em Reais")
    end_to_end_id: str = Field(..., description="Identificador único E2E do Pix")
