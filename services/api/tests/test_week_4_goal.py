import os
import time
import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from app.main import app
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.services.scrapers.mercadolivre import MercadoLivreScraper
from tests.conftest import TestAsyncSessionLocal

FIXTURE_PATH = os.path.join(os.path.dirname(__file__), "fixtures", "mercadolivre_search.html")


@pytest.fixture
def mock_ml_listings():
    scraper = MercadoLivreScraper()
    with open(FIXTURE_PATH, "r", encoding="utf-8") as f:
        html = f.read()
    return scraper.parse_search_results(html, limit=10)


@pytest.mark.asyncio
async def test_week_4_goal_complete_agent_mission_e2e(monkeypatch, mock_ml_listings):
    """
    GOAL SEMANA 4 (GOAL FINAL DO MVP):
    Missão Completa do Agente Autônomo em Produção Local:
    'Pesquise o iPhone 15, verifique se há estoque para 2 unidades e, se o preço à vista
    no Pix estiver abaixo de R$ 5.000,00 cada, compre usando o meu saldo pré-pago na loja parceira;
    caso encontre apenas no Mercado Livre, me entregue o link do carrinho pronto.'

    Validação:
    1. Invoca search_products (com JevClassifier + PricingEngine).
    2. Analisa opções e seleciona o melhor preço com Pix.
    3. Invoca checkout (modo autônomo e modo híbrido).
    4. Valida débito de saldo com taxa retida e comprovante Pix.
    5. Tempo total inferior a 15 segundos.
    """
    # Mock do scraper para ambiente de teste hermético e determinístico
    async def mock_search(self, query: str, limit: int = 10):
        return mock_ml_listings

    monkeypatch.setattr(MercadoLivreScraper, "search", mock_search)

    # 1. Setup da Carteira com Saldo Pré-Pago de R$ 15.000,00
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="agent_user_week4_goal",
            balance=15000.0,
            currency="BRL",
            max_per_order=15000.0,
            daily_limit=20000.0,
            spent_today=0.0
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    mission_start_time = time.perf_counter()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # =========================================================================
        # PASSO 1: Agente invoca search_products via MCP/API
        # =========================================================================
        search_res = await client.post(
            "/api/v1/search",
            json={
                "query": "iPhone 15 128GB",
                "min_quantity": 2,
                "prefer_best_cash_price": True
            }
        )
        assert search_res.status_code == 200
        search_data = search_res.json()
        results = search_data["results"]
        assert len(results) > 0

        # =========================================================================
        # PASSO 2: Agente analisa ofertas e identifica menor preço Pix
        # =========================================================================
        best_offer = results[0]  # Resultados já vêm ordenados por best_effective_price
        assert best_offer["pricing"]["best_payment_method"] == "pix"
        best_price = best_offer["pricing"]["best_effective_price"]

        # =========================================================================
        # PASSO 3A: Se o item for de Loja Parceira (< 5000), executa Checkout Autônomo
        # =========================================================================
        partner_checkout_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [
                    {
                        "product_id_or_url": "SKU-IPHONE-PARTNER",
                        "quantity": 2,
                        "unit_price": 4769.0,
                        "merchant_domain": "lojaparceira.com.br"
                    }
                ],
                "shipping_profile_id": "sp_deposito_sp"
            }
        )
        assert partner_checkout_res.status_code == 200
        partner_data = partner_checkout_res.json()
        assert partner_data["status"] == "completed"
        assert partner_data["execution_type"] == "autonomous"
        # 2 unidades * 4769 = 9538.00 + 2% taxa ACP (190.76) = 9728.76
        assert partner_data["total_debited"] == 9728.76
        assert partner_data["receipt"]["amount_transferred"] == 9538.0
        assert partner_data["receipt"]["acp_fee_retained"] == 190.76
        assert partner_data["receipt"]["pix_end_to_end_id"].startswith("E")

        # =========================================================================
        # PASSO 3B: Se for no Mercado Livre, entrega link de carrinho pronto (Híbrido)
        # =========================================================================
        meli_checkout_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [
                    {
                        "product_id_or_url": best_offer["product_id"],
                        "quantity": 2,
                        "unit_price": best_price,
                        "merchant_domain": "mercadolivre.com.br"
                    }
                ],
                "shipping_profile_id": "sp_deposito_sp"
            }
        )
        assert meli_checkout_res.status_code == 200
        meli_data = meli_checkout_res.json()
        assert meli_data["status"] == "pending_human_approval"
        assert meli_data["execution_type"] == "human_handoff"
        assert meli_data["handoff_url"] is not None
        assert "produto.mercadolivre.com.br/MLB-1005" in meli_data["handoff_url"]
        assert "quantity=" not in meli_data["handoff_url"]

    total_mission_time = time.perf_counter() - mission_start_time

    # =========================================================================
    # PASSO 4: Verificação do Tempo Total (< 15 segundos)
    # =========================================================================
    assert total_mission_time < 15.0, f"Tempo de missão excedeu 15s: {total_mission_time:.3f}s"

    # =========================================================================
    # PASSO 5: Conferência de Integridade Contábil no Ledger
    # =========================================================================
    async with TestAsyncSessionLocal() as session:
        stmt = select(Wallet).where(Wallet.id == wallet_id)
        res = await session.execute(stmt)
        updated_wallet = res.scalar_one()
        # 15000 - 9728.76 = 5271.24
        assert round(updated_wallet.balance, 2) == 5271.24

        stmt_tx = select(Transaction).where(Transaction.wallet_id == wallet_id)
        tx_res = await session.execute(stmt_tx)
        transactions = tx_res.scalars().all()
        assert len(transactions) == 1
        assert transactions[0].type == "DEBIT_PURCHASE"
        assert transactions[0].amount == 9728.76
