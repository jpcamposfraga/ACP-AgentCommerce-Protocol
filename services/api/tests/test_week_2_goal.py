import os
import time
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
async def test_week_2_goal_fast_search_and_pix_decomposition(monkeypatch, mock_ml_listings):
    """
    GOAL SEMANA 2:
    Query POST /api/v1/search para 'iPhone 15 128GB' responde em < 1.5s
    com decomposição de desconto Pix e 0 tokens LLM.
    """
    async def mock_search(self, query: str, limit: int = 10):
        return mock_ml_listings

    monkeypatch.setattr(MercadoLivreScraper, "search", mock_search)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        start_time = time.perf_counter()
        res = await client.post(
            "/api/v1/search",
            json={
                "query": "iPhone 15 128GB",
                "prefer_best_cash_price": True,
            }
        )
        elapsed_time = time.perf_counter() - start_time

        # 1. Latência deve ser muito abaixo de 1.5s (tipicamente < 50ms)
        assert elapsed_time < 1.5, f"Execution took too long: {elapsed_time:.3f}s"
        assert res.status_code == 200

        data = res.json()
        results = data["results"]
        assert len(results) >= 5

        # 2. Decomposição de Menor Preço Efetivo (Pix à vista + 2% ACP fee)
        has_pix_discount = False
        for item in results:
            pricing = item["pricing"]
            assert pricing["best_effective_price"] > 0
            assert pricing["fee_acp_estimated"] > 0
            assert item["merchant"]["trust_score"] >= 0.0
            assert item["execution_type"] in ["autonomous", "human_handoff"]

            if pricing["cash_discount_pct"] > 0:
                has_pix_discount = True
                assert pricing["best_payment_method"] == "pix"
                # O preço efetivo com Pix deve ser menor que o preço de vitrine
                assert pricing["best_effective_price"] < pricing["display_price"]

        assert has_pix_discount is True, "Ao menos um item deve conter desconto à vista via Pix"
