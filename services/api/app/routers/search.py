from fastapi import APIRouter
from app.schemas.search import (
    SearchRequest,
    SearchResponse,
    ProductSearchResult,
    MerchantInfo,
)
from app.services.scrapers.mercadolivre import MercadoLivreScraper
from app.services.classifier import JevClassifier
from app.services.pricing import calculate_effective_price

router = APIRouter(prefix="/api/v1/search", tags=["search"])

scraper = MercadoLivreScraper()
classifier = JevClassifier()


@router.post("", response_model=SearchResponse)
async def search_products(request: SearchRequest):
    raw_listings = await scraper.search(request.query, limit=20)
    results: list[ProductSearchResult] = []

    for item in raw_listings:
        classification = classifier.classify_listing(
            title=item.title,
            price=item.display_price,
            seller_info={"reputation_level": item.seller_reputation, "sales_count": 150},
            target_query=request.query,
        )

        # Filtra acessórios incompatíveis e honeypots
        if not classification.is_valid_product:
            continue
        if "UNREALISTIC_PRICE" in classification.risk_flags:
            continue

        pricing = calculate_effective_price(
            display_price=item.display_price,
            cash_price=item.cash_price if request.prefer_best_cash_price else None,
        )

        # Filtro de teto de preço
        if request.max_unit_price is not None and pricing.best_effective_price > request.max_unit_price:
            continue

        merchant = MerchantInfo(
            domain="mercadolivre.com.br",
            is_verified=classification.trust_score >= 0.85,
            trust_score=classification.trust_score,
        )

        if request.merchant_filter == "verified_only" and not merchant.is_verified:
            continue

        results.append(
            ProductSearchResult(
                product_id=item.product_id,
                title=item.title,
                url=item.url,
                merchant=merchant,
                pricing=pricing,
                stock_available=1,
                execution_type="human_handoff",
            )
        )

    results.sort(key=lambda x: x.pricing.best_effective_price)

    return SearchResponse(
        results=results,
        total_results=len(results),
    )
