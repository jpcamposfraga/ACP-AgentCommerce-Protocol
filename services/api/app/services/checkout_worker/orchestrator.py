import os
import uuid
import logging
from dataclasses import dataclass
from typing import Optional
from urllib.parse import urlparse
from app.services.checkout_worker.browser_manager import BrowserManager
from app.services.checkout_worker.strategies.base import BaseCheckoutStrategy
from app.services.checkout_worker.strategies.generic import GenericGuestCheckoutStrategy
from app.services.checkout_worker.strategies.nuvemshop import NuvemshopCheckoutStrategy
from app.models.shipping import ShippingProfile

logger = logging.getLogger(__name__)


@dataclass
class CheckoutWorkerResult:
    status: str  # "SUCCESS" | "FAILED"
    pix_copia_e_cola: Optional[str] = None
    order_id: Optional[str] = None
    error_message: Optional[str] = None
    screenshot_path: Optional[str] = None


class PlaywrightCheckoutWorker:
    """
    Orquestrador do navegador autônomo para execução de guest checkout em lojas abertas.
    Navega até o produto, preenche o endereço e dados fiscais do ShippingProfile,
    seleciona Pix e extrai o código real de pagamento do gateway da loja.
    """

    def __init__(self, browser_manager: Optional[BrowserManager] = None):
        self.browser_manager = browser_manager or BrowserManager()
        self.failures_dir = os.path.join(os.getcwd(), "scratch", "checkout_failures")

    def get_strategy(self, domain: str) -> BaseCheckoutStrategy:
        domain_lower = domain.lower()
        if "nuvemshop" in domain_lower or "tiendanube" in domain_lower:
            return NuvemshopCheckoutStrategy()
        return GenericGuestCheckoutStrategy()

    async def execute(
        self,
        url: str,
        quantity: int,
        profile: ShippingProfile
    ) -> CheckoutWorkerResult:
        domain = urlparse(url).netloc or "unknown"
        order_ref = f"ord_pw_{uuid.uuid4().hex[:8]}"
        strategy = self.get_strategy(domain)

        context = await self.browser_manager.create_context()
        page = await context.new_page()

        try:
            logger.info(f"[PlaywrightWorker] Iniciando navegação para {url}")
            await page.goto(url, wait_until="domcontentloaded")

            # 1. Adicionar ao carrinho e prosseguir
            added = await strategy.add_to_cart_and_proceed(page, quantity)
            if not added:
                logger.info("[PlaywrightWorker] Seletor direto de compra não encontrado, continuando na página atual")

            # 2. Preencher dados de entrega (ShippingProfile)
            await strategy.fill_shipping(page, profile)

            # 3. Selecionar Pix e submeter
            pix_payload = await strategy.select_pix_and_submit(page)

            if not pix_payload:
                raise ValueError("Não foi possível capturar o código Pix oficial na página de checkout da loja")

            return CheckoutWorkerResult(
                status="SUCCESS",
                pix_copia_e_cola=pix_payload,
                order_id=order_ref
            )

        except Exception as e:
            logger.error(f"[PlaywrightWorker] Falha no checkout em {domain}: {e}")
            os.makedirs(self.failures_dir, exist_ok=True)
            screenshot_path = os.path.join(self.failures_dir, f"failure_{domain}_{uuid.uuid4().hex[:6]}.png")
            try:
                await page.screenshot(path=screenshot_path)
            except Exception as ss_err:
                logger.warning(f"Não foi possível salvar screenshot de falha: {ss_err}")

            return CheckoutWorkerResult(
                status="FAILED",
                error_message=str(e),
                screenshot_path=screenshot_path
            )

        finally:
            try:
                await page.close()
                await context.close()
            except Exception:
                pass
