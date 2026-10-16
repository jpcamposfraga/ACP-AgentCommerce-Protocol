import pytest
import httpx
from app.services.baas_asaas import AsaasClient


def test_detect_pix_key_type():
    client = AsaasClient(api_key="fake")
    assert client.detect_pix_key_type("user@test.com") == "EMAIL"
    assert client.detect_pix_key_type("12345678909") == "CPF"
    assert client.detect_pix_key_type("123.456.789-09") == "CPF"
    assert client.detect_pix_key_type("12345678000199") == "CNPJ"
    assert client.detect_pix_key_type("12.345.678/0001-99") == "CNPJ"
    assert client.detect_pix_key_type("+5511999998888") == "PHONE"
    assert client.detect_pix_key_type("11999998888") == "PHONE"
    assert client.detect_pix_key_type("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d") == "EVP"


@pytest.mark.asyncio
async def test_send_pix_transfer_success():
    captured_requests = []

    def mock_handler(request: httpx.Request):
        captured_requests.append(request)
        if request.url.path in ("/v3/transfers", "/transfers"):
            return httpx.Response(
                200,
                json={
                    "id": "transf_123",
                    "status": "DONE",
                    "endToEndIdentifier": "E1960301020261016123456",
                    "value": 29.90,
                    "netValue": 29.90
                }
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    client = AsaasClient(api_key="sec_token_test", base_url="https://api.asaas.com/v3", transport=transport)

    res = await client.send_pix_transfer(value=29.90, pix_key="loja@teste.com", description="ACP Test")
    assert res["status"] == "DONE"
    assert res["endToEndIdentifier"] == "E1960301020261016123456"

    assert len(captured_requests) == 1
    req = captured_requests[0]
    assert req.headers.get("access_token") == "sec_token_test"
    assert b"\"pixAddressKey\": \"loja@teste.com\"" in req.content or b"\"pixAddressKey\":\"loja@teste.com\"" in req.content
    assert b"\"pixAddressKeyType\": \"EMAIL\"" in req.content or b"\"pixAddressKeyType\":\"EMAIL\"" in req.content


@pytest.mark.asyncio
async def test_create_pix_charge_and_get_qr_code():
    def mock_handler(request: httpx.Request):
        path = request.url.path
        if "customers" in path and request.method == "POST":
            return httpx.Response(200, json={"id": "cus_12345"})
        elif "payments" in path and "pixQrCode" in path:
            return httpx.Response(
                200,
                json={
                    "encodedImage": "data:image/png;base64,iVBORw0KGgo...",
                    "payload": "00020126580014br.gov.bcb.pix0136abc...",
                    "expirationDate": "2026-10-16 23:59:59"
                }
            )
        elif "payments" in path and request.method == "POST":
            return httpx.Response(
                200,
                json={
                    "id": "pay_998877",
                    "value": 100.0,
                    "billingType": "PIX",
                    "status": "PENDING"
                }
            )
        return httpx.Response(404)

    transport = httpx.MockTransport(mock_handler)
    client = AsaasClient(api_key="sec_token_test", base_url="https://api.asaas.com/v3", transport=transport)

    charge = await client.create_pix_charge(
        value=100.0,
        description="Recarga ACP #wallet_1",
        external_reference="wallet_1",
        customer_name="Cliente Teste",
        customer_cpf_cnpj="12345678909"
    )
    assert charge["payment_id"] == "pay_998877"
    assert charge["copy_paste_payload"].startswith("00020126")
    assert "encoded_image" in charge


@pytest.mark.asyncio
async def test_send_pix_transfer_handles_error():
    def mock_handler(request: httpx.Request):
        return httpx.Response(
            400,
            json={"errors": [{"description": "Saldo insuficiente em conta."}]}
        )

    transport = httpx.MockTransport(mock_handler)
    client = AsaasClient(api_key="sec_token_test", base_url="https://api.asaas.com/v3", transport=transport)

    with pytest.raises(ValueError, match="Saldo insuficiente"):
        await client.send_pix_transfer(value=5000.0, pix_key="chave@teste.com")
