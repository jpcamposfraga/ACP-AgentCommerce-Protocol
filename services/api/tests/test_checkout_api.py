import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.main import app
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from tests.conftest import TestAsyncSessionLocal


@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")


@pytest.mark.asyncio
async def test_checkout_hybrid_meli():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "wallet_id": "wallet_dummy_123",
            "order_items": [
                {
                    "product_id_or_url": "MLB-1001",
                    "quantity": 1,
                    "unit_price": 4769.0,
                    "merchant_domain": "mercadolivre.com.br"
                }
            ],
            "shipping_profile_id": "sp_galpao_sp"
        }
        res = await client.post("/api/v1/checkout", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "pending_human_approval"
        assert data["execution_type"] == "human_handoff"
        assert data["total_debited"] == 0.0
        assert data["handoff_url"] is not None
        assert "produto.mercadolivre.com.br/MLB-1001" in data["handoff_url"]
        assert data["receipt"] is None


@pytest.mark.asyncio
async def test_checkout_autonomous_partner_success():
    # 1. Cria carteira com saldo suficiente de R$ 1000
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="user_checkout_auto",
            balance=1000.0,
            currency="BRL",
            max_per_order=1000.0,
            daily_limit=5000.0,
            spent_today=0.0
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "wallet_id": wallet_id,
            "order_items": [
                {
                    "product_id_or_url": "SKU-AUTO-500",
                    "quantity": 1,
                    "unit_price": 500.0,
                    "merchant_domain": "loja-parceira.com.br"
                }
            ],
            "shipping_profile_id": "sp_galpao_sp"
        }
        res = await client.post("/api/v1/checkout", json=payload)
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["execution_type"] == "autonomous"
        # Total debitado = R$ 500 + 2% de taxa (R$ 10) = R$ 510.0
        assert data["total_debited"] == 510.0
        assert data["receipt"] is not None
        assert data["receipt"]["amount_transferred"] == 500.0
        assert data["receipt"]["acp_fee_retained"] == 10.0
        assert data["receipt"]["pix_end_to_end_id"].startswith("E")

    # 2. Confere saldo debitado e transação no banco
    async with TestAsyncSessionLocal() as session:
        stmt = select(Wallet).where(Wallet.id == wallet_id)
        result = await session.execute(stmt)
        updated_wallet = result.scalar_one()
        assert updated_wallet.balance == 490.0  # 1000 - 510 = 490

        stmt_tx = select(Transaction).where(Transaction.wallet_id == wallet_id)
        tx_res = await session.execute(stmt_tx)
        tx = tx_res.scalar_one()
        assert tx.type == "DEBIT_PURCHASE"
        assert tx.amount == 510.0
        assert tx.platform_fee == 10.0
        assert tx.net_amount == 500.0


@pytest.mark.asyncio
async def test_checkout_autonomous_insufficient_balance():
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="user_low_funds",
            balance=100.0,
            currency="BRL",
            max_per_order=1000.0,
            daily_limit=5000.0
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "wallet_id": wallet_id,
            "order_items": [
                {
                    "product_id_or_url": "SKU-AUTO-500",
                    "quantity": 1,
                    "unit_price": 500.0,
                    "merchant_domain": "loja-parceira.com.br"
                }
            ],
            "shipping_profile_id": "sp_default"
        }
        res = await client.post("/api/v1/checkout", json=payload)
        assert res.status_code in (400, 402)


@pytest.mark.asyncio
async def test_checkout_autonomous_exceeds_max_per_order():
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="user_max_limit",
            balance=5000.0,
            currency="BRL",
            max_per_order=300.0,  # teto de 300
            daily_limit=5000.0
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        payload = {
            "wallet_id": wallet_id,
            "order_items": [
                {
                    "product_id_or_url": "SKU-EXPENSIVE",
                    "quantity": 1,
                    "unit_price": 400.0,
                    "merchant_domain": "loja-parceira.com.br"
                }
            ],
            "shipping_profile_id": "sp_default"
        }
        res = await client.post("/api/v1/checkout", json=payload)
        assert res.status_code == 400
        assert "max_per_order" in res.json()["detail"].lower()
