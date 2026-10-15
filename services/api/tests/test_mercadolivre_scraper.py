import os
import pytest
from app.services.scrapers.mercadolivre import MercadoLivreScraper, RawListing, clean_meli_url

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mercadolivre_search.html")

def test_mercadolivre_parser_extracts_structured_listings():
    scraper = MercadoLivreScraper()
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    results = scraper.parse_search_results(html, limit=5)
    assert len(results) == 5

    # Produto 1: Loja Oficial com Pix
    p1 = results[0]
    assert isinstance(p1, RawListing)
    assert p1.product_id == "MLB-1001"
    assert "Apple iPhone 15 128GB Preto" in p1.title
    assert p1.display_price == 5299.0
    assert p1.cash_price == 4769.0
    assert p1.seller_reputation == "official_store"

    # Produto 2: Platinum com Pix
    p2 = results[1]
    assert p2.product_id == "MLB-1002"
    assert p2.display_price == 5899.0
    assert p2.cash_price == 5499.0
    assert p2.seller_reputation == "platinum"

    # Produto 3: Sem desconto de Pix
    p3 = results[2]
    assert p3.display_price == 5199.0
    assert p3.cash_price is None
    assert p3.seller_reputation == "gold"

def test_mercadolivre_parser_respects_limit():
    scraper = MercadoLivreScraper()
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()

    results = scraper.parse_search_results(html, limit=2)
    assert len(results) == 2

@pytest.mark.asyncio
async def test_mercadolivre_search_async(monkeypatch):
    scraper = MercadoLivreScraper()
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        mock_html = f.read()

    class MockResponse:
        text = mock_html

    class MockSession:
        async def __aenter__(self):
            return self
        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass
        async def get(self, url):
            return MockResponse()

    monkeypatch.setattr("app.services.scrapers.mercadolivre.AsyncSession", lambda **kwargs: MockSession())

    results = await scraper.search("iPhone 15", limit=3)
    assert len(results) == 3
    assert results[0].product_id == "MLB-1001"


def test_mercadolivre_parser_extracts_poly_card_listings():
    poly_html = """
    <li class="ui-search-layout__item">
      <div class="andes-card poly-card">
        <h3 class="poly-component__title-wrapper">
          <a href="https://produto.mercadolivre.com.br/MLB-99901-sketchbook-a4" class="poly-component__title">
            Caderno Sketchbook Desenho A4 240g
          </a>
        </h3>
        <div class="poly-component__price">
          <span class="andes-money-amount">
            <span class="andes-money-amount__fraction">42</span>
            <span class="andes-money-amount__cents">90</span>
          </span>
        </div>
      </div>
    </li>
    """
    scraper = MercadoLivreScraper()
    results = scraper.parse_search_results(poly_html, limit=1)
    assert len(results) == 1
    assert results[0].product_id == "MLB-99901"
    assert "Caderno Sketchbook" in results[0].title
    assert results[0].display_price == 42.90


def test_clean_meli_url_catalog_product():
    raw = "https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico/p/MLB2096580517#polycard_client=search-desktop&be_origin=backend&tracking_id=123"
    assert clean_meli_url(raw) == "https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico/p/MLB2096580517"


def test_clean_meli_url_standard_item():
    raw = "https://produto.mercadolivre.com.br/MLB-4286916381-sketchbook-caderno-desenho-_JM?searchVariation=123&tracking_id=456#polycard_client=search"
    assert clean_meli_url(raw) == "https://produto.mercadolivre.com.br/MLB-4286916381-sketchbook-caderno-desenho-_JM"
