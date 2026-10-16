import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from tests.conftest import TestAsyncSessionLocal
from app.models.wallet import Wallet


@pytest.mark.asyncio
async def test_wallet_pix_deposit_generates_copy_paste_payload_in_sandbox():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Cria carteira
        wallet_res = await client.post(
            "/api/v1/wallets",
            json={"user_id": "user_dep_sb", "max_per_order": 500.0, "daily_limit": 1000.0}
        )
        assert wallet_res.status_code == 201
        wallet_id = wallet_res.json()["id"]

        # Solicita Pix Copia-e-Cola de recarga
        dep_res = await client.post(
            f"/api/v1/wallets/{wallet_id}/pix-deposit",
            json={"amount": 50.0}
        )
        assert dep_res.status_code == 200
        data = dep_res.json()
        assert data["payment_id"].startswith("pay_")
        assert data["value"] == 50.0
        assert data["copy_paste_payload"].startswith("00020126")
        assert "qr_code_base64" in data
        assert "expiration_date" in data


@pytest.mark.asyncio
async def test_wallet_pix_deposit_calls_asaas_when_configured(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.ASAAS_API_KEY", "real_asaas_key")

    async def mock_charge(self, value, description, external_reference, customer_name=None, customer_cpf_cnpj=None):
        return {
            "payment_id": "pay_asaas_live_123",
            "value": value,
            "copy_paste_payload": "00020126580014br.gov.bcb.pix0136asaaslivepayload...",
            "encoded_image": "data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...",
            "expiration_date": "2026-10-16 23:59:59"
        }

    monkeypatch.setattr("app.services.baas_asaas.AsaasClient.create_pix_charge", mock_charge)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        wallet_res = await client.post(
            "/api/v1/wallets",
            json={"user_id": "user_dep_asaas", "max_per_order": 500.0, "daily_limit": 1000.0}
        )
        wallet_id = wallet_res.json()["id"]

        dep_res = await client.post(
            f"/api/v1/wallets/{wallet_id}/pix-deposit",
            json={
                "amount": 120.0,
                "customer_name": "Joao Teste",
                "customer_cpf_cnpj": "12345678909"
            }
        )
        assert dep_res.status_code == 200
        data = dep_res.json()
        assert data["payment_id"] == "pay_asaas_live_123"
        assert data["value"] == 120.0
        assert "asaaslivepayload" in data["copy_paste_payload"]


@pytest.mark.asyncio
async def test_wallet_pix_deposit_rejects_nonexistent_wallet():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post(
            "/api/v1/wallets/nonexistent_id_123/pix-deposit",
            json={"amount": 50.0}
        )
        assert res.status_code == 404
