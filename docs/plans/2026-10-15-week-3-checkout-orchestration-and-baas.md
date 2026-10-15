# Semana 3: Orquestração de Checkout (Híbrido vs. Autônomo) & Webhook BaaS

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o motor de orquestração de checkout unificado (`POST /api/v1/checkout`), suportando compras autônomas em lojas parceiras com débito atômico de carteira e liquidação Pix via BaaS Sandbox, além de checkout híbrido seguro (1 clique) para ecossistemas fechados (Mercado Livre).

**Architecture:** Roteamento inteligente de checkout baseado no status de verificação do lojista. Lojas abertas/parceiras disparam a criação de pedido na Storefront API, debitam a carteira do usuário com conferência estrita de limites e realizam a emissão do Pix no BaaS em < 3 segundos. Lojas fechadas/não verificadas geram URLs seguras de carrinho para aprovação humana sem manusear credenciais do usuário. O sistema também recebe webhooks bancários de cash-in para recarga de carteira.

**Tech Stack:** Python 3.14+, FastAPI, SQLAlchemy (Async/SQLite/PostgreSQL), Pydantic v2, HTTPX / Curl-CFFI, Pytest, Pytest-Asyncio.

**Spec:** [docs/plans/mvp-4-weeks-implementation-plan.md](file:///C:/Users/elast/ACP-MCP/docs/plans/mvp-4-weeks-implementation-plan.md) e [docs/ideas/agent-commerce-protocol.md](file:///C:/Users/elast/ACP-MCP/docs/ideas/agent-commerce-protocol.md)

## Global Constraints
- `ACP_PLATFORM_FEE_PCT`: Taxa padrão de 2% (0.02) retida atomicamente no débito.
- Concorrência de carteira: Nenhuma compra pode permitir saldo negativo ou ultrapassar `daily_limit` e `max_per_order`.
- Evasão de Prompt Injection em endereços: Endereços físicos devem utilizar `shipping_profile_id` cadastrado no cofre.
- Idempotência: Webhooks bancários de Pix e requisições de checkout devem suportar chave de idempotência para evitar cobranças duplicadas.
- Hermeticidade de Testes: Todos os testes unitários e de integração devem rodar sem dependência de internet externa, utilizando mocks rápidos do BaaS e da Storefront API.

## Review Focus
1. **Tentativa de compra autônoma com saldo insuficiente:** Deve falhar imediatamente com HTTP 402 / 400 sem chamar o BaaS e sem alterar o saldo.
2. **Tentativa de compra autônoma que excede `max_per_order`:** Deve ser rejeitada com código específico de violação de governança.
3. **Webhook de recarga duplicado (Replay Attack):** Processamento do mesmo `end_to_end_id` deve ser idempotente e não creditar a carteira duas vezes.
4. **Loja fechada (Mercado Livre) em rota de checkout:** Deve obrigatoriamente rotear para modo híbrido (`pending_human_approval`) e nunca tentar debito financeiro autônomo.
5. **Falha na liquidação BaaS após reserva de saldo:** Deve realizar rollback atômico ou estorno do saldo reservado na carteira.

---

### Task 1: Contratos e Schemas Pydantic (`checkout.py` e `webhook.py`)

**Files:**
- Create: `services/api/app/schemas/checkout.py`
- Create: `services/api/app/schemas/webhook.py`
- Test: `services/api/tests/test_checkout_schemas.py`

**Interfaces:**
- Produces:
  - `CheckoutItem`: `product_id_or_url: str`, `quantity: int`, `unit_price: float`, `merchant_domain: str`
  - `CheckoutRequest`: `wallet_id: str`, `order_items: list[CheckoutItem]`, `shipping_profile_id: str`, `idempotency_key: str | None`
  - `PaymentReceipt`: `pix_end_to_end_id: str`, `paid_at: str`, `amount_transferred: float`, `acp_fee_retained: float`
  - `CheckoutResponse`: `order_id: str`, `status: Literal["completed", "pending_human_approval", "failed"]`, `execution_type: Literal["autonomous", "human_handoff"]`, `total_debited: float`, `handoff_url: str | None`, `receipt: PaymentReceipt | None`
  - `BaaSPixWebhook`: `event: str`, `payment_id: str`, `wallet_id: str`, `amount: float`, `end_to_end_id: str`

- [ ] **Step 1: Write failing schema validation tests**
Write `services/api/tests/test_checkout_schemas.py` validating valid inputs and boundary conditions (quantity >= 1, unit_price > 0, wallet_id UUID format, etc.).

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_checkout_schemas.py`
Expected: FAIL with `ModuleNotFoundError`.

- [ ] **Step 3: Implement schemas in `app/schemas/checkout.py` and `app/schemas/webhook.py`**
Implement the Pydantic models with field constraints.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_checkout_schemas.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add services/api/app/schemas/checkout.py services/api/app/schemas/webhook.py services/api/tests/test_checkout_schemas.py
git commit -m "feat(api): define checkout and baas webhook schemas"
```

---

### Task 2: Cliente BaaS Sandbox & Endpoint de Webhook Pix (`/api/v1/webhooks/pix`)

**Files:**
- Create: `services/api/app/services/baas.py`
- Create: `services/api/app/routers/webhooks.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_baas_and_webhooks.py`

**Interfaces:**
- Consumes: `Wallet` model, database session, `BaaSPixWebhook`
- Produces:
  - `BaaSPixClient.send_pix_payout(amount: float, pix_key: str, description: str) -> dict`
  - `POST /api/v1/webhooks/pix`: Endpoint assíncrono que credita o saldo da carteira atomicamente e registra transação de tipo `deposit`.

- [ ] **Step 1: Write failing tests for BaaS client and webhook endpoint**
Write tests simulating:
1. `BaaSPixClient` emitting a mock payout and generating an `end_to_end_id`.
2. `POST /api/v1/webhooks/pix` receiving a deposit event and incrementing the wallet balance.
3. Idempotent webhook handling (duplicate `end_to_end_id` returns 200 without double credit).

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_baas_and_webhooks.py`
Expected: FAIL.

- [ ] **Step 3: Implement `BaaSPixClient` and `webhooks.py` router**
Implement the BaaS service adapter in `app/services/baas.py`, create router in `app/routers/webhooks.py`, and register in `app/main.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_baas_and_webhooks.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/baas.py services/api/app/routers/webhooks.py services/api/app/main.py services/api/tests/test_baas_and_webhooks.py
git commit -m "feat(api): implement baas sandbox client and pix deposit webhook"
```

---

### Task 3: Conector de Loja Aberta (Storefront API Adapter & Partner Mock)

**Files:**
- Create: `services/api/app/services/connectors/storefront.py`
- Test: `services/api/tests/test_storefront_connector.py`

**Interfaces:**
- Produces:
  - `PartnerOrderResult(order_id: str, total_price: float, pix_copia_e_cola: str, pix_key: str, status: str)`
  - `StorefrontPartnerClient.create_order(items: list[CheckoutItem], shipping_profile_id: str) -> PartnerOrderResult`

- [ ] **Step 1: Write failing unit test for Storefront Partner connector**
Create unit test testing order creation, calculation of totals, generation of mock Pix Copia-e-Cola payload, and shipping profile assignment.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_storefront_connector.py`
Expected: FAIL.

- [ ] **Step 3: Implement `StorefrontPartnerClient`**
Implement the client capable of interacting with open partner e-commerce APIs (e.g. Shopify Storefront API structure or local partner sandbox).

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_storefront_connector.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/connectors/storefront.py services/api/tests/test_storefront_connector.py
git commit -m "feat(api): implement open storefront partner connector"
```

---

### Task 4: Motor de Checkout Híbrido (Mercado Livre / Hand-off Seguro)

**Files:**
- Create: `services/api/app/services/connectors/hybrid_meli.py`
- Test: `services/api/tests/test_hybrid_checkout.py`

**Interfaces:**
- Produces:
  - `generate_meli_cart_url(items: list[CheckoutItem]) -> str`
  - Sanitization of parameters to prevent open redirects or malformed URLs.

- [ ] **Step 1: Write failing test for hybrid checkout generator**
Test that given Mercado Livre SKUs/URLs, it produces a clean, validated direct cart URL for human approval without exposing sensitive credentials.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_hybrid_checkout.py`
Expected: FAIL.

- [ ] **Step 3: Implement `hybrid_meli.py`**
Implement URL construction and validation logic according to Mercado Livre checkout structure.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_hybrid_checkout.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/connectors/hybrid_meli.py services/api/tests/test_hybrid_checkout.py
git commit -m "feat(api): implement hybrid checkout cart generator for closed marketplaces"
```

---

### Task 5: Orquestrador & Endpoint `POST /api/v1/checkout`

**Files:**
- Create: `services/api/app/routers/checkout.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_checkout_api.py`

**Interfaces:**
- Consumes: `WalletService`, `StorefrontPartnerClient`, `BaaSPixClient`, `hybrid_meli`, `MerchantStatus`
- Produces:
  - `POST /api/v1/checkout` -> `CheckoutResponse`

- [ ] **Step 1: Write failing integration tests for `/api/v1/checkout`**
Test cases:
1. Autonomous purchase on verified partner: wallet debited with 2% ACP fee, BaaS Pix dispatched, status `completed`, receipt returned.
2. Closed marketplace (Meli): returns status `pending_human_approval`, zero wallet debit, `handoff_url` populated.
3. Unverified suspicious store: rejected with status `failed` or forced to human hand-off.
4. Insufficient wallet balance: HTTP 402 or error response, 0 balance change.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_checkout_api.py`
Expected: FAIL with 404 Not Found.

- [ ] **Step 3: Implement router in `app/routers/checkout.py` and register in `app/main.py`**
Implement intelligent routing, atomic debit integration with `wallets.py` engine, BaaS payment dispatch, and transaction audit trail.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_checkout_api.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add services/api/app/routers/checkout.py services/api/app/main.py services/api/tests/test_checkout_api.py
git commit -m "feat(api): implement unified POST /api/v1/checkout router"
```

---

### Task 6: Verificação do GOAL da Semana 3 & Ponytail Review

**Files:**
- Create: `services/api/tests/test_week_3_goal.py`

- [ ] **Step 1: Write automated E2E test validating Week 3 Goal**
Validate in a single test file:
1. Modo Autônomo com R$ 500,00 de compra + R$ 10,00 de taxa (2%) liquidado em BaaS sandbox em < 3 segundos.
2. Modo Híbrido com link seguro do Mercado Livre gerado com status `pending_human_approval`.
3. Recarga via Webhook Pix BaaS de R$ 1.000,00 elevando saldo da carteira.

- [ ] **Step 2: Run full test suite across project**
Run: `uv run pytest -v`
Expected: ALL PASS (~26+ tests passing in < 2 seconds).

- [ ] **Step 3: Run Ponytail Review on Week 3 changes**
Review code for simplicity, safety, scale, and absence of bloat.

- [ ] **Step 4: Commit and Push**
```bash
git add services/api/tests/test_week_3_goal.py
git commit -m "test(api): add automated e2e verification for week 3 goal"
git push origin main
```
