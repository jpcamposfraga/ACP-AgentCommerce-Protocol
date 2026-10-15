# Semana 2: Motor de Busca, Parser Rápido com Jev & Pricing Engine - Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o motor de busca e catálogo do ACP consumindo listagens públicas do Mercado Livre via `curl_cffi` e `selectolax`, classificação de ofertas e reputação via modelo Jev (TypeSafe AI), normalização do Menor Preço Efetivo (Pix com desconto à vista + taxa do ACP) e exposição dos endpoints `POST /api/v1/search` e `GET /api/v1/merchant/status`.

**Architecture:** Módulo assíncrono modular no FastAPI: cliente HTTP com impersonation de browser TLS (`curl_cffi`), parser C-level de alta performance (`selectolax.lexbor`), classificador de ofertas estruturado (`JevClassifier`), motor de cálculo financeiro (`pricing_engine`) e routers REST padronizados para o servidor MCP.

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, `curl_cffi`, `selectolax`, Pytest, Pytest-Asyncio.

**Spec:** [docs/ideas/agent-commerce-protocol.md](file:///C:/Users/elast/ACP-MCP/docs/ideas/agent-commerce-protocol.md) e [docs/plans/mvp-4-weeks-implementation-plan.md](file:///C:/Users/elast/ACP-MCP/docs/plans/mvp-4-weeks-implementation-plan.md)

---

## Global Constraints
- Toda adição de código deve seguir estritamente o ciclo TDD (Red-Green-Refactor): **teste falha primeiro, código mínimo para passar, refatoração limpa**.
- Código deve seguir os princípios do Ponytail: enxuto, sem camadas desnecessárias, focado exclusivamente no que a especificação exige.
- Sem consumo de tokens de LLMs caros e lentos durante a extração e parsing: decisões estruturadas devem operar em <200ms.
- Testes automatizados não devem depender de chamadas de rede externas instáveis: usar mocks determinísticos e fixtures HTML para garantir suite rápida e confiável em CI.

## Review Focus
1. **Página sem desconto Pix explícito:** Tratar produtos onde o preço à vista é igual ao parcelado sem gerar quebras de tipo ou divisão por zero.
2. **Variações de layout HTML no Mercado Livre:** Parser deve extrair campos com fallbacks resilientes para evitar `AttributeError` em nós ausentes.
3. **Validação de teto de preço (`max_unit_price`):** O filtro deve considerar o `best_effective_price` já com a taxa do ACP calculada.
4. **Formatação de Moeda e Arredondamento:** Valores financeiros em `float` devem ser arredondados com `round(val, 2)` para evitar dízimas periódicas de precisão binária.
5. **Timeout e Tratamento de Bloqueio:** Resposta elegante com código HTTP 504/502 caso o e-commerce externo demore mais de 5 segundos.

---

### Task 1: Dependências & Schemas de Busca e Lojista

**Files:**
- Modify: `services/api/pyproject.toml`
- Create: `services/api/app/schemas/search.py`
- Create: `services/api/app/schemas/merchant.py`
- Test: `services/api/tests/test_search_schemas.py`

**Interfaces:**
- Produces: `SearchRequest`, `ProductPricing`, `MerchantInfo`, `ProductSearchResult`, `SearchResponse`, `MerchantStatusResponse`.

- [ ] **Step 1: Write failing test for schemas**
```python
def test_search_request_defaults_and_validation():
    from app.schemas.search import SearchRequest
    req = SearchRequest(query="iPhone 15")
    assert req.min_quantity == 1
    assert req.prefer_best_cash_price is True
    assert req.merchant_filter == "all"
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_search_schemas.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.schemas.search'`

- [ ] **Step 3: Add `curl-cffi` and `selectolax` to pyproject.toml and implement schemas**
Implement `services/api/app/schemas/search.py` and `services/api/app/schemas/merchant.py` matching the MCP Tool contracts in `agent-commerce-protocol.md`.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_search_schemas.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/pyproject.toml services/api/app/schemas/ services/api/tests/test_search_schemas.py
git commit -m "feat(api): add curl_cffi, selectolax and search/merchant pydantic schemas"
```

---

### Task 2: Motor de Cálculo de Menor Preço Efetivo (Pricing Engine)

**Files:**
- Create: `services/api/app/services/pricing.py`
- Test: `services/api/tests/test_pricing_engine.py`

**Interfaces:**
- Consumes: `ACP_PLATFORM_FEE_PCT` de `app.core.config.settings`
- Produces: `calculate_effective_price(display_price: float, cash_price: float | None = None, fee_pct: float = 0.02) -> ProductPricing`

- [ ] **Step 1: Write failing tests for pricing engine**
```python
def test_pricing_engine_with_pix_discount():
    # R$ 5000 parcelado, R$ 4500 no Pix (10% off), taxa ACP 2% (R$ 90,00)
    pricing = calculate_effective_price(display_price=5000.0, cash_price=4500.0, fee_pct=0.02)
    assert pricing.display_price == 5000.0
    assert pricing.best_effective_price == 4590.0
    assert pricing.best_payment_method == "pix"
    assert pricing.cash_discount_pct == 10.0
    assert pricing.fee_acp_estimated == 90.0
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_pricing_engine.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.pricing'`

- [ ] **Step 3: Implement `calculate_effective_price` in `app/services/pricing.py`**
Implement function with clean rounding, handling cases where `cash_price is None` or `cash_price >= display_price`.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_pricing_engine.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/pricing.py services/api/tests/test_pricing_engine.py
git commit -m "feat(api): implement best effective pricing engine with cash discount calculation"
```

---

### Task 3: Camada de Classificação Rápida & Validação de Ofertas (Jev Engine)

**Files:**
- Create: `services/api/app/services/classifier.py`
- Test: `services/api/tests/test_classifier.py`

**Interfaces:**
- Produces: `JevClassifier.classify_listing(title: str, price: float, seller_info: dict) -> ClassificationResult`
- Computes: `is_valid_product: bool`, `trust_score: float`, `confidence: float`.

- [ ] **Step 1: Write failing test for classifier**
```python
def test_classifier_identifies_valid_product_and_seller_score():
    classifier = JevClassifier()
    result = classifier.classify_listing(
        title="Apple iPhone 15 128GB Preto Novo Lacrado",
        price=4800.0,
        seller_info={"reputation_level": "gold", "sales_count": 500}
    )
    assert result.is_valid_product is True
    assert result.trust_score >= 0.90
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_classifier.py`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.classifier'`

- [ ] **Step 3: Implement `JevClassifier` in `app/services/classifier.py`**
Implement fast classification with calibrated heuristics and ready extension for TypeSafe AI Jev API.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_classifier.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/classifier.py services/api/tests/test_classifier.py
git commit -m "feat(api): implement fast listing classifier and trust score engine"
```

---

### Task 4: Parser & Scraper Leve do Mercado Livre (`curl_cffi` + `selectolax`)

**Files:**
- Create: `services/api/app/services/scrapers/mercadolivre.py`
- Create: `services/api/tests/fixtures/mercadolivre_search.html`
- Test: `services/api/tests/test_mercadolivre_scraper.py`

**Interfaces:**
- Consumes: `curl_cffi.AsyncSession`, `selectolax.lexbor.LexborHTMLParser`
- Produces: `MercadoLivreScraper.search(query: str, limit: int = 10) -> list[RawListing]`

- [ ] **Step 1: Write failing test with mock HTML fixture**
Create fixture `tests/fixtures/mercadolivre_search.html` containing real sample DOM nodes of Mercado Livre listings.
Write test:
```python
@pytest.mark.asyncio
async def test_mercadolivre_scraper_parses_html_correctly():
    scraper = MercadoLivreScraper()
    with open("tests/fixtures/mercadolivre_search.html", "r", encoding="utf-8") as f:
        html = f.read()
    results = scraper.parse_search_results(html, limit=5)
    assert len(results) == 5
    assert "iPhone 15" in results[0].title
    assert results[0].display_price > 0
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_mercadolivre_scraper.py`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `MercadoLivreScraper` in `app/services/scrapers/mercadolivre.py`**
Implement `parse_search_results` with `LexborHTMLParser` using high-speed CSS selectors and `search` using `AsyncSession(impersonate="chrome124")`.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_mercadolivre_scraper.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/scrapers/ services/api/tests/test_mercadolivre_scraper.py services/api/tests/fixtures/
git commit -m "feat(api): implement high-speed Mercado Livre scraper using curl_cffi and selectolax"
```

---

### Task 5: Endpoints da API: `POST /api/v1/search` e `GET /api/v1/merchant/status`

**Files:**
- Create: `services/api/app/routers/search.py`
- Create: `services/api/app/routers/merchants.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_search_api.py`

**Interfaces:**
- Endpoints:
  - `POST /api/v1/search` -> `SearchResponse`
  - `GET /api/v1/merchant/status` -> `MerchantStatusResponse`

- [ ] **Step 1: Write failing integration test for search and merchant endpoints**
```python
@pytest.mark.asyncio
async def test_search_api_endpoint():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/search", json={"query": "iPhone 15", "max_unit_price": 6000.0})
        assert res.status_code == 200
        data = res.json()
        assert "results" in data
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_search_api.py`
Expected: FAIL with 404 Not Found

- [ ] **Step 3: Implement routers and register in `app/main.py`**
Implement `app/routers/search.py` orchestrating scraper + classifier + pricing engine, and `app/routers/merchants.py` with domain verification status.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_search_api.py`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/app/routers/ services/api/app/main.py services/api/tests/test_search_api.py
git commit -m "feat(api): expose /api/v1/search and /api/v1/merchant/status endpoints"
```

---

### Task 6: Verificação do GOAL da Semana 2 & Teste E2E

**Files:**
- Create: `services/api/tests/test_week_2_goal.py`

- [ ] **Step 1: Write automated test validating Week 2 Goal**
```python
@pytest.mark.asyncio
async def test_week_2_goal_fast_search_and_pix_decomposition():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        res = await client.post("/api/v1/search", json={
            "query": "iPhone 15 128GB",
            "prefer_best_cash_price": True
        })
        assert res.status_code == 200
        results = res.json()["results"]
        assert len(results) >= 5
        for item in results:
            assert item["pricing"]["best_effective_price"] > 0
            assert item["pricing"]["fee_acp_estimated"] > 0
            assert item["merchant"]["trust_score"] >= 0.0
            assert item["execution_type"] in ["autonomous", "human_handoff"]
```

- [ ] **Step 2: Run full test suite**
Run: `uv run pytest -v`
Expected: ALL PASS (Week 1 concurrency tests + Week 2 search tests).

- [ ] **Step 3: Run Ponytail Review on Week 2 changes**

- [ ] **Step 4: Commit and Push**
```bash
git commit -m "feat: complete Week 2 search engine, Jev classification and cash pricing engine"
git push origin main
```
