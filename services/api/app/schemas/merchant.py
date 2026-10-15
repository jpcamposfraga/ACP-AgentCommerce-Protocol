from typing import Literal
from pydantic import BaseModel, Field

class MerchantStatusResponse(BaseModel):
    domain: str = Field(..., description="Domínio do lojista consultado")
    verification_status: Literal["verified", "unverified", "blacklisted"] = Field(
        ...,
        description="Status de conformidade e auditoria"
    )
    has_well_known_acp_signature: bool = Field(
        default=False,
        description="Indica se o domínio assina digitalmente seu catálogo em /.well-known/agent-commerce.json"
    )
    allowed_execution_modes: list[str] = Field(
        default_factory=lambda: ["human_handoff"],
        description="Modos de execução autorizados para o domínio"
    )
    fraud_risk_score: float = Field(
        default=0.0,
        ge=0.0,
        le=1.0,
        description="Probabilidade estimada de fraude ou honeypot"
    )
