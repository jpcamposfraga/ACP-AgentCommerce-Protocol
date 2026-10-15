import pytest
from app.services.connectors.hybrid_meli import build_meli_handoff_url
from app.services.product_registry import product_registry


def test_build_meli_handoff_with_full_catalog_url():
    url = "https://www.mercadolivre.com.br/caderno-sketchbook/p/MLB2096580517#tracking=xyz&other=123"
    handoff = build_meli_handoff_url(url, quantity=1)
    # Must NOT contain tracking hash or broken quantity parameter
    assert handoff == "https://www.mercadolivre.com.br/caderno-sketchbook/p/MLB2096580517"


def test_build_meli_handoff_with_registered_id():
    product_registry.register("MLB2096580517", "https://www.mercadolivre.com.br/caderno/p/MLB2096580517")
    handoff = build_meli_handoff_url("MLB-2096580517", quantity=1)
    assert handoff == "https://www.mercadolivre.com.br/caderno/p/MLB2096580517"


def test_build_meli_handoff_fallback_catalog_id():
    # If not registered and matches catalog format MLB\d{8,}
    handoff = build_meli_handoff_url("MLB999888777", quantity=1)
    assert handoff == "https://www.mercadolivre.com.br/p/MLB999888777"


def test_build_meli_handoff_url_from_full_url():
    raw_url = "https://produto.mercadolivre.com.br/MLB-1002-apple-iphone?tracking_id=123&utm_source=fake"
    clean_url = build_meli_handoff_url(raw_url, quantity=1)
    assert clean_url == "https://produto.mercadolivre.com.br/MLB-1002-apple-iphone"
    assert "tracking_id" not in clean_url
    assert "utm_source" not in clean_url


def test_build_meli_handoff_url_fallback_standard_item_id():
    url = build_meli_handoff_url("MLB-1001", quantity=2)
    assert url == "https://produto.mercadolivre.com.br/MLB-1001"


def test_build_meli_handoff_url_rejects_untrusted_domain():
    with pytest.raises(ValueError, match="Domínio inválido"):
        build_meli_handoff_url("https://site-malicioso.com/MLB-1001")
