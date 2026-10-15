import time
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.main import app
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from tests.conftest import TestAsyncSessionLocal


@pytest.mark.asyncio
async def test_week_3_goal_autonomous_and_hybrid_execution():
    """
    GOAL SEMANA 3:
    1. Modo Autônomo: Checkout para loja parceira debita R$ 500 da carteira + R$ 10 (2%) de taxa ACP,
       emite Pix no sandbox BaaS e retorna 'completed' com recibo em < 3 segundos.
    2. Modo Híbrido: Checkout para o Mercado Livre identifica ecossistema fechado e retorna
       'pending_human_approval' com URL válida de carrinho em 1 clique.
    """
    # 1. Setup da Carteira com Saldo de R$ 1.000,00
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="user_week3_goal",
            balance=1000.0,
            currency="BRL",
            max_per_order=2000.0,
            daily_limit=5000.0,
            spent_today=0.0
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # ==========================================
        # PARTE 1: MODO AUTÔNOMO (LOJA PARCEIRA)
        # ==========================================
        start_time = time.perf_counter()
        res_auto = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [
                    {
                        "product_id_or_url": "SKU-WEEK3-PARCEIRO",
                        "quantity": 1,
                        "unit_price": 500.0,
                        "merchant_domain": "lojaparceira.com.br"
                    }
                ],
                "shipping_profile_id": "sp_sede_principal"
            }
        )
        elapsed_time = time.perf_counter() - start_time

        # Critério: Conclusão em menos de 3 segundos
        assert elapsed_time < 3.0, f"Tempo de resposta excedeu 3s: {elapsed_time:.3f}s"
        assert res_auto.status_code == 200

        data_auto = res_auto.json()
        assert data_auto["status"] == "completed"
        assert data_auto["execution_type"] == "autonomous"
        # Total debitado: R$ 500 do produto + R$ 10 (2% ACP take-rate) = R$ 510,00
        assert data_auto["total_debited"] == 510.0
        assert data_auto["receipt"] is not None
        assert data_auto["receipt"]["amount_transferred"] == 500.0
        assert data_auto["receipt"]["acp_fee_retained"] == 10.0
        assert data_auto["receipt"]["pix_end_to_end_id"].startswith("E")

        # ==========================================
        # PARTE 2: MODO HÍBRIDO (MERCADO LIVRE)
        # ==========================================
        res_hybrid = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [
                    {
                        "product_id_or_url": "MLB-998877",
                        "quantity": 2,
                        "unit_price": 4500.0,
                        "merchant_domain": "mercadolivre.com.br"
                    }
                ],
                "shipping_profile_id": "sp_sede_principal"
            }
        )
        assert res_hybrid.status_code == 200
        data_hybrid = res_hybrid.json()
        assert data_hybrid["status"] == "pending_human_approval"
        assert data_hybrid["execution_type"] == "human_handoff"
        assert data_hybrid["total_debited"] == 0.0
        assert data_hybrid["handoff_url"] is not None
        assert "produto.mercadolivre.com.br/MLB-998877?quantity=2" in data_hybrid["handoff_url"]
        assert data_hybrid["receipt"] is None

    # ==========================================
    # PARTE 3: VERIFICAÇÃO DE INTEGRIDADE CONTÁBIL
    # ==========================================
    async with TestAsyncSessionLocal() as session:
        stmt = select(Wallet).where(Wallet.id == wallet_id)
        result = await session.execute(stmt)
        updated_wallet = result.scalar_one()

        # Saldo inicial (1000) - Débito autônomo (510) - Débito híbrido (0) = 490
        assert updated_wallet.balance == 490.0

        # Verifica registro da transação
        stmt_tx = select(Transaction).where(Transaction.wallet_id == wallet_id)
        tx_res = await session.execute(stmt_tx)
        transactions = tx_res.scalars().all()
        assert len(transactions) == 1
        tx = transactions[0]
        assert tx.type == "DEBIT_PURCHASE"
        assert tx.amount == 510.0
        assert tx.platform_fee == 10.0
        assert tx.net_amount == 500.0
