from abc import ABC, abstractmethod
from typing import Optional
from app.models.shipping import ShippingProfile


class BaseCheckoutStrategy(ABC):
    """
    Interface base para estratégias de preenchimento e finalização de checkout
    em diferentes plataformas de e-commerce aberto (Nuvemshop, Shopify, WooCommerce, Genérico).
    """

    @abstractmethod
    async def add_to_cart_and_proceed(self, page, quantity: int = 1) -> bool:
        """Localiza botão de comprar/adicionar ao carrinho e navega para a página de checkout."""
        pass

    @abstractmethod
    async def fill_shipping(self, page, profile: ShippingProfile) -> bool:
        """Preenche os dados de entrega (Nome, CPF, Telefone, CEP, Rua, Número)."""
        pass

    @abstractmethod
    async def select_pix_and_submit(self, page) -> Optional[str]:
        """Seleciona a opção Pix, confirma o pedido e extrai o código Pix Copia-e-Cola."""
        pass
