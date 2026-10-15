import pytest
from httpx import ASGITransport, AsyncClient
from app.main import app
from app.models.wallet import Wallet
from tests.conftest import TestAsyncSessionLocal

@pytest.mark.asyncio
async def test_virtual_card_checkout_locks_exact_amount_and_debits_wallet():
    async with TestAsyncSessionLocal() as session:
        wallet = Wallet(
            user_id="user_vcard_test",
            balance=500.0,
            currency="BRL",
            max_per_order=1000.0,
            daily_limit=2000.0
        )
        session.add(wallet)
        await session.commit()
        wallet_id = wallet.id

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Checkout em loja aberta internacional ou sem Pix (modo virtual card autônomo)
        res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [
                    {
                        "product_id_or_url": "SKU-VCARD-PROD",
                        "quantity": 1,
                        "unit_price": 100.0,
                        "merchant_domain": "loja-aberta-shopify.com"
                    }
                ],
                "preferred_autonomous_payment": "virtual_card"
            }
        )
        assert res.status_code == 200
        data = res.json()
        assert data["status"] == "completed"
        assert data["execution_type"] == "autonomous"
        # Total debitado: 100 + 2% taxa ACP = 102.00
        assert data["total_debited"] == 102.00
        assert data["virtual_card"] is not None
        vcard = data["virtual_card"]
        assert vcard["exact_amount_locked"] == 100.00
        assert vcard["status"] == "ACTIVE_ONE_TIME"
        assert len(vcard["cvv"]) == 3
        assert "********" in vcard["masked_pan"]
        assert vcard["masked_pan"].startswith("4111")
