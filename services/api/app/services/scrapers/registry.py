from typing import Optional
from app.services.scrapers.base import BaseScraper
from app.services.scrapers.mercadolivre import MercadoLivreScraper
from app.services.scrapers.mock_scrapers import create_top_10_scrapers


class ScraperRegistry:
    """
    Registro centralizado de conectores de e-commerce e marketplaces.
    Permite agregação concorrente com filtragem por região (BR, US, GLOBAL)
    e por whitelist explícita de domínios configurada pelo usuário.
    """

    def __init__(self):
        self._scrapers: dict[str, BaseScraper] = {}
        # Registra conector primário Mercado Livre
        meli = MercadoLivreScraper()
        self.register(meli)
        # Registra os demais conectores do Big 10
        for scraper in create_top_10_scrapers():
            self.register(scraper)

    def register(self, scraper: BaseScraper) -> None:
        self._scrapers[scraper.domain] = scraper

    def get_all_scrapers(self) -> list[BaseScraper]:
        return list(self._scrapers.values())

    def get_scrapers(
        self,
        region: str = "BR",
        currency: str | None = None,
        allowed_domains: Optional[list[str]] = None
    ) -> list[BaseScraper]:
        clean_region = region.upper().strip()
        filtered: list[BaseScraper] = []

        for s in self._scrapers.values():
            # Filtro por moeda (se informada)
            if currency is not None and s.currency != currency.upper().strip():
                continue

            # Filtro por região: aceita se coincidir ou se for GLOBAL
            if s.region != clean_region and s.region != "GLOBAL":
                continue

            # Filtro por whitelist do usuário (se fornecida)
            if allowed_domains is not None:
                domain_clean = s.domain.lower()
                normalized_allowed = [d.lower().strip() for d in allowed_domains]
                if not any(domain_clean == a or domain_clean.endswith("." + a) for a in normalized_allowed):
                    continue
            else:
                # Sem whitelist explícita: para região BR, o conector primário padrão de produção é o Mercado Livre
                if clean_region == "BR" and s.domain != "mercadolivre.com.br":
                    continue

            filtered.append(s)

        return filtered
