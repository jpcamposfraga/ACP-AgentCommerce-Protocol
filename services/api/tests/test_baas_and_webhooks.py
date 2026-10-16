import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.main import app
from app.core.database import Base, get_db
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.services.baas import BaaSPixClient

from tests.conftest import TestAsyncSessionLocal

@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_baas_client_send_pix_payout():
    baas = BaaSPixClient()
    result = await baas.send_pix_payout(
        amount=500.0,
        pix_key="chave-pix-lojista@parceiro.com.br",
        description="Pagamento pedido #12345"
    )
    assert result["status"] == "CONFIRMED"
    assert "end_to_end_id" in result
    assert result["amount"] == 500.0
    assert result["end_to_end_id"].startswith("E")


@pytest.mark.asyncio
async def test_baas_client_delegates_to_asaas_when_configured(monkeypatch):
    baas = BaaSPixClient()
    monkeypatch.setattr("app.core.config.settings.ASAAS_API_KEY", "real_key_123")

    async def mock_transfer(self, value, pix_key, pix_key_type=None, description=""):
        return {
            "status": "DONE",
            "endToEndIdentifier": "E_REAL_1234567890",
            "value": value,
            "netValue": value
        }

    monkeypatch.setattr("app.services.baas_asaas.AsaasClient.send_pix_transfer", mock_transfer)

    result = await baas.send_pix_payout(
        amount=250.0,
        pix_key="pix@loja.com",
        description="Pedido Real #999"
    )
    assert result["status"] == "CONFIRMED"
    assert result["end_to_end_id"] == "E_REAL_1234567890"
    assert result["amount"] == 250.0


@pytest.mark.asyncio
async def test_webhook_pix_cash_in_credits_wallet(client):
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="user_topup_test",
            balance=0.0,
            currency="BRL",
            max_per_order=1000.0,
            daily_limit=5000.0,
            spent_today=0.0
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    webhook_payload = {
        "event": "pix_received",
        "payment_id": "pay_test_001",
        "wallet_id": wallet_id,
        "amount": 750.0,
        "end_to_end_id": "E_SANDBOX_0001"
    }

    res = await client.post("/api/v1/webhooks/pix", json=webhook_payload)
    assert res.status_code == 200
    data = res.json()
    assert data["status"] in ("credited", "COMPLETED", "success")

    async with TestAsyncSessionLocal() as read_session:
        stmt = select(Wallet).where(Wallet.id == wallet_id)
        result = await read_session.execute(stmt)
        updated_wallet = result.scalar_one()
        assert updated_wallet.balance == 750.0

        stmt_tx = select(Transaction).where(Transaction.wallet_id == wallet_id)
        tx_res = await read_session.execute(stmt_tx)
        tx = tx_res.scalar_one()
        assert tx.type == "TOPUP"
        assert tx.amount == 750.0
        assert tx.reference_id == "E_SANDBOX_0001"


@pytest.mark.asyncio
async def test_webhook_pix_idempotency_prevents_double_credit(client):
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="user_idempotency_test",
            balance=100.0,
            currency="BRL"
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    payload = {
        "event": "pix_received",
        "payment_id": "pay_test_002",
        "wallet_id": wallet_id,
        "amount": 200.0,
        "end_to_end_id": "E_SANDBOX_0002"
    }

    res1 = await client.post("/api/v1/webhooks/pix", json=payload)
    assert res1.status_code == 200

    res2 = await client.post("/api/v1/webhooks/pix", json=payload)
    assert res2.status_code == 200
    data2 = res2.json()
    assert data2["status"] == "already_processed"

    async with TestAsyncSessionLocal() as read_session:
        stmt = select(Wallet).where(Wallet.id == wallet_id)
        result = await read_session.execute(stmt)
        updated_wallet = result.scalar_one()
        assert updated_wallet.balance == 300.0
