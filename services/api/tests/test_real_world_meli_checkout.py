import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.scrapers.base import RawListing


@pytest.mark.asyncio
async def test_real_world_meli_search_and_checkout_handoff(monkeypatch):
    # Mock dos listings brutos simulando a raspagem com tracking parameters do Mercado Livre
    mock_raw_listings = [
        RawListing(
            product_id="MLB2096580517",
            title="Caderno Sketchbook Desenho Artístico Profissional Esboço A4",
            url="https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico-profissional-esboco-a4-a4/p/MLB2096580517",
            display_price=29.90,
            cash_price=28.40,
            seller_name="Papelaria Prime",
            seller_reputation="platinum",
            image_url="https://http2.mlstatic.com/D_123-O.jpg"
        )
    ]

    async def mock_search(self, query: str, limit: int = 10):
        return mock_raw_listings

    monkeypatch.setattr("app.services.scrapers.mercadolivre.MercadoLivreScraper.search", mock_search)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Busca produtos via API do ACP
        res_search = await client.post(
            "/api/v1/search",
            json={
                "query": "caderno sketchbook desenho",
                "max_unit_price": 50.0,
                "prefer_best_cash_price": True
            }
        )
        assert res_search.status_code == 200
        data_search = res_search.json()
        assert data_search["total_results"] > 0
        results = data_search["results"]
        top_item = results[0]

        # Verifica sanitização da URL nos resultados da busca
        assert "#" not in top_item["url"]
        assert "polycard_client" not in top_item["url"]
        assert "tracking_id" not in top_item["url"]
        assert top_item["product_id"] == "MLB2096580517"

        # 2. Checkout passando apenas o product_id (cenário exato que quebrou no teste do usuário)
        res_checkout_id = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": "test_wallet_dummy",
                "order_items": [
                    {
                        "product_id_or_url": top_item["product_id"],
                        "quantity": 1,
                        "unit_price": top_item["pricing"]["display_price"],
                        "merchant_domain": top_item["merchant"]["domain"]
                    }
                ]
            }
        )
        assert res_checkout_id.status_code == 200
        data_checkout_id = res_checkout_id.json()
        assert data_checkout_id["status"] == "pending_human_approval"
        handoff_from_id = data_checkout_id["handoff_url"]

        # O link NÃO pode conter ?quantity=1 (que aciona verificação/bloqueio)
        assert "quantity=" not in handoff_from_id
        # O link deve ser a URL canônica real resolvida pelo ProductRegistry
        assert handoff_from_id == "https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico-profissional-esboco-a4-a4/p/MLB2096580517"

        # 3. Checkout passando com hífen ("MLB-2096580517")
        res_checkout_hyphen = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": "test_wallet_dummy",
                "order_items": [
                    {
                        "product_id_or_url": "MLB-2096580517",
                        "quantity": 1,
                        "unit_price": top_item["pricing"]["display_price"],
                        "merchant_domain": top_item["merchant"]["domain"]
                    }
                ]
            }
        )
        assert res_checkout_hyphen.status_code == 200
        assert res_checkout_hyphen.json()["handoff_url"] == "https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico-profissional-esboco-a4-a4/p/MLB2096580517"

        # 4. Checkout passando a URL completa com parâmetros sujos
        dirty_url = top_item["url"] + "#polycard_client=search-desktop&tracking_id=abc123xyz"
        res_checkout_url = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": "test_wallet_dummy",
                "order_items": [
                    {
                        "product_id_or_url": dirty_url,
                        "quantity": 2,
                        "unit_price": top_item["pricing"]["display_price"],
                        "merchant_domain": top_item["merchant"]["domain"]
                    }
                ]
            }
        )
        assert res_checkout_url.status_code == 200
        data_checkout_url = res_checkout_url.json()
        assert data_checkout_url["handoff_url"] == "https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico-profissional-esboco-a4-a4/p/MLB2096580517"
        assert "quantity=" not in data_checkout_url["handoff_url"]
