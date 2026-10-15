import re
from typing import Literal
from app.services.scrapers.base import BaseScraper, RawListing


class GenericMockScraper(BaseScraper):
    """
    Conector genérico de marketplace / e-commerce com catálogo estruturado.
    Usado para agregar plataformas dos Big 10 (Amazon BR/US, Magalu, KaBuM, Shopee, Kalunga, eBay, Walmart, AliExpress).
    """

    def __init__(
        self,
        domain: str,
        region: Literal["BR", "US", "GLOBAL"],
        currency: Literal["BRL", "USD", "EUR"],
        execution_type: Literal["autonomous", "human_handoff"] = "human_handoff",
        price_multiplier: float = 1.0,
        pix_discount_pct: float = 0.0
    ):
        self.domain = domain
        self.region = region
        self.currency = currency
        self.execution_type = execution_type
        self.price_multiplier = price_multiplier
        self.pix_discount_pct = pix_discount_pct

    async def search(self, query: str, limit: int = 10) -> list[RawListing]:
        lower_q = query.lower()
        listings: list[RawListing] = []

        # Catálogo adaptativo baseado na consulta
        if "caderno" in lower_q or "sketchbook" in lower_q or "desenho" in lower_q:
            base_items = [
                ("Caderno Sketchbook Desenho Artístico A4 200g", 34.90),
                ("Bloco Canson Papel Desenho 180g A4 20 Fls", 28.50),
                ("Caderno Desenho Capa Dura Spiral 80 Fls", 22.90),
            ]
        elif "iphone" in lower_q or "celular" in lower_q or "smartphone" in lower_q:
            base_price = 4800.0 if self.currency == "BRL" else 899.0
            base_items = [
                (f"Apple iPhone 15 128GB {self.domain.split('.')[0].capitalize()}", base_price),
                (f"Apple iPhone 15 256GB {self.domain.split('.')[0].capitalize()}", base_price * 1.15),
            ]
        else:
            base_items = [
                (f"{query.title()} Oferta Especial", 99.00 if self.currency == "BRL" else 29.00)
            ]

        for i, (name, base_price) in enumerate(base_items[:limit], start=1):
            price = round(base_price * self.price_multiplier, 2)
            cash_price = round(price * (1.0 - self.pix_discount_pct), 2) if self.pix_discount_pct > 0 else None
            clean_domain_tag = self.domain.split(".")[0].upper()

            listings.append(
                RawListing(
                    product_id=f"{clean_domain_tag}-{100 + i}",
                    title=f"{name} ({clean_domain_tag})",
                    url=f"https://{self.domain}/item/{100 + i}",
                    display_price=price,
                    cash_price=cash_price,
                    seller_name=f"{clean_domain_tag} Store",
                    seller_reputation="official_store" if i == 1 else "platinum",
                    image_url=f"https://img.{self.domain}/p{100 + i}.jpg"
                )
            )

        return listings


def create_top_10_scrapers() -> list[BaseScraper]:
    """
    Instancia os conectores padronizados dos 9 e-commerces que complementam o Mercado Livre.
    """
    return [
        GenericMockScraper("amazon.com.br", "BR", "BRL", "human_handoff", price_multiplier=0.98, pix_discount_pct=0.05),
        GenericMockScraper("magazineluiza.com.br", "BR", "BRL", "human_handoff", price_multiplier=1.02, pix_discount_pct=0.08),
        GenericMockScraper("kabum.com.br", "BR", "BRL", "autonomous", price_multiplier=0.95, pix_discount_pct=0.10),
        GenericMockScraper("shopee.com.br", "BR", "BRL", "human_handoff", price_multiplier=0.92, pix_discount_pct=0.03),
        GenericMockScraper("kalunga.com.br", "BR", "BRL", "autonomous", price_multiplier=0.96, pix_discount_pct=0.05),
        GenericMockScraper("amazon.com", "US", "USD", "human_handoff", price_multiplier=1.0),
        GenericMockScraper("ebay.com", "US", "USD", "human_handoff", price_multiplier=0.94),
        GenericMockScraper("walmart.com", "US", "USD", "human_handoff", price_multiplier=0.97),
        GenericMockScraper("aliexpress.com", "GLOBAL", "USD", "human_handoff", price_multiplier=0.85),
    ]
