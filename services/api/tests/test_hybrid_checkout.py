import pytest
from app.services.connectors.hybrid_meli import build_meli_handoff_url


def test_build_meli_handoff_url_from_id():
    url = build_meli_handoff_url("MLB-1001", quantity=2)
    assert url == "https://produto.mercadolivre.com.br/MLB-1001?quantity=2"


def test_build_meli_handoff_url_from_full_url():
    raw_url = "https://produto.mercadolivre.com.br/MLB-1002-apple-iphone?tracking_id=123&utm_source=fake"
    clean_url = build_meli_handoff_url(raw_url, quantity=1)
    assert clean_url == "https://produto.mercadolivre.com.br/MLB-1002-apple-iphone?quantity=1"
    assert "tracking_id" not in clean_url
    assert "utm_source" not in clean_url


def test_build_meli_handoff_url_rejects_untrusted_domain():
    with pytest.raises(ValueError, match="Domínio inválido"):
        build_meli_handoff_url("https://site-malicioso.com/MLB-1001")
