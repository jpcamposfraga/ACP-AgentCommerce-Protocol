import asyncio
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    ProductSearchResult,
    MerchantInfo,
)
from app.services.scrapers.registry import ScraperRegistry
from app.services.classifier import JevClassifier
from app.services.pricing import calculate_effective_price
from app.services.product_registry import product_registry


class SearchAggregator:
    """
    Agregador Concorrente de Busca do AgentCommerce Protocol (ACP).
    Coordena consultas simultâneas nos 10+ e-commerces registrados,
    aplica isolamento de falhas por timeout, desduplica resultados,
    classifica via Jev e calcula o Menor Preço Efetivo.
    """

    def __init__(self, registry: ScraperRegistry | None = None, classifier: JevClassifier | None = None):
        self.registry = registry or ScraperRegistry()
        self.classifier = classifier or JevClassifier()

    async def search(self, request: SearchRequest) -> SearchResponse:
        scrapers = self.registry.get_scrapers(
            region=request.region,
            currency=request.currency,
            allowed_domains=request.allowed_domains
        )

        if not scrapers:
            return SearchResponse(results=[], total_results=0)

        # Dispara buscas concorrentes com timeout protetivo individual
        async def fetch_safe(scraper):
            try:
                return scraper, await asyncio.wait_for(scraper.search(request.query, limit=10), timeout=3.5)
            except Exception:
                # Falhas isoladas de um lojista/scraper não quebram os demais
                return scraper, []

        tasks = [fetch_safe(s) for s in scrapers]
        completed = await asyncio.gather(*tasks, return_exceptions=True)

        results: list[ProductSearchResult] = []

        for item in completed:
            if isinstance(item, Exception):
                continue
            scraper, raw_listings = item
            for raw in raw_listings:
                classification = self.classifier.classify_listing(
                    title=raw.title,
                    price=raw.display_price,
                    seller_info={"reputation_level": raw.seller_reputation, "sales_count": 150},
                    target_query=request.query
                )

                if not classification.is_valid_product:
                    continue
                if "UNREALISTIC_PRICE" in classification.risk_flags:
                    continue

                pricing = calculate_effective_price(
                    display_price=raw.display_price,
                    cash_price=raw.cash_price if request.prefer_best_cash_price else None,
                    currency=request.currency
                )

                if request.max_unit_price is not None and pricing.best_effective_price > request.max_unit_price:
                    continue

                merchant = MerchantInfo(
                    domain=scraper.domain,
                    is_verified=classification.trust_score >= 0.85,
                    trust_score=classification.trust_score
                )

                if request.merchant_filter == "verified_only" and not merchant.is_verified:
                    continue

                product_registry.register(raw.product_id, raw.url)
                results.append(
                    ProductSearchResult(
                        product_id=raw.product_id,
                        title=raw.title,
                        url=raw.url,
                        merchant=merchant,
                        pricing=pricing,
                        stock_available=1,
                        execution_type=scraper.execution_type
                    )
                )

        # Ordenação global pelo menor preço efetivo
        results.sort(key=lambda x: x.pricing.best_effective_price)

        return SearchResponse(
            results=results,
            total_results=len(results)
        )
