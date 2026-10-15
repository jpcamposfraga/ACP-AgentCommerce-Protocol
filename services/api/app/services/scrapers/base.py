from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Literal, Optional


@dataclass
class RawListing:
    product_id: str
    title: str
    url: str
    display_price: float
    cash_price: Optional[float] = None
    seller_name: str = ""
    seller_reputation: str = "standard"
    image_url: Optional[str] = None


class BaseScraper(ABC):
    """
    Interface base padronizada para todos os conectores e scrapers de e-commerce do ACP.
    Permite busca agnóstica de catálogo com suporte a roteamento regional e moedas.
    """

    domain: str
    region: Literal["BR", "US", "GLOBAL"]
    currency: Literal["BRL", "USD", "EUR"]
    execution_type: Literal["autonomous", "human_handoff"]
    is_verified: bool = True

    @abstractmethod
    async def search(self, query: str, limit: int = 10) -> list[RawListing]:
        """
        Executa a busca de produtos e retorna listagens normalizadas em RawListing.
        """
        pass
