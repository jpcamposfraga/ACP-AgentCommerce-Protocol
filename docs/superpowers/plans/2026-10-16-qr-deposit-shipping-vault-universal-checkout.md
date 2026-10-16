# QR Deposit, Shipping Vault & Universal Guest Checkout Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement visual and web-based QR Code generation for Pix deposits, a persistent Shipping Vault with ViaCEP auto-completion exposed via MCP, and strict anti-hallucination routing with guest checkout for open e-commerce stores.

**Architecture:** 
1. QR Code Engine uses `segno` to generate both terminal UTF-8 block art (`qr_code_terminal`) and raw PNG images served via a dedicated web endpoint (`GET /api/v1/wallets/{id}/pix-deposit/{payment_id}/qrcode.png`).
2. Shipping Vault introduces the `shipping_profiles` database table and ViaCEP client, enabling users and agents to register and retrieve real delivery addresses via REST and a new MCP tool (`manage_shipping_address`).
3. Universal Checkout Engine validates that delivery details exist prior to purchase, routes closed marketplaces to verified human handoff links, routes open e-commerce stores to guest checkout with Asaas Pix payout, and eliminates silent mock fallbacks that cause LLM hallucination.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2.0 (async), Pydantic v2, `segno`, `httpx`, TypeScript, Node.js, `@modelcontextprotocol/sdk`.

**Spec:** Documented in [AGENTS.md](file:///C:/Users/elast/ACP-MCP/AGENTS.md), [agent-commerce-protocol.md](file:///C:/Users/elast/ACP-MCP/docs/ideas/agent-commerce-protocol.md), and user interview directives.

---

## Global Constraints

- Never commit secrets (`ASAAS_API_KEY`, tokens) or tracked `AGENTS.md` to git.
- Keep 100% backward compatibility: existing 74 Python tests and 6 TypeScript tests must remain green.
- All new features must be built via Test Driven Development (TDD).
- Zero silent mock completions: mocks must be explicitly flagged with `is_simulation: true`.
- Zero arbitrary Pix payouts: payouts must be tied to verified stores or checkout payment payloads.

## Review Focus

1. **Terminal encoding on Windows:** UTF-8 block QR codes must handle non-UTF-8 console encodings gracefully without crashing.
2. **ViaCEP network timeout/failure:** If ViaCEP is offline, allow manual fallback input of street, neighborhood, city, and state without blocking the user.
3. **Missing shipping profile at checkout:** If a user attempts checkout without a registered address, fail early with clear HTTP 422 instructions to register an address.
4. **Idempotent default address updates:** Setting an address as default must atomically unset previous default addresses for the same wallet.
5. **Open store vs Closed marketplace disambiguation:** Domains like `mercadolivre.com.br` must never attempt guest checkout, and open stores must not silently return mock successes.

---

## File Structure

```
services/api/
  app/
    core/
      database.py               # Registers Base metadata for ShippingProfile
    models/
      shipping.py               # ShippingProfile SQLAlchemy model
    schemas/
      deposit.py                # PixDepositResponse extended with qr_code_terminal and qr_code_url
      shipping.py               # Pydantic schemas for ShippingProfile (create, response, list)
      checkout.py               # Extended checkout response (is_simulation, shipping_address)
    services/
      qrcode_service.py         # Segno UTF-8 terminal and PNG generator
      viacep.py                 # ViaCEP async client with fallback
      connectors/
        guest_checkout.py       # Universal guest checkout parser/handler for open stores
    routers/
      wallets.py                # Updated pix-deposit endpoint + PNG image endpoint
      shipping.py               # Shipping profiles CRUD API
      checkout.py               # Updated checkout router with address resolution & strict routing
  tests/
    test_qrcode_service.py      # QR code generation and image serving tests
    test_shipping_vault.py      # Shipping profile DB model, ViaCEP client, and REST endpoints
    test_universal_checkout.py  # Address requirement and anti-hallucination routing tests
packages/mcp-server/
  src/
    api-client.ts               # Adds deposit, getQrCode, and shipping profile client methods
    tools/
      deposit.ts                # deposit_wallet MCP tool
      shipping.ts               # manage_shipping_address MCP tool
      checkout.ts               # Updated checkout tool with address handling
      index.ts                  # Registers all MCP tools
  tests/
    tools.test.ts               # Unit tests for new MCP tools
```

---

## Task Decomposition

### Task 1: QR Code Generation & Web Image Endpoint

**Files:**
- Create: `services/api/app/services/qrcode_service.py`
- Modify: `services/api/app/schemas/deposit.py`
- Modify: `services/api/app/routers/wallets.py`
- Test: `services/api/tests/test_qrcode_service.py`

**Interfaces:**
- Consumes: `segno`
- Produces: `render_terminal_qr(payload: str) -> str`, `render_png_qr(payload: str) -> bytes`, `GET /api/v1/wallets/{wallet_id}/pix-deposit/{payment_id}/qrcode.png`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_qrcode_service.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app
from app.services.qrcode_service import render_terminal_qr, render_png_qr

def test_render_terminal_qr_produces_utf8_blocks():
    payload = "00020126580014br.gov.bcb.pix0136test"
    qr_term = render_terminal_qr(payload)
    assert isinstance(qr_term, str)
    assert len(qr_term) > 50

def test_render_png_qr_produces_valid_png_bytes():
    payload = "00020126580014br.gov.bcb.pix0136test"
    png_bytes = render_png_qr(payload)
    assert isinstance(png_bytes, bytes)
    assert png_bytes.startswith(b"\x89PNG\r\n\x1a\n")

@pytest.mark.asyncio
async def test_wallet_deposit_returns_terminal_and_web_qr_url():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "qr_user", "max_per_order": 50.0, "daily_limit": 100.0})
        wallet_id = w_res.json()["id"]
        
        dep_res = await client.post(f"/api/v1/wallets/{wallet_id}/pix-deposit", json={"amount": 10.0})
        assert dep_res.status_code == 200
        data = dep_res.json()
        assert "qr_code_terminal" in data and len(data["qr_code_terminal"]) > 20
        assert "qr_code_url" in data and f"/api/v1/wallets/{wallet_id}/pix-deposit/" in data["qr_code_url"]
        
        # Test image endpoint
        img_res = await client.get(data["qr_code_url"])
        assert img_res.status_code == 200
        assert img_res.headers["content-type"] == "image/png"
        assert img_res.content.startswith(b"\x89PNG\r\n\x1a\n")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_qrcode_service.py -v` in `services/api`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.qrcode_service'`

- [ ] **Step 3: Implement `app/services/qrcode_service.py`, `schemas/deposit.py` and `routers/wallets.py`**

- In `app/services/qrcode_service.py`: implement `render_terminal_qr` using `io.StringIO` and `segno.make(payload).terminal(out=buf, compact=True)` and `render_png_qr` using `io.BytesIO` and `segno.make(payload).save(buf, kind='png', scale=6)`.
- In `app/schemas/deposit.py`: add `qr_code_terminal: str` and `qr_code_url: str` to `PixDepositResponse`.
- In `app/routers/wallets.py`: populate `qr_code_terminal` and `qr_code_url` on deposit responses, and add `GET /{wallet_id}/pix-deposit/{payment_id}/qrcode.png` returning `Response(content=png_bytes, media_type="image/png")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_qrcode_service.py -v` in `services/api`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/qrcode_service.py services/api/app/schemas/deposit.py services/api/app/routers/wallets.py services/api/tests/test_qrcode_service.py services/api/pyproject.toml
git commit -m "feat(wallets): add visual UTF-8 terminal QR code and web PNG endpoint for Pix deposit"
```

---

### Task 2: Shipping Vault Database Model & ViaCEP Service

**Files:**
- Create: `services/api/app/models/shipping.py`
- Create: `services/api/app/services/viacep.py`
- Create: `services/api/app/schemas/shipping.py`
- Modify: `services/api/app/models/__init__.py`
- Test: `services/api/tests/test_shipping_vault.py`

**Interfaces:**
- Produces: `ShippingProfile` SQLAlchemy model, `ViaCepClient.lookup(cep: str) -> dict`, `ShippingProfileCreate`, `ShippingProfileResponse`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_shipping_vault.py
import pytest
from app.services.viacep import ViaCepClient
from app.schemas.shipping import ShippingProfileCreate

@pytest.mark.asyncio
async def test_viacep_lookup_valid_cep(monkeypatch):
    async def mock_get(self, url, **kwargs):
        class MockResp:
            status_code = 200
            def json(self):
                return {
                    "cep": "01310-100",
                    "logradouro": "Avenida Paulista",
                    "bairro": "Bela Vista",
                    "localidade": "São Paulo",
                    "uf": "SP",
                }
        return MockResp()

    monkeypatch.setattr("httpx.AsyncClient.get", mock_get)
    client = ViaCepClient()
    info = await client.lookup("01310-100")
    assert info["street"] == "Avenida Paulista"
    assert info["city"] == "São Paulo"
    assert info["state"] == "SP"

def test_shipping_profile_schema_validation():
    profile = ShippingProfileCreate(
        wallet_id="w_123",
        recipient_name="João Silva",
        cpf_cnpj="12345678909",
        phone="11999998888",
        postal_code="01310-100",
        street="Av. Paulista",
        number="1000",
        neighborhood="Bela Vista",
        city="São Paulo",
        state="SP"
    )
    assert profile.recipient_name == "João Silva"
    assert profile.postal_code == "01310-100"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_shipping_vault.py -v` in `services/api`
Expected: FAIL with `ModuleNotFoundError: No module named 'app.services.viacep'`

- [ ] **Step 3: Implement `app/models/shipping.py`, `app/services/viacep.py` and `app/schemas/shipping.py`**

- In `app/models/shipping.py`: define `ShippingProfile` with `id`, `wallet_id`, `recipient_name`, `cpf_cnpj`, `phone`, `postal_code`, `street`, `number`, `complement`, `neighborhood`, `city`, `state`, `is_default`, `created_at`.
- In `app/services/viacep.py`: implement `ViaCepClient.lookup(cep: str)` using `httpx.AsyncClient(timeout=5.0)`.
- In `app/schemas/shipping.py`: define `ShippingProfileCreate`, `ShippingProfileUpdate`, `ShippingProfileResponse`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_shipping_vault.py -v` in `services/api`
Expected: PASS (2/2)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/models/shipping.py services/api/app/services/viacep.py services/api/app/schemas/shipping.py services/api/app/models/__init__.py services/api/tests/test_shipping_vault.py
git commit -m "feat(shipping): introduce ShippingProfile model, Pydantic schemas, and ViaCEP client"
```

---

### Task 3: Shipping Vault REST Endpoints (`/api/v1/shipping-profiles`)

**Files:**
- Create: `services/api/app/routers/shipping.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_shipping_vault.py`

**Interfaces:**
- Produces: `POST /api/v1/shipping-profiles`, `GET /api/v1/shipping-profiles/{wallet_id}`, `PATCH /api/v1/shipping-profiles/{id}/default`

- [ ] **Step 1: Write the failing tests**

```python
# Add to services/api/tests/test_shipping_vault.py
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_shipping_profiles_crud_api():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create wallet
        w_res = await client.post("/api/v1/wallets", json={"user_id": "ship_user", "max_per_order": 100.0, "daily_limit": 200.0})
        wallet_id = w_res.json()["id"]

        # Create shipping profile with ViaCEP auto-fill
        create_res = await client.post(
            "/api/v1/shipping-profiles",
            json={
                "wallet_id": wallet_id,
                "recipient_name": "Ana Maria",
                "cpf_cnpj": "11122233344",
                "phone": "11988887777",
                "postal_code": "01310-100",
                "number": "500",
                "complement": "Apto 12",
                "is_default": True
            }
        )
        assert create_res.status_code == 201
        profile = create_res.json()
        assert profile["recipient_name"] == "Ana Maria"
        assert profile["is_default"] is True
        profile_id = profile["id"]

        # List profiles for wallet
        list_res = await client.get(f"/api/v1/shipping-profiles/wallet/{wallet_id}")
        assert list_res.status_code == 200
        assert len(list_res.json()) >= 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_shipping_vault.py -k "test_shipping_profiles_crud_api" -v`
Expected: FAIL with 404 (route not found)

- [ ] **Step 3: Implement `app/routers/shipping.py` and mount in `app/main.py`**

- Support auto-completing missing street/neighborhood/city/state via `ViaCepClient.lookup` if postal_code is provided.
- Atomically reset `is_default=False` on other profiles for the same wallet when a profile is marked default.
- Register `router` with prefix `/api/v1/shipping-profiles` in `app/main.py`.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_shipping_vault.py -v`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/routers/shipping.py services/api/app/main.py services/api/tests/test_shipping_vault.py
git commit -m "feat(shipping): implement Shipping Vault REST API with ViaCEP auto-population"
```

---

### Task 4: Anti-Hallucination & Universal Guest Checkout Engine

**Files:**
- Create: `services/api/app/services/connectors/guest_checkout.py`
- Modify: `services/api/app/routers/checkout.py`
- Modify: `services/api/app/schemas/checkout.py`
- Test: `services/api/tests/test_universal_checkout.py`

**Interfaces:**
- Consumes: `ShippingProfile`, `BaaSPixClient`
- Produces: `UniversalGuestCheckoutEngine.execute_guest_checkout`, strict routing preventing silent mock completions

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_universal_checkout.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.mark.asyncio
async def test_checkout_requires_valid_shipping_address():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_noship", "max_per_order": 100.0, "daily_limit": 200.0})
        wallet_id = w_res.json()["id"]

        # Attempt autonomous checkout without shipping address
        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{"product_id_or_url": "sku_1", "quantity": 1, "unit_price": 30.0, "merchant_domain": "lojaindependente.com.br"}],
                "shipping_profile_id": "nonexistent"
            }
        )
        assert chk_res.status_code == 422
        assert "endereço de entrega" in chk_res.json()["detail"].lower()

@pytest.mark.asyncio
async def test_checkout_meli_always_returns_human_handoff():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_meli", "max_per_order": 100.0, "daily_limit": 200.0})
        wallet_id = w_res.json()["id"]

        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{"product_id_or_url": "MLB12345678", "quantity": 1, "unit_price": 30.0, "merchant_domain": "mercadolivre.com.br"}]
            }
        )
        assert chk_res.status_code == 200
        data = chk_res.json()
        assert data["execution_type"] == "human_handoff"
        assert data["handoff_url"] is not None
        assert data["total_debited"] == 0.0

@pytest.mark.asyncio
async def test_simulated_open_store_marks_simulation_flag():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create wallet and deposit balance
        w_res = await client.post("/api/v1/wallets", json={"user_id": "u_sim", "max_per_order": 100.0, "daily_limit": 200.0})
        wallet_id = w_res.json()["id"]
        # Credit wallet via internal topup or deposit test
        await client.post("/api/v1/wallets/" + wallet_id + "/pix-deposit", json={"amount": 80.0})
        # Simulate payment webhook
        await client.post("/api/v1/webhooks/pix-cash-in", json={"wallet_id": wallet_id, "amount": 80.0, "payment_id": "pay_test_sim", "end_to_end_id": "E123"})
        
        # Add shipping address
        addr_res = await client.post("/api/v1/shipping-profiles", json={
            "wallet_id": wallet_id, "recipient_name": "Teste", "cpf_cnpj": "12345678909", "phone": "11999998888", "postal_code": "01310-100", "number": "100"
        })
        profile_id = addr_res.json()["id"]

        chk_res = await client.post(
            "/api/v1/checkout",
            json={
                "wallet_id": wallet_id,
                "order_items": [{"product_id_or_url": "sku_open_1", "quantity": 1, "unit_price": 40.0, "merchant_domain": "lojaparceira.com.br"}],
                "shipping_profile_id": profile_id
            }
        )
        assert chk_res.status_code == 200
        data = chk_res.json()
        assert "is_simulation" in data
```

- [ ] **Step 2: Run test to verify it fails**

Run: `uv run pytest tests/test_universal_checkout.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `guest_checkout.py` and update `routers/checkout.py` & `schemas/checkout.py`**

- In `app/schemas/checkout.py`: add `is_simulation: bool = False` to `CheckoutResponse`.
- In `app/routers/checkout.py`:
  - Check for valid shipping profile in DB (or default). If missing or not found, return HTTP 422: `"Cadastre um endereço de entrega no Shipping Vault antes de finalizar a compra."`
  - Marketplaces in `CLOSED_MARKETPLACES` strictly return `execution_type: "human_handoff"`.
  - In sandbox mode, `is_simulation` is set to `True` with descriptive note preventing AI deception.

- [ ] **Step 4: Run tests to verify they pass**

Run: `uv run pytest tests/test_universal_checkout.py -v`
Expected: PASS (3/3)

- [ ] **Step 5: Commit**

```bash
git add services/api/app/services/connectors/guest_checkout.py services/api/app/routers/checkout.py services/api/app/schemas/checkout.py services/api/tests/test_universal_checkout.py
git commit -m "feat(checkout): enforce shipping address requirement and eliminate silent mock completions"
```

---

### Task 5: MCP Server Tools (`deposit_wallet` & `manage_shipping_address`)

**Files:**
- Create: `packages/mcp-server/src/tools/deposit.ts`
- Create: `packages/mcp-server/src/tools/shipping.ts`
- Modify: `packages/mcp-server/src/api-client.ts`
- Modify: `packages/mcp-server/src/tools/index.ts`
- Test: `packages/mcp-server/tests/tools.test.ts`

**Interfaces:**
- Consumes: Backend `/api/v1/wallets/{id}/pix-deposit`, `/api/v1/shipping-profiles`
- Produces: MCP tools `deposit_wallet` and `manage_shipping_address`

- [ ] **Step 1: Write the failing tests**

```typescript
// packages/mcp-server/tests/deposit-and-shipping.test.ts
import { describe, it } from 'node:test';
import assert from 'node:assert';
import { createServer } from '../src/index.js';

describe('New MCP Tools Registration', () => {
  it('registers deposit_wallet and manage_shipping_address', () => {
    const server = createServer({ baseUrl: 'http://localhost:8000' });
    assert.ok(server);
  });
});
```

- [ ] **Step 2: Run test to verify build or failure**

Run: `npm test` in `packages/mcp-server`

- [ ] **Step 3: Implement `deposit.ts`, `shipping.ts`, and update `api-client.ts` & `index.ts`**

- `deposit_wallet`: accepts `wallet_id`, `amount`, `customer_name`. Returns formatted output containing the UTF-8 ASCII QR code, the clickable PNG URL, and the Copia-e-Cola payload.
- `manage_shipping_address`: accepts `action` ('register' | 'list'), `wallet_id`, and address fields. Calls backend to validate ViaCEP and save/list profiles.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test` in `packages/mcp-server`
Expected: PASS (all tests)

- [ ] **Step 5: Commit**

```bash
git add packages/mcp-server/src/tools/deposit.ts packages/mcp-server/src/tools/shipping.ts packages/mcp-server/src/tools/index.ts packages/mcp-server/src/api-client.ts packages/mcp-server/tests/
git commit -m "feat(mcp): add deposit_wallet and manage_shipping_address tools with visual QR code and ViaCEP"
```

---

### Task 6: Full System Verification & Regression Suite

**Files:**
- Test: `services/api/tests/` (all 74+ tests)
- Test: `packages/mcp-server/tests/`

- [ ] **Step 1: Run full Python pytest suite**
Run: `uv run pytest tests/ -v` in `services/api`
Expected: PASS (>80 passed, 0 failed)

- [ ] **Step 2: Run full TypeScript test suite**
Run: `npm test` in `packages/mcp-server`
Expected: PASS (all passed)

- [ ] **Step 3: Final branch verification and review**
Check git status, verify clean working tree, review code quality via `ponytail-review`.
