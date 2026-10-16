import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.qrcode_service import render_terminal_qr, render_png_qr


def test_render_terminal_qr_produces_utf8_blocks():
    payload = "00020126580014br.gov.bcb.pix0136test"
    qr_term = render_terminal_qr(payload)
    assert isinstance(qr_term, str)
    assert len(qr_term) > 50


def test_render_png_qr_produces_valid_png_bytes():
    payload = "00020126580014br.gov.bcb.pix0136test"
    png_bytes = render_png_qr(payload)
    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")


@pytest.mark.asyncio
async def test_wallet_deposit_returns_terminal_and_web_qr_url():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "qr_user", "max_per_order": 50.0, "daily_limit": 100.0})
        assert w_res.status_code == 201
        wallet_id = w_res.json()["id"]

        dep_res = await client.post(f"/api/v1/wallets/{wallet_id}/pix-deposit", json={"amount": 10.0})
        assert dep_res.status_code == 200
        data = dep_res.json()
        assert "qr_code_terminal" in data and len(data["qr_code_terminal"]) > 20
        assert "qr_code_url" in data and f"/api/v1/wallets/{wallet_id}/pix-deposit/" in data["qr_code_url"]

        # Test image endpoint
        img_res = await client.get(data["qr_code_url"])
        assert img_res.status_code == 200
        assert img_res.headers["content-type"] == "image/png"
        assert img_res.content.startswith(b"\x89PNG\r\n\x1a\n")
