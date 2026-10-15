from fastapi import APIRouter, Query
from app.schemas.merchant import MerchantStatusResponse

router = APIRouter(prefix="/api/v1/merchant", tags=["merchants"])

TRUSTED_DOMAINS = {
    "mercadolivre.com.br",
    "produto.mercadolivre.com.br",
    "amazon.com.br",
    "magazineluiza.com.br",
}

SUSPICIOUS_INDICATORS = {
    "golpe",
    "fake",
    "clonado",
    ".tk",
    ".xyz",
    ".top",
    ".click",
}


@router.get("/status", response_model=MerchantStatusResponse)
async def get_merchant_status(domain: str = Query(..., min_length=3, description="Domínio do lojista consultado")):
    normalized_domain = domain.strip().lower()

    # Checa padrões suspeitos / blacklisted
    is_suspicious = any(indicator in normalized_domain for indicator in SUSPICIOUS_INDICATORS)
    if is_suspicious:
        return MerchantStatusResponse(
            domain=normalized_domain,
            verification_status="blacklisted",
            has_well_known_acp_signature=False,
            allowed_execution_modes=[],
            fraud_risk_score=0.95,
        )

    # Checa se é um parceiro ou grande marketplace verificado
    if any(trusted in normalized_domain for trusted in TRUSTED_DOMAINS):
        return MerchantStatusResponse(
            domain=normalized_domain,
            verification_status="verified",
            has_well_known_acp_signature=False,
            allowed_execution_modes=["human_handoff"],
            fraud_risk_score=0.05,
        )

    # Domínio padrão não verificado
    return MerchantStatusResponse(
        domain=normalized_domain,
        verification_status="unverified",
        has_well_known_acp_signature=False,
        allowed_execution_modes=["human_handoff"],
        fraud_risk_score=0.45,
    )
