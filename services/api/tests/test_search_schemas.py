import pytest

def test_search_request_defaults_and_validation():
    from app.schemas.search import SearchRequest
    req = SearchRequest(query="iPhone 15 128GB")
    assert req.query == "iPhone 15 128GB"
    assert req.min_quantity == 1
    assert req.max_unit_price is None
    assert req.prefer_best_cash_price is True
    assert req.merchant_filter == "all"

def test_product_search_result_schema():
    from app.schemas.search import ProductSearchResult, ProductPricing, MerchantInfo
    merchant = MerchantInfo(domain="mercadolivre.com.br", is_verified=False, trust_score=0.95)
    pricing = ProductPricing(
        display_price=5299.00,
        best_effective_price=4769.10,
        best_payment_method="pix",
        cash_discount_pct=10.0,
        fee_acp_estimated=71.53
    )
    product = ProductSearchResult(
        product_id="MLB123456",
        title="Apple iPhone 15 128GB Preto",
        url="https://produto.mercadolivre.com.br/MLB-123456",
        merchant=merchant,
        pricing=pricing,
        stock_available=10,
        execution_type="human_handoff"
    )
    assert product.product_id == "MLB123456"
    assert product.pricing.best_effective_price == 4769.10
    assert product.merchant.domain == "mercadolivre.com.br"
    assert product.execution_type == "human_handoff"

def test_merchant_status_schema():
    from app.schemas.merchant import MerchantStatusResponse
    status = MerchantStatusResponse(
        domain="loja-parceira.com.br",
        verification_status="verified",
        has_well_known_acp_signature=True,
        allowed_execution_modes=["autonomous", "human_handoff"],
        fraud_risk_score=0.01
    )
    assert status.domain == "loja-parceira.com.br"
    assert status.verification_status == "verified"
    assert "autonomous" in status.allowed_execution_modes
