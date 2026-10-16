import uuid
from dataclasses import dataclass
from typing import Optional
from app.schemas.checkout import CheckoutItem
from app.models.shipping import ShippingProfile
from app.services.checkout_worker.orchestrator import PlaywrightCheckoutWorker


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

    def __init__(self, worker: Optional[PlaywrightCheckoutWorker] = None):
        self.worker = worker or PlaywrightCheckoutWorker()

    async def execute_guest_checkout(
        self,
        items: list[CheckoutItem],
        shipping_profile: ShippingProfile,
        use_headless: bool = True
    ) -> GuestCheckoutResult:
        if not items:
            raise ValueError("Pelo menos um item deve ser fornecido para checkout")

        total_price = round(sum(item.quantity * item.unit_price for item in items), 2)
        first_item = items[0]
        primary_domain = first_item.merchant_domain.strip().lower()
        product_url = first_item.product_id_or_url
        quantity = first_item.quantity or 1

        # Se for uma URL web real e headless habilitado, aciona o PlaywrightCheckoutWorker
        if use_headless and (product_url.startswith("http://") or product_url.startswith("https://")):
            worker_result = await self.worker.execute(
                url=product_url,
                quantity=quantity,
                profile=shipping_profile
            )
            if worker_result.status != "SUCCESS" or not worker_result.pix_copia_e_cola:
                err_msg = worker_result.error_message or "Não foi possível capturar o código Pix oficial na loja"
                raise RuntimeError(f"Falha ao realizar checkout autônomo na loja ({primary_domain}): {err_msg}")

            return GuestCheckoutResult(
                order_id=worker_result.order_id or f"ord_pw_{uuid.uuid4().hex[:8]}",
                total_price=total_price,
                pix_copia_e_cola=worker_result.pix_copia_e_cola,
                pix_key=f"pix@{primary_domain}",
                merchant_domain=primary_domain,
                is_simulation=False,
                status="PENDING_PAYMENT",
                recipient_name=shipping_profile.recipient_name if shipping_profile else "Comprador ACP"
            )

        # Fallback / Simulação para testes e ambientes sem URL real de produto
        order_id = f"order_guest_{uuid.uuid4().hex[:8]}"
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
            recipient_name=shipping_profile.recipient_name if shipping_profile else "Comprador ACP"
        )
