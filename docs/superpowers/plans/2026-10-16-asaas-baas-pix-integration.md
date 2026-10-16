# Asaas BaaS Pix Real Integration Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Conectar o AgentCommerce Protocol (ACP) à API bancária oficial do Asaas para habilitar movimentação de dinheiro real via Pix (Cash-in para recarga de carteira e Cash-out para compras autônomas de agentes).

**Architecture:** Implementar um cliente HTTP assíncrono (`AsaasClient`) sobre `httpx` que se comunica com a API REST v3 do Asaas (`https://api.asaas.com/v3`), integrá-lo de forma transparente ao `BaaSPixClient` existente com chaveamento automático (Modo Real quando `ASAAS_API_KEY` estiver presente, Modo Mock/Sandbox quando vazia para testes e CI), criar o endpoint de recarga de carteira (`POST /api/v1/wallets/{id}/pix-deposit`) retornando Pix Copia-e-Cola / QR Code real, e processar webhooks de confirmação bancária (`POST /api/v1/webhooks/asaas`) com validação de token e idempotência atômica.

**Tech Stack:** Python 3.12+, FastAPI, httpx, SQLAlchemy Assíncrono, Pydantic v2, pytest, pytest-asyncio.

**Spec:** [docs/ideas/agent-commerce-protocol.md](file:///C:/Users/elast/ACP-MCP/docs/ideas/agent-commerce-protocol.md) (Seção 3: Camada de Liquidação Financeira BaaS).

## Global Constraints

- **Fallback Hermético:** Se `ASAAS_API_KEY` não for informada no ambiente, o sistema DEVE manter o comportamento de simulação/mock local sem quebrar nenhum teste automatizado existente.
- **Segurança de Credenciais:** `ASAAS_API_KEY` e `ASAAS_WEBHOOK_ACCESS_TOKEN` devem ser carregadas estritamente de variáveis de ambiente (`.env`) e nunca expostas em logs, respostas públicas ou commits.
- **Idempotência Estrita:** Webhooks do Asaas podem ser reenviados por indisponibilidade de rede. Nenhuma transação pode creditar ou debitar saldo mais de uma vez.
- **TDD:** Cada tarefa deve seguir rigorosamente o ciclo Red-Green-Refactor.

## Review Focus

- Detecção e formatação automática do tipo de chave Pix (`CPF`, `CNPJ`, `EMAIL`, `PHONE`, `EVP`) no cash-out.
- Tratamento de falhas de comunicação com a API do Asaas (timeout, erro 400, saldo insuficiente na conta bancária do Asaas).
- Formatação correta do payload do Webhook do Asaas (`event == "PAYMENT_RECEIVED"`).
- Validação de cabeçalho `asaas-access-token` no webhook de recebimento.
- Integridade matemática do débito da taxa ACP de 2% durante o cash-out real.

---

### Task 1: Configuração & Cliente HTTP Oficial do Asaas (`AsaasClient`)

**Files:**
- Modify: `services/api/app/core/config.py`
- Create: `services/api/app/services/baas_asaas.py`
- Test: `services/api/tests/test_baas_asaas_client.py`

**Interfaces:**
- Consumes: `settings.ASAAS_API_KEY`, `settings.ASAAS_BASE_URL`
- Produces: `AsaasClient`:
  - `send_pix_transfer(value: float, pix_key: str, pix_key_type: Optional[str] = None, description: str = "") -> dict`
  - `create_pix_charge(customer_id: str, value: float, description: str, external_reference: str) -> dict`
  - `get_pix_qr_code(payment_id: str) -> dict`
  - `detect_pix_key_type(pix_key: str) -> str`

- [ ] **Step 1: Write the failing tests for `AsaasClient`**

```python
@pytest.mark.asyncio
async def test_detect_pix_key_type():
    client = AsaasClient(api_key="fake")
    assert client.detect_pix_key_type("user@test.com") == "EMAIL"
    assert client.detect_pix_key_type("12345678909") == "CPF"
    assert client.detect_pix_key_type("12345678000199") == "CNPJ"
    assert client.detect_pix_key_type("+5511999998888") == "PHONE"
    assert client.detect_pix_key_type("9b1deb4d-3b7d-4bad-9bdd-2b0d7b3dcb6d") == "EVP"

@pytest.mark.asyncio
async def test_send_pix_transfer_success(httpx_mock):
    httpx_mock.add_response(
        url="https://api.asaas.com/v3/transfers",
        method="POST",
        json={
            "id": "transf_123",
            "status": "DONE",
            "endToEndIdentifier": "E1960301020261016123456",
            "value": 29.90
        }
    )
    client = AsaasClient(api_key="sec_token_test", base_url="https://api.asaas.com/v3")
    res = await client.send_pix_transfer(value=29.90, pix_key="loja@teste.com", description="ACP Test")
    assert res["status"] == "DONE"
    assert res["endToEndIdentifier"] == "E1960301020261016123456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_baas_asaas_client.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `AsaasClient` and update `Settings`**

Adicionar variáveis `ASAAS_API_KEY: str = ""`, `ASAAS_BASE_URL: str = "https://api.asaas.com/v3"`, `ASAAS_WEBHOOK_ACCESS_TOKEN: str = ""` no `app/core/config.py`.
Implementar `AsaasClient` em `services/api/app/services/baas_asaas.py` utilizando `httpx.AsyncClient` com timeout seguro e mapeamento de chaves Pix.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_baas_asaas_client.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 1**

```bash
git add services/api/app/core/config.py services/api/app/services/baas_asaas.py services/api/tests/test_baas_asaas_client.py
git commit -m "feat(baas): implement official Asaas HTTP client and settings"
```

---

### Task 2: Integração Transparente com `BaaSPixClient` (Chaveamento Real / Mock)

**Files:**
- Modify: `services/api/app/services/baas.py`
- Test: `services/api/tests/test_baas_and_webhooks.py`

**Interfaces:**
- Consumes: `settings.ASAAS_API_KEY`, `AsaasClient`
- Produces: `BaaSPixClient.send_pix_payout(amount: float, pix_key: str, description: str = "") -> dict` com suporte a execução real em produção e mock em desenvolvimento.

- [ ] **Step 1: Write tests for real execution vs. fallback mock**

```python
@pytest.mark.asyncio
async def test_baas_client_delegates_to_asaas_when_configured(monkeypatch):
    client = BaaSPixClient()
    monkeypatch.setattr("app.core.config.settings.ASAAS_API_KEY", "real_key_123")
    
    async def mock_transfer(self, value, pix_key, pix_key_type=None, description=""):
        return {"status": "DONE", "endToEndIdentifier": "E_REAL_123456", "value": value}
        
    monkeypatch.setattr("app.services.baas_asaas.AsaasClient.send_pix_transfer", mock_transfer)
    res = await client.send_pix_payout(amount=45.0, pix_key="pix@loja.com", description="Order #1")
    assert res["status"] == "CONFIRMED"
    assert res["end_to_end_id"] == "E_REAL_123456"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_baas_and_webhooks.py -k test_baas_client_delegates_to_asaas_when_configured -v`
Expected: FAIL

- [ ] **Step 3: Implement delegation in `BaaSPixClient`**

Em `services/api/app/services/baas.py`, checar se `settings.ASAAS_API_KEY` possui valor. Se sim, instanciar `AsaasClient` e chamar `send_pix_transfer`. Se não, manter o mock local existente.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_baas_and_webhooks.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 2**

```bash
git add services/api/app/services/baas.py services/api/tests/test_baas_and_webhooks.py
git commit -m "feat(baas): wire real Asaas pix transfers into BaaSPixClient with mock fallback"
```

---

### Task 3: Endpoint de Cash-in (Recarga de Carteira via Pix Copia-e-Cola Real)

**Files:**
- Create: `services/api/app/schemas/deposit.py`
- Modify: `services/api/app/routers/wallets.py`
- Test: `services/api/tests/test_wallet_deposit_api.py`

**Interfaces:**
- Consumes: `wallet_id: str`, `amount: float`
- Produces: `POST /api/v1/wallets/{wallet_id}/pix-deposit` retornando `qr_code_base64`, `copy_paste_payload`, `payment_id`, `expiration_date`.

- [ ] **Step 1: Write failing tests for `POST /api/v1/wallets/{id}/pix-deposit`**

```python
@pytest.mark.asyncio
async def test_wallet_pix_deposit_generates_copy_paste_payload(client: AsyncClient):
    # Setup carteira
    wallet_res = await client.post("/api/v1/wallets", json={"user_id": "user_dep_test", "max_per_order": 500, "daily_limit": 1000})
    wallet_id = wallet_res.json()["id"]

    res = await client.post(f"/api/v1/wallets/{wallet_id}/pix-deposit", json={"amount": 50.0})
    assert res.status_code == 200
    data = res.json()
    assert "copy_paste_payload" in data
    assert data["copy_paste_payload"].startswith("00020126")
    assert data["value"] == 50.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_wallet_deposit_api.py -v`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Implement `pix-deposit` endpoint**

Criar schemas em `app/schemas/deposit.py`. Adicionar rota `POST /api/v1/wallets/{wallet_id}/pix-deposit` em `app/routers/wallets.py`. Se `settings.ASAAS_API_KEY` estiver configurada, chama o Asaas para criar cobrança Pix e buscar o QR Code; se estiver em mock, gera um payload EMV padrão válido.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_wallet_deposit_api.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 3**

```bash
git add services/api/app/schemas/deposit.py services/api/app/routers/wallets.py services/api/tests/test_wallet_deposit_api.py
git commit -m "feat(wallets): add Pix cash-in deposit endpoint with Copia-e-Cola payload"
```

---

### Task 4: Webhook do Asaas para Crédito Instantâneo de Saldo

**Files:**
- Modify: `services/api/app/routers/webhooks.py`
- Test: `services/api/tests/test_asaas_webhook.py`

**Interfaces:**
- Consumes: `POST /api/v1/webhooks/asaas`
- Produces: Crédito atômico na `Wallet` e criação de `Transaction` contábil com status `COMPLETED`.

- [ ] **Step 1: Write failing tests for Asaas Webhook handling**

```python
@pytest.mark.asyncio
async def test_asaas_webhook_credits_wallet_on_payment_received(client: AsyncClient):
    wallet_res = await client.post("/api/v1/wallets", json={"user_id": "user_wh_test", "max_per_order": 500, "daily_limit": 1000})
    wallet_id = wallet_res.json()["id"]

    webhook_payload = {
        "event": "PAYMENT_RECEIVED",
        "payment": {
            "id": "pay_asaas_999888",
            "value": 75.0,
            "netValue": 74.01,
            "externalReference": wallet_id,
            "status": "RECEIVED"
        }
    }
    res = await client.post("/api/v1/webhooks/asaas", json=webhook_payload)
    assert res.status_code == 200
    assert res.json()["status"] == "credited"

    # Confere saldo
    check = await client.get(f"/api/v1/wallets/{wallet_id}")
    assert check.json()["balance"] == 75.0
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_asaas_webhook.py -v`
Expected: FAIL with `404 Not Found`

- [ ] **Step 3: Implement `POST /api/v1/webhooks/asaas`**

Em `app/routers/webhooks.py`, implementar o handler para o formato de webhook do Asaas:
1. Validar `asaas-access-token` do header se `settings.ASAAS_WEBHOOK_ACCESS_TOKEN` estiver configurado.
2. Filtrar evento `PAYMENT_RECEIVED`.
3. Validar idempotência por `payment.id`.
4. Executar update atômico no `Wallet.balance`.
5. Inserir `Transaction(type="TOPUP", reference_id=payment.id)`.

- [ ] **Step 4: Run test to verify it passes**

Run: `uv run pytest tests/test_asaas_webhook.py -v`
Expected: PASS

- [ ] **Step 5: Commit Task 4**

```bash
git add services/api/app/routers/webhooks.py services/api/tests/test_asaas_webhook.py
git commit -m "feat(webhooks): implement Asaas payment webhook with atomic wallet crediting"
```

---

### Task 5: Validação de Integração Ponta a Ponta (Fluxo Completo de Dinheiro)

**Files:**
- Create: `services/api/tests/test_asaas_e2e_flow.py`

**Interfaces:**
- Simula a jornada completa:
  1. Cria carteira zerada.
  2. Gera recarga Pix Copia-e-Cola de R$ 100,00.
  3. Recebe webhook do Asaas confirmando o Pix.
  4. Agente faz checkout autônomo de R$ 50,00 + taxa 2% (R$ 51,00).
  5. Saldo final da carteira: R$ 49,00.
  6. Recibo contém ID da transferência bancária gerada.

- [ ] **Step 1: Write and run end-to-end mission test**

```python
@pytest.mark.asyncio
async def test_full_asaas_cash_in_and_autonomous_cash_out_cycle(client: AsyncClient):
    ...
```

- [ ] **Step 2: Run test to verify it passes**

Run: `uv run pytest tests/test_asaas_e2e_flow.py -v`
Expected: PASS

- [ ] **Step 3: Run full suite to ensure zero regressions**

Run: `uv run pytest tests/ -v` and `npm test` inside `packages/mcp-server`.
Expected: 100% PASS

- [ ] **Step 4: Commit Task 5**

```bash
git add services/api/tests/test_asaas_e2e_flow.py
git commit -m "test: add end-to-end integration test for full Asaas cash-in and cash-out cycle"
```
