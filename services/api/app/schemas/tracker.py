from typing import Literal
from pydantic import BaseModel, Field


class TrackerRequest(BaseModel):
    product_url_or_id: str = Field(..., min_length=1, description="URL direta ou ID do produto a monitorar")
    target_price: float = Field(..., gt=0.0, description="Preço alvo para disparo de alerta ou compra")
    target_payment_method: Literal["pix", "credit_card", "any"] = Field(
        default="pix",
        description="Método de pagamento alvo do monitoramento"
    )
    min_stock: int = Field(default=1, ge=1, description="Estoque mínimo exigido")
    check_interval_seconds: int = Field(
        default=300,
        description="Intervalo em segundos entre checagens periódicas (mínimo de 60s)"
    )
    webhook_url: str | None = Field(
        default=None,
        description="URL de callback do agente a ser notificada quando o alvo for atingido"
    )


class TrackerResponse(BaseModel):
    tracker_id: str = Field(..., description="ID único do rastreador registrado")
    status: str = Field(default="active", description="Status do rastreador (active/paused/triggered)")
    product_url_or_id: str = Field(..., description="Produto monitorado")
    target_price: float = Field(..., description="Preço alvo configurado")
    current_best_price: float = Field(..., description="Menor preço efetivo detectado no momento do registro")
    check_interval_seconds: int = Field(..., description="Intervalo efetivo aplicado")
    warning: str | None = Field(
        default=None,
        description="Alerta de governança emitido caso o intervalo tenha sido ajustado"
    )
