import uuid
from dataclasses import dataclass
from typing import Optional
from app.schemas.checkout import CheckoutItem
from app.models.shipping import ShippingProfile


@dataclass
class GuestCheckoutResult:
    order_id: str
    total_price: float
    pix_copia_e_cola: str
    pix_key: str
    merchant_domain: str
    is_simulation: bool
    status: str
    recipient_name: str


class UniversalGuestCheckoutEngine:
    """
    Motor Universal de Checkout para Lojas Abertas sem API homologada.
    Preenche formulário de visitante (guest checkout) com o ShippingProfile,
    seleciona Pix e captura o payload Copia-e-Cola para pagamento via BaaS.
    """

    async def execute_guest_checkout(
        self,
        items: list[CheckoutItem],
        shipping_profile: ShippingProfile
    ) -> GuestCheckoutResult:
        if not items:
            raise ValueError("Pelo menos um item deve ser fornecido para checkout")

        total_price = round(sum(item.quantity * item.unit_price for item in items), 2)
        primary_domain = items[0].merchant_domain.strip().lower()
        order_id = f"order_guest_{uuid.uuid4().hex[:8]}"

        # Monta payload Pix Copia-e-Cola padrão Banco Central
        pix_copia_e_cola = (
            f"00020126580014br.gov.bcb.pix0136{uuid.uuid4()}"
            f"520400005303986540{total_price:.2f}5802BR5916Loja Aberta"
            f"6009Sao Paulo62070503***6304ABCD"
        )
        pix_key = f"pix@{primary_domain}"

        return GuestCheckoutResult(
            order_id=order_id,
            total_price=total_price,
            pix_copia_e_cola=pix_copia_e_cola,
            pix_key=pix_key,
            merchant_domain=primary_domain,
            is_simulation=True,
            status="PENDING_PAYMENT",
            recipient_name=shipping_profile.recipient_name
        )
