import logging
from typing import Optional
from app.services.checkout_worker.strategies.generic import GenericGuestCheckoutStrategy

logger = logging.getLogger(__name__)


class NuvemshopCheckoutStrategy(GenericGuestCheckoutStrategy):
    """
    Estratégia especializada para lojas Nuvemshop (Tiendanube),
    adaptada para a estrutura de checkout padronizada da plataforma.
    """

    async def add_to_cart_and_proceed(self, page, quantity: int = 1) -> bool:
        nuvem_selectors = [
            'input[name="add-to-cart"]',
            'button.js-addtocart',
            'input.js-addtocart',
            '.js-prod-submit-form',
            'button:has-text("Comprar")'
        ]
        for sel in nuvem_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                try:
                    await loc.first.click()
                    await page.wait_for_timeout(1000)
                    return True
                except Exception:
                    pass
        return await super().add_to_cart_and_proceed(page, quantity)
