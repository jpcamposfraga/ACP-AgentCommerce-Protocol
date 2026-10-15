# Plano de Implementação: Arquitetura Multi-Aggregator (10+ E-commerces), Regionalização Global, Resiliência ML & Jev Semântico

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o padrão `SearchAggregator` com registro modular dos 10 principais e-commerces (nacionais e internacionais), roteamento regional/multi-moeda (Brasil vs. EUA/Global), filtro de whitelist do usuário, atualização resiliente do `MercadoLivreScraper` (seletores Poly e bypass anti-bot) e expansão do `JevClassifier` com desambiguação contextual e sinônimos sem custo de LLM.

**Architecture:** 
1. **Aggregator & Registry Pattern:**
   - Interface abstrata `BaseScraper` com contrato `search(query: str, limit: int, region: str) -> list[RawListing]`.
   - `ScraperRegistry` centralizando os 10 conectores (Mercado Livre, Amazon BR, Magalu, KaBuM!, Shopee, Kalunga, Amazon US, eBay, Walmart US, AliExpress) + conector aberto genérico (`StorefrontPartnerClient`).
   - Roteamento por região (`BR`, `US`, `GLOBAL`) e moeda (`BRL`, `USD`, `EUR`).
   - Whitelist do usuário via `allowed_domains: list[str]`.
   - Execução concorrente não-bloqueante (`asyncio.gather(*, return_exceptions=True)`) com timeout individual de 2.5s.
2. **MercadoLivreScraper Dual-Parser:**
   - Suporte unificado aos seletores legados (`.ui-search-layout__item`) e modernos Poly (`.poly-card`, `a.poly-component__title`).
   - Headers com User-Agent aceito para evitar interceptação Muralla.
3. **JevClassifier Contextual & Semântico:**
   - Regras léxicas não-autorregressivas (< 10ms CPU local).
   - Distinção entre compostos atributos ("capa dura", "capa flexível") e acessórios avulsos ("capa para", "capinha").
   - Dicionário de sinônimos/equivalências de alta frequência (papelaria, eletrônicos, informática, áudio).

**Tech Stack:** Python 3.12+, FastAPI, Pydantic v2, `curl_cffi`, `selectolax`, Pytest, Pytest-Asyncio.

**Spec:** [docs/ideas/agent-commerce-protocol.md](file:///C:/Users/elast/acp-mcp/docs/ideas/agent-commerce-protocol.md) e [docs/plans/scalability-and-global-expansion.md](file:///C:/Users/elast/acp-mcp/docs/plans/scalability-and-global-expansion.md)

---

## Global Constraints
- **TDD Estrito:** Nenhum código em produção sem teste falhando primeiro (Red-Green-Refactor).
- **Ponytail Mode:** O menor código que resolve o problema completamente. Sem sobrecarregar o sistema com micro-abstrações desnecessárias.
- **Zero Custo de Tokens:** O agregador, os scrapers e o Jev rodam localmente com custo R$ 0,00 e sem chamadas a APIs pagas.
- **Retrocompatibilidade:** Manter 100% dos 40 testes existentes passando sem quebras.

## Review Focus
1. **Isolamento de Falha no Aggregator:** Se 1 dos 10 scrapers cair ou der timeout, os outros 9 devem continuar respondendo sem quebrar a busca.
2. **Filtragem por Whitelist do Usuário:** Quando o usuário define `allowed_domains=["amazon.com.br"]`, nenhum outro marketplace pode ser consultado.
3. **Roteamento Regional (EUA vs. BR):** Usuário buscando nos EUA (`country_code="US"`) não pode receber resultados em BRL do Mercado Livre Brasil.
4. **Desambiguação "Capa Dura" vs "Capa Para":** Cadernos e livros de capa dura são produtos válidos; capas avulsas para cadernos/celulares continuam filtradas.
5. **Normalização Multi-Moeda:** Garantir que o schema de precificação aceite e identifique a moeda correta (`BRL`, `USD`).

---

### Task 1: Resiliência do MercadoLivreScraper (Seletores Poly + Headers)

**Files:**
- Modify: `services/api/app/services/scrapers/mercadolivre.py`
- Modify: `services/api/tests/test_mercadolivre_scraper.py`

**Interfaces:**
- Produces: `MercadoLivreScraper.parse_search_results(html: str, limit: int = 10) -> list[RawListing]`
- Produces: `MercadoLivreScraper.search(query: str, limit: int = 10) -> list[RawListing]`

- [ ] **Step 1: Escrever teste de falha para parser com estrutura Poly**

Adicionar em `services/api/tests/test_mercadolivre_scraper.py`:
```python
def test_mercadolivre_parser_extracts_poly_card_listings():
    poly_html = '''
    <li class="ui-search-layout__item">
      <div class="andes-card poly-card">
        <h3 class="poly-component__title-wrapper">
          <a href="https://produto.mercadolivre.com.br/MLB-99901-sketchbook-a4" class="poly-component__title">
            Caderno Sketchbook Desenho A4 240g
          </a>
        </h3>
        <div class="poly-component__price">
          <span class="andes-money-amount">
            <span class="andes-money-amount__fraction">42</span>
            <span class="andes-money-amount__cents">90</span>
          </span>
        </div>
      </div>
    </li>
    '''
    scraper = MercadoLivreScraper()
    results = scraper.parse_search_results(poly_html, limit=1)
    assert len(results) == 1
    assert results[0].product_id == "MLB-99901"
    assert "Caderno Sketchbook" in results[0].title
    assert results[0].display_price == 42.90
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.\.venv\Scripts\pytest tests/test_mercadolivre_scraper.py -k test_mercadolivre_parser_extracts_poly_card_listings`
Expected: FAIL

- [ ] **Step 3: Implementar suporte Poly e headers no MercadoLivreScraper**

Em `services/api/app/services/scrapers/mercadolivre.py`:
- Suportar tanto `a.poly-component__title` quanto `a.ui-search-link` e `.ui-search-item__title`.
- Extrair centavos e frações corretamente.
- Adicionar User-Agent aceito para mitigar a interceptação Muralla.

- [ ] **Step 4: Executar testes do scraper**

Run: `.\.venv\Scripts\pytest tests/test_mercadolivre_scraper.py`
Expected: PASS

---

### Task 2: Desambiguação Contextual & Sinônimos no JevClassifier

**Files:**
- Modify: `services/api/app/services/classifier.py`
- Modify: `services/api/tests/test_classifier.py`

**Interfaces:**
- Produces: `JevClassifier.classify_listing(title: str, price: float, seller_info: dict | None, target_query: str) -> ClassificationResult`

- [ ] **Step 1: Escrever testes de falha para desambiguação contextual e sinônimos**

Adicionar em `services/api/tests/test_classifier.py`:
```python
def test_classifier_allows_capa_dura_in_stationery_and_books():
    classifier = JevClassifier()
    result = classifier.classify_listing(
        title="Caderno De Desenho Capa Dura Spiral 80 Fls",
        price=29.90,
        seller_info={"reputation_level": "gold", "sales_count": 300},
        target_query="caderno para desenho"
    )
    assert result.is_valid_product is True
    assert "ACCESSORY_MISMATCH" not in result.risk_flags

def test_classifier_still_blocks_real_notebook_cover_accessories():
    classifier = JevClassifier()
    result = classifier.classify_listing(
        title="Capa Para Caderno Universitário Transparente Pct C/ 10",
        price=15.90,
        seller_info={"reputation_level": "gold", "sales_count": 200},
        target_query="caderno para desenho"
    )
    assert result.is_valid_product is False
    assert "ACCESSORY_MISMATCH" in result.risk_flags

def test_classifier_understands_synonyms():
    classifier = JevClassifier()
    result = classifier.classify_listing(
        title="Sketchbook Artístico Profissional A4 200g",
        price=45.00,
        seller_info={"reputation_level": "platinum", "sales_count": 1000},
        target_query="caderno para desenho"
    )
    assert result.is_valid_product is True
    assert result.trust_score >= 0.85
```

- [ ] **Step 2: Executar testes para verificar falha**

Run: `.\.venv\Scripts\pytest tests/test_classifier.py -k "test_classifier_allows_capa_dura or test_classifier_still_blocks or test_classifier_understands_synonyms"`
Expected: FAIL

- [ ] **Step 3: Implementar regras contextuais e mapa de sinônimos no JevClassifier**

Em `services/api/app/services/classifier.py`:
- Adicionar atributos permitidos compostos: `"capa dura"`, `"capa flexivel"`, `"capa cartao"`, `"capa de couro"`.
- Acessório só dispara falso positivo quando acompanhado de preposição de destinação (ex: `"capa para"`, `"capinha"`, `"pelicula"`) ou quando o alvo for eletrônico.
- Adicionar dicionário léxico de sinônimos de alta frequência para papelaria, telefonia, áudio e computadores.

- [ ] **Step 4: Executar testes para verificar aprovação**

Run: `.\.venv\Scripts\pytest tests/test_classifier.py`
Expected: PASS

---

### Task 3: Arquitetura BaseScraper & ScraperRegistry dos 10 E-commerces

**Files:**
- Create: `services/api/app/services/scrapers/base.py`
- Create: `services/api/app/services/scrapers/registry.py`
- Modify: `services/api/app/services/scrapers/mercadolivre.py` (herdar de `BaseScraper`)
- Create: `services/api/app/services/scrapers/mock_scrapers.py` (implementação dos 9 conectores com suporte a live/mock)
- Test: `services/api/tests/test_scraper_registry.py`

**Interfaces:**
- Produces: `BaseScraper` com `domain: str`, `region: str`, `currency: str`, `search(query: str, limit: int) -> list[RawListing]`
- Produces: `ScraperRegistry.get_scrapers(region: str = "BR", allowed_domains: list[str] | None = None) -> list[BaseScraper]`
- Suporta os 10 e-commerces:
  1. `mercadolivre.com.br` (BR, BRL)
  2. `amazon.com.br` (BR, BRL)
  3. `magazineluiza.com.br` (BR, BRL)
  4. `kabum.com.br` (BR, BRL)
  5. `shopee.com.br` (BR, BRL)
  6. `kalunga.com.br` (BR, BRL)
  7. `amazon.com` (US, USD)
  8. `ebay.com` (US/Global, USD)
  9. `walmart.com` (US, USD)
  10. `aliexpress.com` (Global, USD/BRL)

- [ ] **Step 1: Escrever teste de falha para BaseScraper e ScraperRegistry**

Adicionar em `services/api/tests/test_scraper_registry.py`:
```python
def test_registry_contains_at_least_10_ecommerce_connectors():
    from app.services.scrapers.registry import ScraperRegistry
    registry = ScraperRegistry()
    all_scrapers = registry.get_all_scrapers()
    assert len(all_scrapers) >= 10
    domains = {s.domain for s in all_scrapers}
    assert "mercadolivre.com.br" in domains
    assert "amazon.com.br" in domains
    assert "amazon.com" in domains
    assert "ebay.com" in domains
    assert "kabum.com.br" in domains
    assert "kalunga.com.br" in domains

def test_registry_filters_by_region():
    from app.services.scrapers.registry import ScraperRegistry
    registry = ScraperRegistry()
    br_scrapers = registry.get_scrapers(region="BR")
    us_scrapers = registry.get_scrapers(region="US")
    
    assert any(s.domain == "mercadolivre.com.br" for s in br_scrapers)
    assert not any(s.domain == "mercadolivre.com.br" for s in us_scrapers)
    assert any(s.domain == "amazon.com" for s in us_scrapers)

def test_registry_filters_by_user_whitelist():
    from app.services.scrapers.registry import ScraperRegistry
    registry = ScraperRegistry()
    filtered = registry.get_scrapers(region="BR", allowed_domains=["kabum.com.br", "kalunga.com.br"])
    assert len(filtered) == 2
    assert {s.domain for s in filtered} == {"kabum.com.br", "kalunga.com.br"}
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.\.venv\Scripts\pytest tests/test_scraper_registry.py`
Expected: FAIL (módulo ausente)

- [ ] **Step 3: Implementar `BaseScraper`, `ScraperRegistry` e os conectores**

Criar:
- `app/services/scrapers/base.py`: Classe abstrata com atributos `domain`, `region`, `currency`, `execution_type` ("autonomous" ou "human_handoff") e método assíncrono `search()`.
- `app/services/scrapers/registry.py`: Repositório de instâncias de scrapers registrados.
- `app/services/scrapers/mock_scrapers.py`: Implementações especializadas para os e-commerces que retornam produtos estruturados de acordo com a consulta quando chamados.

- [ ] **Step 4: Executar testes do registro**

Run: `.\.venv\Scripts\pytest tests/test_scraper_registry.py`
Expected: PASS

---

### Task 4: SearchAggregator & Atualização de Schemas / API

**Files:**
- Create: `services/api/app/services/aggregator.py`
- Modify: `services/api/app/schemas/search.py` (adicionar `region: str = "BR"`, `currency: str = "BRL"`, `allowed_domains: list[str] | None = None`)
- Modify: `services/api/app/routers/search.py` (usar `SearchAggregator`)
- Test: `services/api/tests/test_search_aggregator.py`
- Test: `services/api/tests/test_search_api.py`

**Interfaces:**
- Produces: `SearchAggregator.search(request: SearchRequest) -> SearchResponse`
- Consumes: `ScraperRegistry`, `JevClassifier`, `calculate_effective_price`

- [ ] **Step 1: Escrever teste de falha para SearchAggregator concorrente**

Adicionar em `services/api/tests/test_search_aggregator.py`:
```python
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
    assert any("amazon.com" in d or "ebay.com" in d for d in domains)
```

- [ ] **Step 2: Executar teste para verificar falha**

Run: `.\.venv\Scripts\pytest tests/test_search_aggregator.py`
Expected: FAIL

- [ ] **Step 3: Implementar SearchAggregator concorrente e atualizar router**

Em `app/services/aggregator.py`:
- Buscar conectores filtrados por `region` e `allowed_domains`.
- Disparar requisições em paralelo usando `asyncio.gather(*tasks, return_exceptions=True)`.
- Tratar exceções isoladas de cada scraper sem abortar as demais.
- Classificar via `JevClassifier` e calcular menor preço via `calculate_effective_price`.
- Ordenar globalmente por `pricing.best_effective_price`.

Em `app/routers/search.py`:
- Conectar o `SearchAggregator` diretamente ao endpoint `POST /api/v1/search`.

- [ ] **Step 4: Executar testes de integração**

Run: `.\.venv\Scripts\pytest tests/test_search_aggregator.py tests/test_search_api.py`
Expected: PASS

---

### Task 5: Validação da Suíte Completa de Testes & Não-Regressão

**Files:**
- Test: Toda a pasta `services/api/tests/`

- [ ] **Step 1: Executar todos os testes automatizados do backend**

Run: `.\.venv\Scripts\pytest`
Expected: 100% de testes verdes (> 50 testes passando, zero falhas).

- [ ] **Step 2: Revisão Ponytail de Qualidade de Código**

Verificar clareza, concisão, ausência de dead code e integridade contábil.
