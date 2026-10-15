import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app


@pytest.mark.asyncio
async def test_create_tracker_with_valid_interval():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "product_url_or_id": "MLB-1001",
            "target_price": 4500.0,
            "target_payment_method": "pix",
            "min_stock": 1,
            "check_interval_seconds": 300,
            "webhook_url": "https://meu-agente.com/alertas"
        }
        res = await client.post("/api/v1/trackers", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "active"
        assert data["tracker_id"].startswith("tr_")
        assert data["check_interval_seconds"] == 300
        assert data["warning"] is None
        assert data["current_best_price"] > 0


@pytest.mark.asyncio
async def test_create_tracker_clamps_aggressive_interval_lock():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Tenta intervalo abusivo de 15 segundos
        payload = {
            "product_url_or_id": "MLB-1002",
            "target_price": 5000.0,
            "check_interval_seconds": 15
        }
        res = await client.post("/api/v1/trackers", json=payload)
        assert res.status_code == 200
        data = res.json()
        # Deve ter sido travado em 60 segundos com aviso de proteção
        assert data["check_interval_seconds"] == 60
        assert data["warning"] is not None
        assert "60 segundos" in data["warning"]
