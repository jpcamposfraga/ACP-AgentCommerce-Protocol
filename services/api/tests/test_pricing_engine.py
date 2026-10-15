import pytest
from app.services.pricing import calculate_effective_price

def test_pricing_engine_with_pix_discount():
    # R$ 5000 parcelado, R$ 4500 no Pix (10% de desconto à vista), taxa 2% (R$ 90,00)
    pricing = calculate_effective_price(display_price=5000.0, cash_price=4500.0, fee_pct=0.02)
    assert pricing.display_price == 5000.0
    assert pricing.best_effective_price == 4590.0
    assert pricing.best_payment_method == "pix"
    assert pricing.cash_discount_pct == 10.0
    assert pricing.fee_acp_estimated == 90.0

def test_pricing_engine_without_cash_discount():
    # R$ 1000 parcelado, sem desconto no Pix (ou cash_price não informado)
    pricing = calculate_effective_price(display_price=1000.0, cash_price=None, fee_pct=0.02)
    assert pricing.display_price == 1000.0
    assert pricing.best_effective_price == 1020.0
    assert pricing.best_payment_method == "credit_card"
    assert pricing.cash_discount_pct == 0.0
    assert pricing.fee_acp_estimated == 20.0

def test_pricing_engine_uses_settings_default_fee():
    from app.core.config import settings
    pricing = calculate_effective_price(display_price=200.0, cash_price=180.0)
    expected_fee = round(180.0 * settings.ACP_PLATFORM_FEE_PCT, 2)
    assert pricing.fee_acp_estimated == expected_fee
    assert pricing.best_effective_price == round(180.0 + expected_fee, 2)

def test_pricing_engine_handles_equal_or_invalid_cash_price():
    # Preço à vista maior ou igual ao de vitrine não deve ser considerado desconto
    pricing = calculate_effective_price(display_price=500.0, cash_price=550.0, fee_pct=0.02)
    assert pricing.best_payment_method == "credit_card"
    assert pricing.cash_discount_pct == 0.0
    assert pricing.best_effective_price == 510.0
