# Fix Broken Marketplace Product & Handoff URLs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Corrigir os links quebrados (erro 404 / página não existe) gerados para produtos e checkouts híbridos do Mercado Livre no AgentCommerce Protocol.

**Architecture:** Implementar higienização canônica de URLs no scraper do Mercado Livre (removendo hash e tracking tags poluentes), introduzir um cache local em memória associando `product_id -> canonical_url` para permitir resolução reversa instantânea quando o agente passar apenas o ID, refatorar o conector híbrido (`build_meli_handoff_url`) para não injetar parâmetros que ativam detecção/erro no Mercado Livre (como `?quantity=1`) e ajustar os schemas do MCP server para instruir agentes a priorizarem a passagem de URLs completas.

**Tech Stack:** Python 3.12+, FastAPI, selectolax, curl_cffi, TypeScript/Node.js, MCP SDK, pytest.

**Spec:** [docs/ideas/agent-commerce-protocol.md](file:///C:/Users/elast/ACP-MCP/docs/ideas/agent-commerce-protocol.md) (Seção 4: Modo Híbrido & Conectores).

## Global Constraints

- Manter 100% de compatibilidade com os endpoints existentes (`/api/v1/search`, `/api/v1/checkout`).
- Nenhuma dependência externa pesada nova (aplicar Ponytail: código mínimo, usar stdlib `urllib.parse` e estruturas em memória).
- Todos os testes unitários e de integração existentes devem continuar verdes.
- Test-Driven Development (TDD) estrito em cada etapa com verificação de falha antes da implementação.

## Review Focus

- Sanitização de URLs com query parameters complexos ou hashes do Mercado Livre sem perder o path original.
- Resolução de catálogo (`/p/MLB...`) vs. anúncios de vendedor (`produto.mercadolivre.com.br/MLB-...-slug-_JM`).
- Resolução reversa de produto quando o cliente MCP envia apenas `product_id`.
- Eliminação do parâmetro `?quantity=1` que aciona checkpoint e bloqueio de segurança na página de produto do Mercado Livre.
- Não quebra de URLs de outros marketplaces suportados pelo conector ou lojas parceiras abertas.

---

### Task 1: URL Sanitization & Canonicalization no Scraper do Mercado Livre

**Files:**
- Modify: `services/api/app/services/scrapers/mercadolivre.py`
- Test: `services/api/tests/test_mercadolivre_scraper.py`

**Interfaces:**
- Consumes: URLs brutas extraídas dos cards de busca do Mercado Livre (ex: com `#polycard_client=...`, `&tracking_id=...`).
- Produces: `clean_meli_url(raw_url: str) -> str` que devolve a URL limpa e canônica preservando o domínio original e o path (`/p/MLB...` ou `produto.mercadolivre.com.br/...`).

- [ ] **Step 1: Write the failing tests for Mercado Livre URL cleaning**

```python
def test_clean_meli_url_catalog_product():
    raw = "https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico/p/MLB2096580517#polycard_client=search-desktop&be_origin=backend&tracking_id=123"
    assert clean_meli_url(raw) == "https://www.mercadolivre.com.br/caderno-sketchbook-desenho-artistico/p/MLB2096580517"

def test_clean_meli_url_standard_item():
    raw = "https://produto.mercadolivre.com.br/MLB-4286916381-sketchbook-caderno-desenho-_JM?searchVariation=123&tracking_id=456"
    assert clean_meli_url(raw) == "https://produto.mercadolivre.com.br/MLB-4286916381-sketchbook-caderno-desenho-_JM"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/api/tests/test_mercadolivre_scraper.py -k test_clean_meli_url -v`
Expected: FAIL with `NameError: name 'clean_meli_url' is not defined`

- [ ] **Step 3: Implement `clean_meli_url` and use it in `parse_search_results`**

Implementar `clean_meli_url(url: str) -> str` usando `urllib.parse.urlsplit` e `urllib.parse.urlunsplit`, descartando query parameters de tracking e fragment (`#...`), e aplicar no `parse_search_results` de `MercadoLivreScraper`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest services/api/tests/test_mercadolivre_scraper.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add services/api/app/services/scrapers/mercadolivre.py services/api/tests/test_mercadolivre_scraper.py
git commit -m "fix(scraper): sanitize and canonicalize Mercado Livre product urls"
```

---

### Task 2: Product URL Registry / Cache para Resolução Reversa de IDs

**Files:**
- Create: `services/api/app/services/product_registry.py`
- Modify: `services/api/app/services/aggregator.py`
- Test: `services/api/tests/test_product_registry.py`

**Interfaces:**
- Consumes: `product_id: str`, `url: str`
- Produces: `product_registry.register(product_id: str, url: str) -> None`, `product_registry.get_url(product_id: str) -> Optional[str]`

- [ ] **Step 1: Write the failing tests for product registry**

```python
def test_product_registry_store_and_lookup():
    from app.services.product_registry import ProductRegistry
    reg = ProductRegistry()
    reg.register("MLB2096580517", "https://www.mercadolivre.com.br/caderno-desenho/p/MLB2096580517")
    # Lookup by identical ID
    assert reg.get_url("MLB2096580517") == "https://www.mercadolivre.com.br/caderno-desenho/p/MLB2096580517"
    # Lookup by hyphenated ID
    assert reg.get_url("MLB-2096580517") == "https://www.mercadolivre.com.br/caderno-desenho/p/MLB2096580517"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/api/tests/test_product_registry.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `ProductRegistry` and wire into `SearchAggregator`**

Criar singleton `product_registry` com dict LRU ou TTL simples thread-safe / async-safe, normalizando chaves removendo hífens (`MLB-123` e `MLB123` apontam para a mesma chave). No `SearchAggregator.search`, registrar cada oferta encontrada no `product_registry`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest services/api/tests/test_product_registry.py services/api/tests/test_search_aggregator.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add services/api/app/services/product_registry.py services/api/app/services/aggregator.py services/api/tests/test_product_registry.py
git commit -m "feat(registry): add product URL registry for reverse ID lookup"
```

---

### Task 3: Refatoração do Conector Híbrido (`build_meli_handoff_url`)

**Files:**
- Modify: `services/api/app/services/connectors/hybrid_meli.py`
- Test: `services/api/tests/test_hybrid_checkout.py`

**Interfaces:**
- Consumes: `product_id_or_url: str`, `quantity: int = 1`, `product_registry`
- Produces: `build_meli_handoff_url(product_id_or_url: str, quantity: int = 1) -> str`

- [ ] **Step 1: Write failing tests for hybrid checkout URL generation**

```python
def test_build_meli_handoff_with_full_catalog_url():
    url = "https://www.mercadolivre.com.br/caderno-sketchbook/p/MLB2096580517#tracking=xyz"
    handoff = build_meli_handoff_url(url, quantity=1)
    # Must NOT contain tracking hash or broken quantity parameter
    assert handoff == "https://www.mercadolivre.com.br/caderno-sketchbook/p/MLB2096580517"

def test_build_meli_handoff_with_registered_id():
    from app.services.product_registry import product_registry
    product_registry.register("MLB2096580517", "https://www.mercadolivre.com.br/caderno/p/MLB2096580517")
    handoff = build_meli_handoff_url("MLB-2096580517", quantity=1)
    assert handoff == "https://www.mercadolivre.com.br/caderno/p/MLB2096580517"

def test_build_meli_handoff_fallback_catalog_id():
    # If not registered and matches catalog format MLB\d{8,}
    handoff = build_meli_handoff_url("MLB2096580517", quantity=1)
    assert handoff == "https://www.mercadolivre.com.br/p/MLB2096580517"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest services/api/tests/test_hybrid_checkout.py -v`
Expected: FAIL due to `quantity=1` query string injection and lack of registry lookup.

- [ ] **Step 3: Implement resilient `build_meli_handoff_url`**

Atualizar `build_meli_handoff_url`:
1. Se for URL completa HTTP/HTTPS: validar domínio, remover hash e query strings inúteis/bloqueadas. Não injetar `?quantity=1` (páginas de produto ML tratam quantidade no botão interno).
2. Se for ID: consultar `product_registry.get_url(product_id)`. Se encontrado, retornar a URL real higienizada.
3. Se não encontrado no cache: se tiver padrão de catálogo (`MLB\d{8,}`), direcionar para `https://www.mercadolivre.com.br/p/{clean_id}`; se tiver slug/hífen antigo, usar `https://produto.mercadolivre.com.br/{clean_id}` limpo sem `quantity=1`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest services/api/tests/test_hybrid_checkout.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 3**

```bash
git add services/api/app/services/connectors/hybrid_meli.py services/api/tests/test_hybrid_checkout.py
git commit -m "fix(checkout): resolve real product URLs and remove invalid quantity params in hybrid handoff"
```

---

### Task 4: Atualização do Schema da Tool MCP `checkout`

**Files:**
- Modify: `packages/mcp-server/src/tools/checkout.ts`
- Test: `packages/mcp-server/tests/api-client.test.ts`

**Interfaces:**
- Consumes: Chamada do modelo de linguagem via MCP
- Produces: Prompting claro no schema Zod instruindo o agente a passar a URL retornada na busca (`url`).

- [ ] **Step 1: Write test or check description in MCP tool**

Verificar que a tool aceita URLs completas e que a documentação de `product_id_or_url` orienta o modelo a enviar preferencialmente a `url` obtida no `search_products`.

- [ ] **Step 2: Update schema description in `packages/mcp-server/src/tools/checkout.ts`**

Ajustar a descrição de `product_id_or_url` para:
`"URL direta do produto retornada na busca (preferencial, garante link 100% válido) ou ID do produto (ex: 'https://produto.mercadolivre.com.br/...', 'MLB-1001')"`

- [ ] **Step 3: Rebuild MCP server and run tests**

Run: `npm run build` and `npm test` inside `packages/mcp-server`.
Expected: PASS

- [ ] **Step 4: Commit Task 4**

```bash
git add packages/mcp-server/src/tools/checkout.ts packages/mcp-server/dist/
git commit -m "docs(mcp): clarify product_id_or_url description to prefer canonical url"
```

---

### Task 5: Validação de Ponta a Ponta com o Cenário Real do Usuário ("Caderno de Desenho")

**Files:**
- Test: `services/api/tests/test_week_3_goal.py` e novo teste `services/api/tests/test_real_world_meli_checkout.py`

**Interfaces:**
- Simula o fluxo idêntico ao do usuário:
  1. `POST /api/v1/search` com query "caderno sketchbook desenho".
  2. Pega o primeiro produto (seja catálogo ou item individual).
  3. `POST /api/v1/checkout` passando ora o `product_id`, ora a `url`.
  4. Valida que o `handoff_url` retornado é uma URL válida que não contém `?quantity=1` e não direciona para 404.

- [ ] **Step 1: Write end-to-end integration test**

```python
@pytest.mark.asyncio
async def test_real_world_meli_search_and_checkout_handoff(client: AsyncClient):
    # 1. Search products
    res_search = await client.post("/api/v1/search", json={"query": "caderno sketchbook desenho"})
    assert res_search.status_code == 200
    results = res_search.json()["results"]
    assert len(results) > 0
    top = results[0]

    # 2. Checkout passing product_id
    res_checkout = await client.post("/api/v1/checkout", json={
        "wallet_id": "any",
        "order_items": [{
            "product_id_or_url": top["product_id"],
            "quantity": 1,
            "unit_price": top["pricing"]["display_price"],
            "merchant_domain": top["merchant"]["domain"]
        }]
    })
    assert res_checkout.status_code == 200
    handoff_url = res_checkout.json()["handoff_url"]
    assert "quantity=1" not in handoff_url
    assert handoff_url.startswith("https://")
    assert "mercadolivre.com.br" in handoff_url
```

- [ ] **Step 2: Run test and verify it passes**

Run: `uv run pytest services/api/tests/test_real_world_meli_checkout.py -v`
Expected: PASS

- [ ] **Step 3: Run full suite to ensure zero regressions**

Run: `uv run pytest services/api/tests/ -v`
Expected: 100% PASS

- [ ] **Step 4: Commit Task 5**

```bash
git add services/api/tests/test_real_world_meli_checkout.py
git commit -m "test: add end-to-end validation for real-world Mercado Livre checkout handoff"
```
