# Semana 4: Servidor MCP Local & Validação com Agente Autônomo

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implementar o servidor oficial Model Context Protocol (MCP) em TypeScript (`packages/mcp-server`) expondo as 4 tools via stdio (`search_products`, `track_price_and_stock`, `get_merchant_status`, `checkout`), adicionar a engine de trackers de preço no backend, e validar a missão autônoma ponta a ponta com agente de IA em menos de 15 segundos.

**Architecture:** O monorepo conecta o ecossistema de agentes (Claude Desktop, Cursor, CrewAI) ao backend do ACP via transporte `stdio` do MCP SDK. A camada TypeScript consome a API REST do ACP (`http://localhost:8000`), convertendo esquemas Zod em chamadas HTTP assíncronas com validação estrita. O backend adiciona a API de rastreadores com trava de intervalo mínimo (60s) e um script/teste de agente orquestra a missão completa (pesquisa de produto, análise de desconto Pix e checkout com roteamento autônomo vs. híbrido).

**Tech Stack:** TypeScript 5.7+, Node.js 24+, `@modelcontextprotocol/sdk`, Zod, Python 3.14+, FastAPI, SQLAlchemy, HTTPX, Pytest.

**Spec:** [docs/plans/mvp-4-weeks-implementation-plan.md](file:///C:/Users/elast/ACP-MCP/docs/plans/mvp-4-weeks-implementation-plan.md) e [docs/ideas/agent-commerce-protocol.md](file:///C:/Users/elast/ACP-MCP/docs/ideas/agent-commerce-protocol.md)

## Global Constraints
- **Protocolo MCP Oficial:** O servidor em TypeScript deve utilizar `@modelcontextprotocol/sdk` e comunicar via `StdioServerTransport`.
- **4 Tools MCP Estritas:** `search_products`, `track_price_and_stock`, `get_merchant_status`, `checkout`.
- **Trava de Intervalo do Tracker:** Frequências inferiores a 60 segundos devem ser automaticamente corrigidas para 60s com aviso explícito no retorno da tool para prevenir rate limiting / banimento.
- **Configuração de Ambiente:** O servidor MCP deve ler `ACP_API_URL` de variáveis de ambiente com fallback para `http://localhost:8000`.
- **Missão E2E em < 15 segundos:** A missão completa do agente (pesquisa + decisão Pix + checkout) deve ser executada com latência total inferior a 15 segundos.

## Review Focus
1. **Falha de conexão MCP -> Backend ACP:** Se a API estiver offline, a tool MCP deve retornar mensagem de erro amigável e estruturada ao LLM, em vez de crashar o processo stdio.
2. **Entrada de Zod inválida no MCP:** Parâmetros com tipos errados ou valores ausentes devem disparar erro de validação claro sem derrubar o transporte JSON-RPC.
3. **Agendamento de tracker abusivo (< 60s):** O endpoint e a tool devem aplicar a trava de segurança sem falhar a requisição, retornando `check_interval_seconds: 60` e um warning descritivo.
4. **Checkout de item fechado via MCP:** Deve retornar o link de carrinho limpo para 1 clique humano com status `pending_human_approval`.
5. **Checkout autônomo via MCP:** Deve debitar a carteira com retenção de taxa e retornar recibo estruturado com `end_to_end_id`.

---

### Task 1: API de Monitoramento & Trackers de Preço no Backend (`POST /api/v1/trackers`)

**Files:**
- Create: `services/api/app/schemas/tracker.py`
- Create: `services/api/app/routers/trackers.py`
- Modify: `services/api/app/main.py`
- Test: `services/api/tests/test_trackers_api.py`

**Interfaces:**
- Produces:
  - `TrackerRequest`: `product_url_or_id: str`, `target_price: float`, `target_payment_method: str`, `min_stock: int`, `check_interval_seconds: int`, `webhook_url: str | None`
  - `TrackerResponse`: `tracker_id: str`, `status: str`, `current_best_price: float`, `check_interval_seconds: int`, `warning: str | None`
  - `POST /api/v1/trackers` -> `TrackerResponse`

- [ ] **Step 1: Write failing test for tracker endpoint with interval lock validation**
Write tests for:
1. Criação de tracker com intervalo >= 60s (retorna status active e preço atual).
2. Criação de tracker com intervalo abusivo (< 60s, ex: 10s) -> ajusta para 60s e injeta warning.

- [ ] **Step 2: Run test to verify it fails**
Run: `uv run pytest tests/test_trackers_api.py`
Expected: FAIL with 404 Not Found.

- [ ] **Step 3: Implement schemas and router in `app/schemas/tracker.py` and `app/routers/trackers.py`**
Implement the router, register in `app/main.py`.

- [ ] **Step 4: Run test to verify it passes**
Run: `uv run pytest tests/test_trackers_api.py`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add services/api/app/schemas/tracker.py services/api/app/routers/trackers.py services/api/app/main.py services/api/tests/test_trackers_api.py
git commit -m "feat(api): implement price tracking endpoint with interval lock"
```

---

### Task 2: Cliente HTTP / API Client do MCP Server em TypeScript

**Files:**
- Create: `packages/mcp-server/src/api-client.ts`
- Test: `packages/mcp-server/tests/api-client.test.ts`

**Interfaces:**
- Produces:
  - `AcpApiClient`:
    - `searchProducts(params: SearchParams): Promise<SearchResponse>`
    - `trackPrice(params: TrackerParams): Promise<TrackerResponse>`
    - `getMerchantStatus(domain: string): Promise<MerchantStatusResponse>`
    - `checkout(params: CheckoutParams): Promise<CheckoutResponse>`

- [ ] **Step 1: Write failing unit tests for `AcpApiClient`**
Write tests using Node's test runner mocking HTTP responses (fetch mock) to verify correct payloads, headers, error handling, and parameter mappings.

- [ ] **Step 2: Run test to verify it fails**
Run: `node --experimental-strip-types --test tests/api-client.test.ts` (in `packages/mcp-server`)
Expected: FAIL (module not found).

- [ ] **Step 3: Implement `AcpApiClient` in `packages/mcp-server/src/api-client.ts`**
Implement typed client using native `fetch` with error catching.

- [ ] **Step 4: Run test to verify it passes**
Run: `node --experimental-strip-types --test tests/api-client.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add packages/mcp-server/src/api-client.ts packages/mcp-server/tests/api-client.test.ts
git commit -m "feat(mcp): implement typed HTTP client for ACP backend"
```

---

### Task 3: Definição e Implementação das 4 MCP Tools com Zod

**Files:**
- Create: `packages/mcp-server/src/tools/search.ts`
- Create: `packages/mcp-server/src/tools/track.ts`
- Create: `packages/mcp-server/src/tools/merchant.ts`
- Create: `packages/mcp-server/src/tools/checkout.ts`
- Test: `packages/mcp-server/tests/tools.test.ts`

**Interfaces:**
- Produces:
  - `registerSearchTool(server: McpServer, client: AcpApiClient)`
  - `registerTrackTool(server: McpServer, client: AcpApiClient)`
  - `registerMerchantTool(server: McpServer, client: AcpApiClient)`
  - `registerCheckoutTool(server: McpServer, client: AcpApiClient)`

- [ ] **Step 1: Write failing tests for tool schemas and handlers**
Write tests verifying that tool input schemas match ACP contracts and tool execution formats responses properly as MCP `content: [{ type: "text", text: ... }]`.

- [ ] **Step 2: Run test to verify it fails**
Run: `node --experimental-strip-types --test tests/tools.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement tool definitions in `packages/mcp-server/src/tools/`**
Implement the 4 tools with Zod schemas and clear markdown descriptions for LLM reasoning.

- [ ] **Step 4: Run test to verify it passes**
Run: `node --experimental-strip-types --test tests/tools.test.ts`
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add packages/mcp-server/src/tools/ packages/mcp-server/tests/tools.test.ts
git commit -m "feat(mcp): register search, track, merchant and checkout tools with zod schemas"
```

---

### Task 4: Servidor MCP Stdio & CLI Executável (`packages/mcp-server/src/index.ts`)

**Files:**
- Create: `packages/mcp-server/src/index.ts`
- Modify: `packages/mcp-server/package.json`
- Test: `packages/mcp-server/tests/server.test.ts`

**Interfaces:**
- Produces:
  - CLI bin: `acp-mcp`
  - Stdio transport initialization connecting all 4 tools.

- [ ] **Step 1: Write failing test verifying server startup and tool listing via MCP client**
Write test connecting an MCP Client to the server via in-memory or stdio transport and verifying `listTools()` returns `search_products`, `track_price_and_stock`, `get_merchant_status`, `checkout`.

- [ ] **Step 2: Run test to verify it fails**
Run: `node --experimental-strip-types --test tests/server.test.ts`
Expected: FAIL.

- [ ] **Step 3: Implement `src/index.ts` and build script**
Wire `McpServer`, register all tools, connect to `StdioServerTransport()`.

- [ ] **Step 4: Run test and build verification**
Run: `npm run build && node --test dist/tests/server.test.js` (or strip-types)
Expected: PASS.

- [ ] **Step 5: Commit**
```bash
git add packages/mcp-server/src/index.ts packages/mcp-server/package.json packages/mcp-server/tests/server.test.ts
git commit -m "feat(mcp): wire StdioServerTransport and build executable CLI server"
```

---

### Task 5: Script de Agente Autônomo & Validação de Missão

**Files:**
- Create: `examples/agent_mission.py`
- Test: `services/api/tests/test_week_4_goal.py`

**Interfaces:**
- Produces:
  - Agent mission simulation runner:
    1. Agente pesquisa iPhone 15 com `prefer_best_cash_price=True`.
    2. Avalia ofertas e detecta desconto Pix.
    3. Executa checkout para loja parceira (autônomo) ou Mercado Livre (híbrido).
    4. Confirma término da missão com tempo total < 15s.

- [ ] **Step 1: Write automated E2E test for Week 4 Goal in `tests/test_week_4_goal.py`**
Validates the full autonomous agent decision lifecycle with real API calls.

- [ ] **Step 2: Run test to verify it passes**
Run: `uv run pytest tests/test_week_4_goal.py -v`
Expected: PASS (< 15s latency).

- [ ] **Step 3: Create executable example script in `examples/agent_mission.py`**
Provide a clean standalone script documenting how CrewAI / Claude Desktop uses the ACP MCP server.

- [ ] **Step 4: Run script to verify execution**
Run: `uv run python examples/agent_mission.py`
Expected: Output showing complete mission flow with JSON receipts.

- [ ] **Step 5: Commit**
```bash
git add services/api/tests/test_week_4_goal.py examples/agent_mission.py
git commit -m "feat: complete Week 4 agent autonomous mission validation"
```

---

### Task 6: Verificação do GOAL Final do MVP & Ponytail Review

- [ ] **Step 1: Run complete test suites**
1. Backend: `uv run pytest -v` (all tests passing)
2. MCP Server: `npm test` in `packages/mcp-server`
3. Monorepo build check.

- [ ] **Step 2: Run Ponytail Review across Week 4 changes**
Verify simplicity, zero code bloat, clean error handling, and security.

- [ ] **Step 3: Commit and Push to remote `main`**
```bash
git push origin main
```
