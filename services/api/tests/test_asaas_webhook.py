import pytest
from httpx import AsyncClient, ASGITransport
from sqlalchemy import select
from app.main import app
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from tests.conftest import TestAsyncSessionLocal


@pytest.mark.asyncio
async def test_asaas_webhook_credits_wallet_on_payment_received():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        wallet_res = await client.post(
            "/api/v1/wallets",
            json={"user_id": "user_wh_asaas", "max_per_order": 500.0, "daily_limit": 1000.0}
        )
        assert wallet_res.status_code == 201
        wallet_id = wallet_res.json()["id"]

        webhook_payload = {
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": "pay_asaas_wh_001",
                "value": 75.0,
                "netValue": 74.01,
                "externalReference": wallet_id,
                "status": "RECEIVED"
            }
        }

        res = await client.post("/api/v1/webhooks/asaas", json=webhook_payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "credited"
        assert data["amount"] == 75.0

        # Confere saldo
        check = await client.get(f"/api/v1/wallets/{wallet_id}")
        assert check.json()["balance"] == 75.0

        # Confere transação contábil
        async with TestAsyncSessionLocal() as session:
            stmt = select(Transaction).where(Transaction.reference_id == "pay_asaas_wh_001")
            tx_res = await session.execute(stmt)
            tx = tx_res.scalar_one()
            assert tx.type == "TOPUP"
            assert tx.amount == 75.0
            assert tx.status == "COMPLETED"


@pytest.mark.asyncio
async def test_asaas_webhook_idempotency_prevents_duplicate_credits():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        wallet_res = await client.post(
            "/api/v1/wallets",
            json={"user_id": "user_wh_idem", "max_per_order": 500.0, "daily_limit": 1000.0}
        )
        wallet_id = wallet_res.json()["id"]

        webhook_payload = {
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": "pay_asaas_wh_002",
                "value": 50.0,
                "netValue": 49.01,
                "externalReference": wallet_id,
                "status": "RECEIVED"
            }
        }

        # Primeiro envio
        res1 = await client.post("/api/v1/webhooks/asaas", json=webhook_payload)
        assert res1.status_code == 200
        assert res1.json()["status"] == "credited"

        # Segundo envio idêntico
        res2 = await client.post("/api/v1/webhooks/asaas", json=webhook_payload)
        assert res2.status_code == 200
        assert res2.json()["status"] == "already_processed"

        # Confere saldo (não pode duplicar para 100)
        check = await client.get(f"/api/v1/wallets/{wallet_id}")
        assert check.json()["balance"] == 50.0


@pytest.mark.asyncio
async def test_asaas_webhook_validates_token_when_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ASAAS_WEBHOOK_ACCESS_TOKEN", "super_secret_wh_token")

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        webhook_payload = {
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": "pay_asaas_wh_003",
                "value": 20.0,
                "externalReference": "dummy_wallet"
            }
        }

        # 1. Sem header de token -> 401
        res_no_token = await client.post("/api/v1/webhooks/asaas", json=webhook_payload)
        assert res_no_token.status_code == 401

        # 2. Token incorreto -> 401
        res_wrong_token = await client.post(
            "/api/v1/webhooks/asaas",
            json=webhook_payload,
            headers={"asaas-access-token": "wrong_token"}
        )
        assert res_wrong_token.status_code == 401


@pytest.mark.asyncio
async def test_asaas_webhook_ignores_unrelated_events():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        webhook_payload = {
            "event": "PAYMENT_CREATED",
            "payment": {"id": "pay_created_123"}
        }
        res = await client.post("/api/v1/webhooks/asaas", json=webhook_payload)
        assert res.status_code == 200
        assert res.json()["status"] == "ignored"
