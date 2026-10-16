import logging
from typing import Optional
from app.services.checkout_worker.strategies.base import BaseCheckoutStrategy
from app.services.checkout_worker.pix_extractor import PixExtractor
from app.models.shipping import ShippingProfile

logger = logging.getLogger(__name__)


class GenericGuestCheckoutStrategy(BaseCheckoutStrategy):
    """
    Estratégia universal com heurísticas de formulário para preenchimento de guest checkout
    em lojas abertas brasileiras (identifica campos de Nome, CPF, Telefone, CEP e rádio Pix).
    """

    async def add_to_cart_and_proceed(self, page, quantity: int = 1) -> bool:
        buy_selectors = [
            'button:has-text("Comprar")',
            'button:has-text("Adicionar ao carrinho")',
            'a:has-text("Comprar")',
            'input[value*="Comprar"]',
            '.btn-buy',
            '.add-to-cart',
            '#buy-button'
        ]
        for sel in buy_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                try:
                    target = loc.first if hasattr(loc, "first") else loc
                    await target.click()
                    await page.wait_for_timeout(1000)
                    return True
                except Exception as e:
                    logger.debug(f"Falha ao clicar no seletor de compra {sel}: {e}")
        return False

    async def _fill_field(self, page, selectors: list[str], value: str) -> bool:
        for sel in selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                try:
                    target = loc.first if hasattr(loc, "first") else loc
                    await target.fill(value)
                    return True
                except Exception:
                    pass
        return False

    async def fill_shipping(self, page, profile: ShippingProfile) -> bool:
        # Nome
        await self._fill_field(page, [
            'input[name*="name"]',
            'input[name*="nome"]',
            'input[id*="name"]',
            'input[id*="nome"]'
        ], profile.recipient_name)

        # CPF
        await self._fill_field(page, [
            'input[name*="cpf"]',
            'input[id*="cpf"]',
            'input[name*="document"]'
        ], profile.cpf_cnpj)

        # Telefone
        await self._fill_field(page, [
            'input[type="tel"]',
            'input[name*="phone"]',
            'input[name*="tel"]',
            'input[id*="phone"]'
        ], profile.phone)

        # CEP
        await self._fill_field(page, [
            'input[name*="cep"]',
            'input[id*="cep"]',
            'input[name*="postal"]',
            'input[id*="zipcode"]'
        ], profile.postal_code)

        # Número do imóvel
        await self._fill_field(page, [
            'input[name*="number"]',
            'input[name*="numero"]',
            'input[id*="number"]',
            'input[id*="numero"]'
        ], profile.number)

        # Complemento
        if profile.complement:
            await self._fill_field(page, [
                'input[name*="complement"]',
                'input[id*="complement"]'
            ], profile.complement)

        return True

    async def select_pix_and_submit(self, page) -> Optional[str]:
        # Localiza e seleciona a opção Pix
        pix_selectors = [
            'input[type="radio"][value*="pix"]',
            'input[type="radio"][id*="pix"]',
            'label:has-text("Pix")',
            'div:has-text("Pix"):not(:has(div))',
            '.payment-pix'
        ]
        for sel in pix_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                try:
                    target = loc.first if hasattr(loc, "first") else loc
                    await target.click()
                    await page.wait_for_timeout(500)
                    break
                except Exception:
                    pass

        # Clica no botão de finalizar pedido
        submit_selectors = [
            'button:has-text("Finalizar compra")',
            'button:has-text("Finalizar pedido")',
            'button:has-text("Pagar")',
            'button:has-text("Confirmar")',
            'input[type="submit"]',
            '.btn-checkout'
        ]
        for sel in submit_selectors:
            loc = page.locator(sel)
            if await loc.count() > 0:
                try:
                    target = loc.first if hasattr(loc, "first") else loc
                    await target.click()
                    await page.wait_for_timeout(1500)
                    break
                except Exception:
                    pass

        # Extrai o código Pix Copia-e-Cola do HTML renderizado
        content = await page.content()
        return PixExtractor.extract_payload(content)
