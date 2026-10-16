import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_checkout_requires_valid_shipping_address():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_noship", "max_per_order": 100.0, "daily_limit": 200.0})
        wallet_id = w_res.json()["id"]

        # Attempt autonomous checkout without shipping address
        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{"product_id_or_url": "sku_1", "quantity": 1, "unit_price": 30.0, "merchant_domain": "lojaindependente.com.br"}],
                "shipping_profile_id": "nonexistent"
            }
        )
        assert chk_res.status_code == 422
        assert "endereço de entrega" in chk_res.json()["detail"].lower()


@pytest.mark.asyncio
async def test_checkout_meli_always_returns_human_handoff():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_meli", "max_per_order": 100.0, "daily_limit": 200.0})
        wallet_id = w_res.json()["id"]

        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{"product_id_or_url": "MLB12345678", "quantity": 1, "unit_price": 30.0, "merchant_domain": "mercadolivre.com.br"}]
            }
        )
        assert chk_res.status_code == 200
        data = chk_res.json()
        assert data["execution_type"] == "human_handoff"
        assert data["handoff_url"] is not None
        assert data["total_debited"] == 0.0


@pytest.mark.asyncio
async def test_simulated_open_store_marks_simulation_flag():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create wallet and deposit balance
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_sim", "max_per_order": 100.0, "daily_limit": 200.0})
        wallet_id = w_res.json()["id"]
        # Credit wallet via internal topup or deposit test
        await client.post(f"/api/v1/wallets/{wallet_id}/topup", json={"amount": 80.0})

        # Add shipping address
        addr_res = await client.post("/api/v1/shipping-profiles", json={
            "wallet_id": wallet_id,
            "recipient_name": "Teste",
            "cpf_cnpj": "12345678909",
            "phone": "11999998888",
            "postal_code": "01310-100",
            "number": "100"
        })
        profile_id = addr_res.json()["id"]

        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{"product_id_or_url": "sku_open_1", "quantity": 1, "unit_price": 40.0, "merchant_domain": "lojaparceira.com.br"}],
                "shipping_profile_id": profile_id
            }
        )
        assert chk_res.status_code == 200
        data = chk_res.json()
        assert "is_simulation" in data


@pytest.mark.asyncio
async def test_checkout_open_store_with_url_invokes_playwright_worker_and_pays(monkeypatch):
    from unittest.mock import AsyncMock
    from app.services.checkout_worker.orchestrator import PlaywrightCheckoutWorker, CheckoutWorkerResult

    mock_worker_result = CheckoutWorkerResult(
        status="SUCCESS",
        order_id="order_pw_test_99",
        pix_copia_e_cola="00020126580014br.gov.bcb.pix0136test-pix-uuid52040000530398654050.005802BR5916Loja Real6009SP62070503***63041234"
    )
    monkeypatch.setattr(
        PlaywrightCheckoutWorker,
        "execute",
        AsyncMock(return_value=mock_worker_result)
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_pw_success", "max_per_order": 200.0, "daily_limit": 500.0})
        wallet_id = w_res.json()["id"]
        await client.post(f"/api/v1/wallets/{wallet_id}/topup", json={"amount": 100.0})

        addr_res = await client.post("/api/v1/shipping-profiles", json={
            "wallet_id": wallet_id,
            "recipient_name": "Comprador Real",
            "cpf_cnpj": "12345678909",
            "phone": "11999998888",
            "postal_code": "01310-100",
            "number": "100"
        })
        profile_id = addr_res.json()["id"]

        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{
                    "product_id_or_url": "https://lojareal.com.br/produtos/tenis-corrida",
                    "quantity": 1,
                    "unit_price": 50.0,
                    "merchant_domain": "lojareal.com.br"
                }],
                "shipping_profile_id": profile_id
            }
        )
        assert chk_res.status_code == 200
        data = chk_res.json()
        assert data["status"] == "completed"
        assert data["execution_type"] == "autonomous"
        assert data["order_id"] == "order_pw_test_99"
        # 50.0 + 2% (1.0) = 51.0
        assert data["total_debited"] == 51.0
        assert data["receipt"]["amount_transferred"] == 50.0
        assert data["receipt"]["acp_fee_retained"] == 1.0


@pytest.mark.asyncio
async def test_checkout_open_store_worker_failure_aborts_without_debiting_wallet(monkeypatch):
    from unittest.mock import AsyncMock
    from app.services.checkout_worker.orchestrator import PlaywrightCheckoutWorker

    monkeypatch.setattr(
        PlaywrightCheckoutWorker,
        "execute",
        AsyncMock(side_effect=RuntimeError("Timeout waiting for Pix element on store"))
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_pw_fail", "max_per_order": 200.0, "daily_limit": 500.0})
        wallet_id = w_res.json()["id"]
        await client.post(f"/api/v1/wallets/{wallet_id}/topup", json={"amount": 100.0})

        addr_res = await client.post("/api/v1/shipping-profiles", json={
            "wallet_id": wallet_id,
            "recipient_name": "Comprador Real",
            "cpf_cnpj": "12345678909",
            "phone": "11999998888",
            "postal_code": "01310-100",
            "number": "100"
        })
        profile_id = addr_res.json()["id"]

        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{
                    "product_id_or_url": "https://lojareal.com.br/produtos/tenis-falha",
                    "quantity": 1,
                    "unit_price": 50.0,
                    "merchant_domain": "lojareal.com.br"
                }],
                "shipping_profile_id": profile_id
            }
        )
        assert chk_res.status_code == 502
        assert "Falha ao realizar checkout autônomo" in chk_res.json()["detail"]

        # Confirma que saldo de R$ 100 permaneceu 100% intacto
        w_check = await client.get(f"/api/v1/wallets/{wallet_id}")
        assert w_check.json()["balance"] == 100.0

