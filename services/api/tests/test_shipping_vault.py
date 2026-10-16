import pytest
from app.services.viacep import ViaCepClient
from app.schemas.shipping import ShippingProfileCreate, ShippingProfileResponse


@pytest.mark.asyncio
async def test_viacep_lookup_valid_cep(monkeypatch):
    async def mock_get(self, url, **kwargs):
        class MockResp:
            status_code = 200

            def json(self):
                return {
                    "cep": "01310-100",
                    "logradouro": "Avenida Paulista",
                    "bairro": "Bela Vista",
                    "localidade": "São Paulo",
                    "uf": "SP",
                }

        return MockResp()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    client = ViaCepClient()
    info = await client.lookup("01310-100")
    assert info["street"] == "Avenida Paulista"
    assert info["city"] == "São Paulo"
    assert info["state"] == "SP"


def test_shipping_profile_schema_validation():
    profile = ShippingProfileCreate(
        wallet_id="w_123",
        recipient_name="João Silva",
        cpf_cnpj="12345678909",
        phone="11999998888",
        postal_code="01310-100",
        street="Av. Paulista",
        number="1000",
        neighborhood="Bela Vista",
        city="São Paulo",
        state="SP"
    )
    assert profile.recipient_name == "João Silva"
    assert profile.postal_code == "01310-100"


@pytest.mark.asyncio
async def test_shipping_profiles_crud_api(monkeypatch):
    from httpx import AsyncClient, ASGITransport
    from app.main import app

    async def mock_lookup(self, cep):
        return {
            "postal_code": "01310-100",
            "street": "Avenida Paulista",
            "neighborhood": "Bela Vista",
            "city": "São Paulo",
            "state": "SP",
            "complement": ""
        }

    monkeypatch.setattr("app.services.viacep.ViaCepClient.lookup", mock_lookup)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Cria carteira
        w_res = await client.post("/api/v1/wallets", json={"user_id": "ship_user", "max_per_order": 100.0, "daily_limit": 200.0})
        assert w_res.status_code == 201
        wallet_id = w_res.json()["id"]

        # 2. Cria endereço com auto-completar do ViaCEP
        create_res = await client.post(
            "/api/v1/shipping-profiles",
            json={
                "wallet_id": wallet_id,
                "recipient_name": "Ana Maria",
                "cpf_cnpj": "11122233344",
                "phone": "11988887777",
                "postal_code": "01310-100",
                "number": "500",
                "complement": "Apto 12",
                "is_default": True
            }
        )
        assert create_res.status_code == 201
        profile = create_res.json()
        assert profile["recipient_name"] == "Ana Maria"
        assert profile["street"] == "Avenida Paulista"
        assert profile["city"] == "São Paulo"
        assert profile["state"] == "SP"
        assert profile["is_default"] is True
        profile_id = profile["id"]

        # 3. Lista endereços da carteira
        list_res = await client.get(f"/api/v1/shipping-profiles/wallet/{wallet_id}")
        assert list_res.status_code == 200
        profiles = list_res.json()
        assert len(profiles) >= 1
        assert profiles[0]["id"] == profile_id

        # 4. Busca perfil individual
        get_res = await client.get(f"/api/v1/shipping-profiles/{profile_id}")
        assert get_res.status_code == 200
        assert get_res.json()["id"] == profile_id
