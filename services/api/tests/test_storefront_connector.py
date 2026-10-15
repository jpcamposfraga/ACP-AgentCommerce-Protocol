import pytest
from app.schemas.checkout import CheckoutItem
from app.services.connectors.storefront import StorefrontPartnerClient, PartnerOrderResult


@pytest.mark.asyncio
async def test_storefront_partner_create_order_success():
    client = StorefrontPartnerClient()
    items = [
        CheckoutItem(
            product_id_or_url="PARTNER-SKU-100",
            quantity=2,
            unit_price=250.0,
            merchant_domain="loja-parceira.com.br"
        ),
        CheckoutItem(
            product_id_or_url="PARTNER-SKU-200",
            quantity=1,
            unit_price=100.0,
            merchant_domain="loja-parceira.com.br"
        )
    ]

    order_result = await client.create_order(
        items=items,
        shipping_profile_id="sp_galpao_sp"
    )

    assert isinstance(order_result, PartnerOrderResult)
    assert order_result.order_id.startswith("order_partner_")
    assert order_result.total_price == 600.0  # (2 * 250) + (1 * 100)
    assert order_result.status == "PENDING_PAYMENT"
    assert "00020126" in order_result.pix_copia_e_cola  # Padrão EMV Pix
    assert "pix@loja-parceira.com.br" in order_result.pix_key


@pytest.mark.asyncio
async def test_storefront_partner_empty_items_raises_error():
    client = StorefrontPartnerClient()
    with pytest.raises(ValueError, match="Pelo menos um item"):
        await client.create_order(items=[], shipping_profile_id="default")
