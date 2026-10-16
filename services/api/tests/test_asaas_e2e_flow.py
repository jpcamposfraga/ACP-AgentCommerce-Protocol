import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app


@pytest.mark.asyncio
async def test_full_asaas_cash_in_and_autonomous_cash_out_cycle(monkeypatch):
    """
    Validação E2E do Ciclo Financeiro do Asaas no ACP:
    1. Criação de carteira com saldo R$ 0.
    2. Geração de Pix Copia-e-Cola para recarga de R$ 100,00.
    3. Simulação de Webhook do Asaas confirmando recebimento do Pix.
    4. Verificação de saldo creditado (R$ 100,00).
    5. Agente realiza compra autônoma em Loja Parceira de R$ 50,00 + taxa ACP de 2% (R$ 51,00).
    6. Verificação de liquidação bancária via BaaS Pix e saldo remanescente exato de R$ 49,00.
    """
    # Configura Asaas simulado em produção
    monkeypatch.setattr("app.core.config.settings.ASAAS_API_KEY", "real_key_simulated")
    monkeypatch.setattr("app.core.config.settings.ASAAS_WEBHOOK_ACCESS_TOKEN", "token_wh_val")

    # Mocks das chamadas externas ao Asaas
    async def mock_charge(self, value, description, external_reference, customer_name=None, customer_cpf_cnpj=None):
        return {
            "payment_id": "pay_live_asaas_999",
            "value": value,
            "copy_paste_payload": "00020126580014br.gov.bcb.pix0136asaaspayload...",
            "encoded_image": "data:image/png;base64,iVBORw0KGgo...",
            "expiration_date": "2026-10-16 23:59:59"
        }

    async def mock_transfer(self, value, pix_key, pix_key_type=None, description=""):
        return {
            "id": "transf_live_888",
            "status": "DONE",
            "endToEndIdentifier": "E1960301020261016888999",
            "value": value,
            "netValue": value
        }

    monkeypatch.setattr("app.services.baas_asaas.AsaasClient.create_pix_charge", mock_charge)
    monkeypatch.setattr("app.services.baas_asaas.AsaasClient.send_pix_transfer", mock_transfer)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # PASSO 1: Criação da carteira
        wallet_res = await client.post(
            "/api/v1/wallets",
            json={"user_id": "user_e2e_asaas", "max_per_order": 500.0, "daily_limit": 1000.0}
        )
        assert wallet_res.status_code == 201
        wallet_id = wallet_res.json()["id"]
        assert wallet_res.json()["balance"] == 0.0

        # PASSO 2: Solicitação de Pix Copia-e-Cola de R$ 100,00
        deposit_res = await client.post(
            f"/api/v1/wallets/{wallet_id}/pix-deposit",
            json={"amount": 100.0, "customer_name": "Fundador ACP"}
        )
        assert deposit_res.status_code == 200
        deposit_data = deposit_res.json()
        assert deposit_data["payment_id"] == "pay_live_asaas_999"
        assert deposit_data["value"] == 100.0
        assert "asaaspayload" in deposit_data["copy_paste_payload"]

        # PASSO 3: Asaas dispara Webhook de pagamento recebido (Cash-in)
        webhook_payload = {
            "event": "PAYMENT_RECEIVED",
            "payment": {
                "id": "pay_live_asaas_999",
                "value": 100.0,
                "netValue": 99.01,
                "externalReference": wallet_id,
                "status": "RECEIVED"
            }
        }
        wh_res = await client.post(
            "/api/v1/webhooks/asaas",
            json=webhook_payload,
            headers={"asaas-access-token": "token_wh_val"}
        )
        assert wh_res.status_code == 200
        assert wh_res.json()["status"] == "credited"

        # PASSO 4: Verifica se o saldo foi creditado na carteira
        wallet_check = await client.get(f"/api/v1/wallets/{wallet_id}")
        assert wallet_check.status_code == 200
        assert wallet_check.json()["balance"] == 100.0

        # PASSO 5: Agente executa checkout autônomo (R$ 50,00 + taxa 2% = R$ 51,00)
        checkout_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [
                    {
                        "product_id_or_url": "SKU-PRODUTO-PARCEIRO",
                        "quantity": 1,
                        "unit_price": 50.0,
                        "merchant_domain": "lojaparceira.com.br"
                    }
                ],
                "shipping_profile_id": "sp_deposito_principal"
            }
        )
        assert checkout_res.status_code == 200
        checkout_data = checkout_res.json()
        assert checkout_data["status"] == "completed"
        assert checkout_data["execution_type"] == "autonomous"
        assert checkout_data["total_debited"] == 51.0
        assert checkout_data["receipt"]["amount_transferred"] == 50.0
        assert checkout_data["receipt"]["acp_fee_retained"] == 1.0
        assert checkout_data["receipt"]["pix_end_to_end_id"] == "E1960301020261016888999"

        # PASSO 6: Saldo remanescente exato após débito e liquidação Pix
        wallet_final = await client.get(f"/api/v1/wallets/{wallet_id}")
        assert wallet_final.json()["balance"] == 49.0
