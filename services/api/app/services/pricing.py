from app.core.config import settings
from app.schemas.search import ProductPricing

def calculate_effective_price(
    display_price: float,
    cash_price: float | None = None,
    fee_pct: float | None = None
) -> ProductPricing:
    """
    Calcula o Menor Preço Efetivo para agentes autônomos.
    Captura automaticamente o desconto à vista (Pix) quando disponível
    e embute a taxa de intermediação do ACP.
    """
    pct = fee_pct if fee_pct is not None else settings.ACP_PLATFORM_FEE_PCT

    if cash_price is not None and 0 < cash_price < display_price:
        base_chosen = cash_price
        method = "pix"
        discount_pct = round(((display_price - cash_price) / display_price) * 100.0, 2)
    else:
        base_chosen = display_price
        method = "credit_card"
        discount_pct = 0.0

    fee = round(base_chosen * pct, 2)
    effective_price = round(base_chosen + fee, 2)

    return ProductPricing(
        display_price=round(display_price, 2),
        best_effective_price=effective_price,
        best_payment_method=method,
        cash_discount_pct=discount_pct,
        fee_acp_estimated=fee
    )
