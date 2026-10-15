import pytest
from pydantic import ValidationError
from app.schemas.checkout import CheckoutItem, CheckoutRequest, CheckoutResponse, PaymentReceipt
from app.schemas.webhook import BaaSPixWebhook


def test_checkout_item_validation():
    # Validação correta
    item = CheckoutItem(
        product_id_or_url="MLB-12345",
        quantity=2,
        unit_price=250.0,
        merchant_domain="lojadoteste.com.br"
    )
    assert item.quantity == 2
    assert item.unit_price == 250.0

    # Quantidade inválida <= 0
    with pytest.raises(ValidationError):
        CheckoutItem(
            product_id_or_url="MLB-12345",
            quantity=0,
            unit_price=250.0,
            merchant_domain="lojadoteste.com.br"
        )

    # Preço inválido <= 0
    with pytest.raises(ValidationError):
        CheckoutItem(
            product_id_or_url="MLB-12345",
            quantity=1,
            unit_price=-10.0,
            merchant_domain="lojadoteste.com.br"
        )


def test_checkout_request_validation():
    item = CheckoutItem(
        product_id_or_url="MLB-12345",
        quantity=1,
        unit_price=100.0,
        merchant_domain="lojadoteste.com.br"
    )
    req = CheckoutRequest(
        wallet_id="wallet_abc123",
        order_items=[item],
        shipping_profile_id="sp_galpao_sp"
    )
    assert req.wallet_id == "wallet_abc123"
    assert len(req.order_items) == 1
    assert req.shipping_profile_id == "sp_galpao_sp"

    # Sem itens
    with pytest.raises(ValidationError):
        CheckoutRequest(
            wallet_id="wallet_abc123",
            order_items=[],
            shipping_profile_id="sp_galpao_sp"
        )


def test_checkout_response_and_receipt_validation():
    receipt = PaymentReceipt(
        pix_end_to_end_id="E12345678202610151200",
        paid_at="2026-10-15T12:00:00Z",
        amount_transferred=500.0,
        acp_fee_retained=10.0
    )
    res = CheckoutResponse(
        order_id="ord_999",
        status="completed",
        execution_type="autonomous",
        total_debited=510.0,
        receipt=receipt
    )
    assert res.status == "completed"
    assert res.total_debited == 510.0
    assert res.receipt.amount_transferred == 500.0


def test_baas_pix_webhook_validation():
    payload = BaaSPixWebhook(
        event="pix_received",
        payment_id="pay_998877",
        wallet_id="wallet_abc123",
        amount=1000.0,
        end_to_end_id="E99887766202610151200"
    )
    assert payload.amount == 1000.0
    assert payload.event == "pix_received"

    # Valor negativo deve falhar
    with pytest.raises(ValidationError):
        BaaSPixWebhook(
            event="pix_received",
            payment_id="pay_998877",
            wallet_id="wallet_abc123",
            amount=-50.0,
            end_to_end_id="E99887766202610151200"
        )
