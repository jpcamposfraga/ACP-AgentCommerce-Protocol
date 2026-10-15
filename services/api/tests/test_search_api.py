import os
import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.services.scrapers.mercadolivre import MercadoLivreScraper

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mercadolivre_search.html")

@pytest.fixture
def mock_ml_listings():
    scraper = MercadoLivreScraper()
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    return scraper.parse_search_results(html, limit=10)

@pytest.mark.asyncio
async def test_search_api_endpoint(monkeypatch, mock_ml_listings):
    async def mock_search(self, query: str, limit: int = 10):
        return mock_ml_listings

    monkeypatch.setattr(MercadoLivreScraper, "search", mock_search)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Busca por iPhone 15 com teto de 6000
        res = await client.post(
            "/api/v1/search",
            json={"query": "iPhone 15", "max_unit_price": 6000.0, "prefer_best_cash_price": True}
        )
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
        assert "total_results" in data
        assert data["total_results"] > 0

        first = data["results"][0]
        assert "product_id" in first
        assert "pricing" in first
        assert first["pricing"]["best_payment_method"] == "pix"
        assert first["pricing"]["best_effective_price"] <= 6000.0
        assert first["merchant"]["domain"] == "mercadolivre.com.br"
        assert first["execution_type"] == "human_handoff"

@pytest.mark.asyncio
async def test_search_api_filters_accessories(monkeypatch):
    from app.services.scrapers.mercadolivre import RawListing

    # Listing com capinha (acessório) misturado na busca de celular
    mixed_listings = [
        RawListing(
            product_id="MLB-ACC-1",
            title="Capa Capinha Para iPhone 15 Silicone",
            url="https://mercadolivre.com.br/capa-iphone",
            display_price=49.90,
            cash_price=45.00,
            seller_name="Acessorios Celular",
            seller_reputation="gold"
        ),
        RawListing(
            product_id="MLB-IPHONE-1",
            title="Apple iPhone 15 128GB Preto",
            url="https://mercadolivre.com.br/iphone-15",
            display_price=5299.00,
            cash_price=4769.00,
            seller_name="Loja Apple",
            seller_reputation="official_store"
        )
    ]

    async def mock_search(self, query: str, limit: int = 10):
        return mixed_listings

    monkeypatch.setattr(MercadoLivreScraper, "search", mock_search)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/search",
            json={"query": "iPhone 15 128GB", "prefer_best_cash_price": True}
        )
        assert res.status_code == 200
        data = res.json()
        # Capinha deve ser filtrada pelo JevClassifier
        product_ids = [item["product_id"] for item in data["results"]]
        assert "MLB-ACC-1" not in product_ids
        assert "MLB-IPHONE-1" in product_ids

@pytest.mark.asyncio
async def test_merchant_status_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Domínio suportado do ecossistema ML
        res_ml = await client.get("/api/v1/merchant/status", params={"domain": "mercadolivre.com.br"})
        assert res_ml.status_code == 200
        data_ml = res_ml.json()
        assert data_ml["domain"] == "mercadolivre.com.br"
        assert data_ml["verification_status"] == "verified"
        assert "human_handoff" in data_ml["allowed_execution_modes"]
        assert data_ml["fraud_risk_score"] < 0.10

        # 2. Domínio malicioso / desconhecido
        res_fake = await client.get("/api/v1/merchant/status", params={"domain": "golpe-comprar-barato.tk"})
        assert res_fake.status_code == 200
        data_fake = res_fake.json()
        assert data_fake["verification_status"] == "blacklisted"
        assert data_fake["fraud_risk_score"] > 0.80

        # 3. Sem parâmetro domain -> 422
        res_missing = await client.get("/api/v1/merchant/status")
        assert res_missing.status_code in (400, 422)
