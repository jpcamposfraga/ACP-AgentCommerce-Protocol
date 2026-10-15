import asyncio
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession

from app.main import app
from app.core.database import Base, get_db
from app.core.config import settings

# Test in-memory / file SQLite engine
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test_acp.db"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"timeout": 30},
    echo=False
)
TestAsyncSessionLocal = async_sessionmaker(
    test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autocommit=False,
    autoflush=False
)

async def override_get_db():
    async with TestAsyncSessionLocal() as session:
        yield session

app.dependency_overrides[get_db] = override_get_db

@pytest_asyncio.fixture(autouse=True)
async def setup_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)

@pytest.mark.asyncio
async def test_wallet_limits_and_guards():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Cria carteira com teto de R$ 500 por ordem e limite diário de R$ 1000
        res = await client.post("/api/v1/wallets", json={
            "user_id": "test_user_1",
            "max_per_order": 500.0,
            "daily_limit": 1000.0
        })
        assert res.status_code == 201
        wallet = res.json()
        wallet_id = wallet["id"]

        # Recarrega R$ 1.000
        res = await client.post(f"/api/v1/wallets/{wallet_id}/topup", json={"amount": 1000.0})
        assert res.status_code == 200
        assert res.json()["balance"] == 1000.0

        # Tentativa de debitar R$ 600 (excede max_per_order de R$ 500)
        res = await client.post(f"/api/v1/wallets/{wallet_id}/debit", json={"amount": 600.0})
        assert res.status_code == 422
        assert "exceeds max allowed per order" in res.json()["detail"]

        # Débito válido de R$ 400 (400 + 2% = 408 total)
        res = await client.post(f"/api/v1/wallets/{wallet_id}/debit", json={"amount": 400.0})
        assert res.status_code == 200
        body = res.json()
        assert body["amount"] == 400.0
        assert body["platform_fee"] == 8.0
        assert body["total_debited"] == 408.0
        assert body["remaining_balance"] == 592.0

        # Bloqueio em carteira inativa
        async with TestAsyncSessionLocal() as session:
            from app.models.wallet import Wallet
            from sqlalchemy import select
            q = await session.execute(select(Wallet).where(Wallet.id == wallet_id))
            w = q.scalar_one()
            w.is_active = False
            await session.commit()

        res_inactive_topup = await client.post(f"/api/v1/wallets/{wallet_id}/topup", json={"amount": 100.0})
        assert res_inactive_topup.status_code == 400
        res_inactive_debit = await client.post(f"/api/v1/wallets/{wallet_id}/debit", json={"amount": 50.0})
        assert res_inactive_debit.status_code == 400

@pytest.mark.asyncio
async def test_goal_week_1_concurrency_integrity():
    """
    GOAL DA SEMANA 1:
    Disparar 10 requisições simultâneas de débito de R$ 100,00 contra uma carteira
    preparada para comportar exatamente 5 transações (5 x R$ 100 líquido + 2% taxa = R$ 510,00).
    Exatamente 5 devem suceder, 5 devem falhar com 402 Insufficient Funds,
    R$ 10,00 de taxa acumulada e saldo final exato de R$ 0,00 sem race condition.
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cria carteira com limites adequados
        res = await client.post("/api/v1/wallets", json={
            "user_id": "concurrent_trader_agent",
            "max_per_order": 1000.0,
            "daily_limit": 10000.0
        })
        assert res.status_code == 201
        wallet_id = res.json()["id"]

        # Recarga de R$ 510,00 (5 * (100 + 2% taxa))
        await client.post(f"/api/v1/wallets/{wallet_id}/topup", json={"amount": 510.0})

        # Prepara 10 requisições concorrentes de R$ 100 cada
        async def make_debit(idx: int):
            return await client.post(
                f"/api/v1/wallets/{wallet_id}/debit",
                json={"amount": 100.0, "reference_id": f"order_batch_{idx}"}
            )

        tasks = [make_debit(i) for i in range(10)]
        responses = await asyncio.gather(*tasks)

        success_responses = [r for r in responses if r.status_code == 200]
        insufficient_funds_responses = [r for r in responses if r.status_code == 402]

        # Validações exatas do GOAL
        assert len(success_responses) == 5, f"Esperado 5 sucessos, obtido: {len(success_responses)}"
        assert len(insufficient_funds_responses) == 5, f"Esperado 5 rejeições, obtido: {len(insufficient_funds_responses)}"

        total_fees = sum(r.json()["platform_fee"] for r in success_responses)
        assert total_fees == 10.0, f"Taxa esperada R$ 10.00, obtido: R$ {total_fees}"

        # Verifica saldo final da carteira
        wallet_res = await client.get(f"/api/v1/wallets/{wallet_id}")
        assert wallet_res.status_code == 200
        final_balance = wallet_res.json()["balance"]
        assert final_balance == 0.0, f"Saldo final esperado R$ 0.00, obtido: R$ {final_balance}"
