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
