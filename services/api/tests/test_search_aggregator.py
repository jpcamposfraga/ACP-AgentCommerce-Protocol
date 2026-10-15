import pytest

@pytest.mark.asyncio
async def test_search_aggregator_queries_multiple_sources_concurrently():
    from app.services.aggregator import SearchAggregator
    from app.schemas.search import SearchRequest
    aggregator = SearchAggregator()
    req = SearchRequest(
        query="caderno para desenho",
        region="BR",
        allowed_domains=["mercadolivre.com.br", "kalunga.com.br"],
        max_unit_price=50.0
    )
    response = await aggregator.search(req)
    assert response.total_results > 0
    domains_present = {item.merchant.domain for item in response.results}
    assert domains_present.issubset({"mercadolivre.com.br", "kalunga.com.br"})
    # Resultados devem estar ordenados por menor preço efetivo
    prices = [item.pricing.best_effective_price for item in response.results]
    assert prices == sorted(prices)

@pytest.mark.asyncio
async def test_search_aggregator_handles_us_region_without_brazilian_stores():
    from app.services.aggregator import SearchAggregator
    from app.schemas.search import SearchRequest
    aggregator = SearchAggregator()
    req = SearchRequest(
        query="iPhone 15",
        region="US",
        currency="USD"
    )
    response = await aggregator.search(req)
    assert response.total_results > 0
    domains = {item.merchant.domain for item in response.results}
    assert "mercadolivre.com.br" not in domains
    assert any("amazon.com" in d or "ebay.com" in d or "walmart.com" in d for d in domains)
    # Todos os itens retornados devem estar em USD
    assert all(item.pricing.currency == "USD" for item in response.results)
