# Playwright Headless Checkout Worker Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement an autonomous guest checkout worker using Playwright that fills delivery forms on open e-commerce stores (Nuvemshop, Shopify, WooCommerce, generic storefronts), selects Pix, extracts the store's real payment payload, and triggers instant BaaS Pix liquidation via Asaas.

**Architecture:** 
1. `BrowserManager`: Manages async Chromium lifecycle, anti-detection headers, and timeouts without memory leaks or event-loop blocking.
2. `PlatformStrategies`: Modular strategy pattern (`NuvemshopStrategy`, `ShopifyStrategy`, `GenericStrategy`) navigating guest checkout, populating `ShippingProfile` fields (Name, CPF, CEP, address, phone), and selecting Pix.
3. `PixExtractor`: Robust extraction of the Brazilian Central Bank EMV QRCPS-MPM payload (`00020126...`) from DOM elements, text, or copy-paste inputs.
4. `UniversalGuestCheckoutEngine`: Bridges `checkout.py` and the worker; receives the extracted Pix code, debits the user's wallet, and executes `BaaSPixClient.send_pix_payout` directly to the merchant's gateway.

**Tech Stack:** Python 3.11+, Playwright (`async_playwright`), FastAPI, SQLAlchemy 2.0, Pydantic v2, Asaas BaaS REST API.

**Spec:** Defined in [agent-commerce-protocol.md](file:///C:/Users/elast/ACP-MCP/docs/ideas/agent-commerce-protocol.md) and user interview directives.

---

## Global Constraints

- Never commit secrets (`ASAAS_API_KEY`, etc.) or untracked `AGENTS.md`.
- Closed marketplaces (`mercadolivre.com.br`, `shopee.com.br`) must NEVER run Playwright (strictly routed to 1-click human handoff).
- Zero-cost sandbox fallback: unit tests must mock Playwright pages/browsers to run fast (<1s) and hermetically without launching real browsers in CI.
- All errors must capture visual diagnostics (screenshot saved to `scratch/checkout_failures/`) for transparent error recovery.
- Keep 100% of existing 83 Python and 7 TypeScript tests green.

## Review Focus

1. **Form input heuristics:** Field names vary across platforms (`name="nome"`, `id="billing_cpf"`, `input[type="tel"]`). Heuristics must fall back across multiple selectors before failing.
2. **Dynamic SPA / React checkout hydration:** Checkout forms load asynchronously; worker must use `wait_for_selector` with realistic timeouts (up to 15s) instead of fixed sleeps.
3. **Pix payload regex extraction:** Some gateways present Pix in `<textarea>`, others in `<code>`, or as a button `data-clipboard-text`. `PixExtractor` must check all three.
4. **Failure isolation:** A crashed or timed-out browser session must be killed cleanly and not leave zombie Chromium processes.
5. **Wallet debit atomicity:** The wallet is only debited AFTER the Pix payload is successfully extracted and verified from the store page.

---

## File Structure

```
services/api/
  app/
    core/
      config.py                                    # Add PLAYWRIGHT_HEADLESS, PLAYWRIGHT_TIMEOUT
    services/
      checkout_worker/
        __init__.py
        browser_manager.py                         # Playwright async context manager & lifecycle
        pix_extractor.py                           # EMV QR Code & Copia-e-Cola payload extractor
        strategies/
          __init__.py
          base.py                                  # BaseCheckoutStrategy interface
          generic.py                               # Generic form-filling heuristic strategy
          nuvemshop.py                             # Nuvemshop/Tiendanube specialized strategy
          shopify.py                               # Shopify guest checkout strategy
        orchestrator.py                            # PlaywrightCheckoutWorker orchestrator
      connectors/
        guest_checkout.py                          # Connects orchestrator to ACP checkout flow
    routers/
      checkout.py                                  # Routes open stores to guest checkout worker
  tests/
    test_playwright_browser_manager.py             # Browser lifecycle & timeout tests
    test_checkout_strategies.py                    # Form filling & Pix extraction tests with mock HTML
    test_playwright_checkout_worker.py             # E2E worker execution with local ASGI mock store
```

---

## Task Decomposition

### Task 1: Playwright Installation, Settings & BrowserManager

**Files:**
- Modify: `services/api/pyproject.toml`
- Modify: `services/api/app/core/config.py`
- Create: `services/api/app/services/checkout_worker/browser_manager.py`
- Test: `services/api/tests/test_playwright_browser_manager.py`

**Interfaces:**
- Produces: `BrowserManager.create_context() -> BrowserContext`, `BrowserManager.close()`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_playwright_browser_manager.py
import pytest
from app.services.checkout_worker.browser_manager import BrowserManager

@pytest.mark.asyncio
async def test_browser_manager_lifecycle(monkeypatch):
    manager = BrowserManager()
    assert manager is not None
    # Verify default user agent and settings
    assert manager.timeout_seconds > 0
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_playwright_browser_manager.py -v`
Expected: FAIL with `ModuleNotFoundError`

- [ ] **Step 3: Implement `pyproject.toml`, `config.py` and `browser_manager.py`**
Add `playwright>=1.49.0` to dependencies.
Implement `BrowserManager` with singleton browser reuse, realistic viewport, Brazilian Portuguese locale (`pt-BR`), and cleanup methods.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_playwright_browser_manager.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/pyproject.toml services/api/app/core/config.py services/api/app/services/checkout_worker/browser_manager.py services/api/tests/test_playwright_browser_manager.py
git commit -m "feat(worker): add Playwright configuration and BrowserManager lifecycle"
```

---

### Task 2: Pix Payload Extractor & Checkout Form Strategies

**Files:**
- Create: `services/api/app/services/checkout_worker/pix_extractor.py`
- Create: `services/api/app/services/checkout_worker/strategies/base.py`
- Create: `services/api/app/services/checkout_worker/strategies/generic.py`
- Create: `services/api/app/services/checkout_worker/strategies/nuvemshop.py`
- Test: `services/api/tests/test_checkout_strategies.py`

**Interfaces:**
- Produces: `PixExtractor.extract_payload(text_or_html: str) -> str | None`
- Produces: `BaseCheckoutStrategy.fill_shipping(page, profile)`, `BaseCheckoutStrategy.select_pix_and_submit(page) -> str`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_checkout_strategies.py
import pytest
from app.services.checkout_worker.pix_extractor import PixExtractor

def test_pix_extractor_extracts_emv_payload():
    html_sample = """
    <div>
      <textarea id="pix-code">00020126580014br.gov.bcb.pix0136123e4567-e89b-12d3-a456-42661417400052040000530398654010.005802BR5913Loja Exemplo6009SAO PAULO62070503***6304ABCD</textarea>
    </div>
    """
    code = PixExtractor.extract_payload(html_sample)
    assert code is not None
    assert code.startswith("00020126580014br.gov.bcb.pix")
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_checkout_strategies.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `pix_extractor.py`, `base.py`, `generic.py`, `nuvemshop.py`**
Implement regex `00020126[0-9a-zA-Z\.\-\_\@\s]{30,}` matching standard Banco Central Pix strings.
Implement fallback field selectors for Name (`name*=nome`, `name*=name`), CPF (`name*=cpf`), CEP (`name*=cep`), Street (`name*=rua`, `name*=street`), Number (`name*=numero`, `name*=number`), Phone (`name*=tel`, `name*=phone`).

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_checkout_strategies.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/checkout_worker/pix_extractor.py services/api/app/services/checkout_worker/strategies/ services/api/tests/test_checkout_strategies.py
git commit -m "feat(worker): implement PixExtractor and form-filling strategies for Nuvemshop and generic stores"
```

---

### Task 3: Playwright Checkout Worker Orchestrator with Failure Diagnostics

**Files:**
- Create: `services/api/app/services/checkout_worker/orchestrator.py`
- Test: `services/api/tests/test_playwright_checkout_worker.py`

**Interfaces:**
- Produces: `PlaywrightCheckoutWorker.execute(url: str, quantity: int, profile: ShippingProfile) -> WorkerResult`

- [ ] **Step 1: Write the failing tests**

```python
# services/api/tests/test_playwright_checkout_worker.py
import pytest
from app.services.checkout_worker.orchestrator import PlaywrightCheckoutWorker

@pytest.mark.asyncio
async def test_worker_captures_failure_screenshot(monkeypatch):
    worker = PlaywrightCheckoutWorker()
    assert worker is not None
```

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_playwright_checkout_worker.py -v`
Expected: FAIL

- [ ] **Step 3: Implement `orchestrator.py`**
Orchestrates:
1. Navigation to product URL.
2. Clicks "Comprar" or selects strategy.
3. Fills shipping profile fields.
4. Selects Pix payment method and clicks submit.
5. Captures Pix payload via `PixExtractor`.
6. On error: captures screenshot into `scratch/checkout_failures/` and raises descriptive exception.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_playwright_checkout_worker.py -v`
Expected: PASS

- [ ] **Step 5: Commit**
```bash
git add services/api/app/services/checkout_worker/orchestrator.py services/api/tests/test_playwright_checkout_worker.py
git commit -m "feat(worker): implement PlaywrightCheckoutWorker orchestrator with failure screenshots"
```

---

### Task 4: Pluggable Integration into Universal Guest Checkout & BaaS Payout

**Files:**
- Modify: `services/api/app/services/connectors/guest_checkout.py`
- Modify: `services/api/app/routers/checkout.py`
- Test: `services/api/tests/test_universal_checkout.py`

**Interfaces:**
- Connects: `PlaywrightCheckoutWorker` output (store Pix payload) directly to `BaaSPixClient.send_pix_payout`.

- [ ] **Step 1: Write integration tests verifying real worker payout delegation**
- [ ] **Step 2: Wire `UniversalGuestCheckoutEngine` to invoke `PlaywrightCheckoutWorker` when `headless_checkout_enabled` is active**
- [ ] **Step 3: Dispatches Asaas Pix payout for the captured store Pix payload**
- [ ] **Step 4: Verify test passes and commit**
```bash
git add services/api/app/services/connectors/guest_checkout.py services/api/app/routers/checkout.py services/api/tests/test_universal_checkout.py
git commit -m "feat(checkout): wire Playwright checkout worker to live Asaas Pix payout"
```

---

### Task 5: Full Regression & System Verification

- Run `uv run pytest tests/ -v` (expect 87+ passed).
- Run `npm test` in `packages/mcp-server` (expect 7/7 passed).
- Ponytail Review & push to `origin/main`.
