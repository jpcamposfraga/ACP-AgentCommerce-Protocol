import pytest

def test_registry_contains_at_least_10_ecommerce_connectors():
    from app.services.scrapers.registry import ScraperRegistry
    registry = ScraperRegistry()
    all_scrapers = registry.get_all_scrapers()
    assert len(all_scrapers) >= 10
    domains = {s.domain for s in all_scrapers}
    assert "mercadolivre.com.br" in domains
    assert "amazon.com.br" in domains
    assert "amazon.com" in domains
    assert "ebay.com" in domains
    assert "kabum.com.br" in domains
    assert "kalunga.com.br" in domains
    assert "magazineluiza.com.br" in domains
    assert "shopee.com.br" in domains
    assert "walmart.com" in domains
    assert "aliexpress.com" in domains

def test_registry_filters_by_region():
    from app.services.scrapers.registry import ScraperRegistry
    registry = ScraperRegistry()
    br_scrapers = registry.get_scrapers(region="BR")
    us_scrapers = registry.get_scrapers(region="US")
    
    assert any(s.domain == "mercadolivre.com.br" for s in br_scrapers)
    assert not any(s.domain == "mercadolivre.com.br" for s in us_scrapers)
    assert any(s.domain == "amazon.com" for s in us_scrapers)

def test_registry_filters_by_user_whitelist():
    from app.services.scrapers.registry import ScraperRegistry
    registry = ScraperRegistry()
    filtered = registry.get_scrapers(region="BR", allowed_domains=["kabum.com.br", "kalunga.com.br"])
    assert len(filtered) == 2
    assert {s.domain for s in filtered} == {"kabum.com.br", "kalunga.com.br"}
