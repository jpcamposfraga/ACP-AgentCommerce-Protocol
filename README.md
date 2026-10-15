# AgentCommerce Protocol (ACP)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![MCP Compatible](https://img.shields.io/badge/MCP-Compatible-blue.svg)](https://modelcontextprotocol.io)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg?logo=fastapi)](https://fastapi.tiangolo.com)
[![TypeScript](https://img.shields.io/badge/TypeScript-5.7+-3178C6.svg?logo=typescript)](https://www.typescriptlang.org)

**The commerce, execution, and wallet layer for autonomous AI agents.**  
*O protocolo aberto de comércio e pagamentos com travas de segurança para agentes de inteligência artificial.*

---

## ⚡ What is ACP? / O que é o ACP?

Most e-commerce websites today are built strictly for humans, with Captchas, 2FA prompts, and anti-bot systems that block autonomous AI agents. Furthermore, giving agents an unrestricted credit card poses massive hallucination risks.

**ACP (AgentCommerce Protocol)** is an open-source protocol and Model Context Protocol (MCP) server that provides agents with:
1. **Hybrid Execution Routing:** High-speed autonomous execution on verified partner stores + 1-click human approval magic links for closed marketplaces (Mercado Livre, Shopee).
2. **Autonomous Wallet Guard:** Pre-paid balance with mathematical spend caps per order, daily limits, and slippage controls to prevent runaway loops.
3. **Best Payment Price Engine:** Automatically selects and executes cash discount options (such as Pix with 10% discount in Brazil) over standard card installment pricing.
4. **Verified Merchant Shield:** Domain validation and digital signatures (`/.well-known/agent-commerce.json`) protecting agents from malicious "honeypot" storefronts.

---

## 🏗️ Repository Architecture / Arquitetura do Repositório

```text
ACP-AgentCommerce-Protocol/
├── docs/                     # Specifications, 4-week roadmap & scalability plans
│   ├── ideas/                # Core architecture & design specs
│   └── plans/                # MVP 4-week implementation plan
├── infra/                    # Deployment & orchestration
│   ├── docker-compose.yml    # PostgreSQL 16 + Redis 7 + FastAPI
│   ├── Dockerfile            # Optimized backend container
│   └── .env.example          # Environment variables template
├── packages/
│   └── mcp-server/           # TypeScript Model Context Protocol (MCP) server
│       ├── src/              # MCP Tools (search, track, status, checkout)
│       └── package.json      # Published to npm as @agent-commerce/mcp-server
└── services/
    └── api/                  # Python FastAPI Cloud Gateway
        ├── app/              # FastAPI application (models, routers, schemas)
        ├── tests/            # Concurrency & ledger test suites
        └── pyproject.toml    # Python dependencies (managed via uv)
```

---

## 🚀 Quickstart / Como Executar

### 1. Infraestrutura Local (Docker Compose)
Para subir o banco de dados PostgreSQL e o Redis:
```bash
docker compose -f infra/docker-compose.yml up -d postgres redis
```

### 2. Backend API (FastAPI)
Instale as dependências com `uv` e execute:
```bash
cd services/api
uv venv
uv pip install -e ".[dev]"
uv run uvicorn app.main:app --reload --port 8000
```

### 3. Servidor MCP Local (TypeScript)
```bash
cd packages/mcp-server
npm install
npm run build
```

---

## 📄 License
Este projeto é distribuído sob a licença [MIT](LICENSE).
