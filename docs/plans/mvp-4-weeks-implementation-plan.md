# AgentCommerce Protocol (ACP) - Plano de Implementação MVP (4 Semanas)

> **Documento de Execução:** Este plano define o cronograma de 4 semanas para construção e validação do MVP do ACP. Cada semana possui entregáveis técnicos atômicos e um **GOAL verificável** (Definition of Done) que comprova a conclusão daquela etapa antes de avançar para a próxima.

**Tempo Total:** 4 semanas (Prazo Máximo)  
**Stack Técnica:** TypeScript/Node.js (Local MCP Server), Python/FastAPI (Backend Gateway), PostgreSQL (ACID Wallet Ledger), Redis (Filas & Cache), TypeSafe AI Jev (Fast Classifier), BaaS Asaas/Efí (Pix Sandbox).  
**Documento de Especificação Base:** [agent-commerce-protocol.md](file:///C:/Users/elast/docs/ideas/agent-commerce-protocol.md)

---

## Semana 1: Fundação Backend, Docker na KVM & Ledger da Wallet

### Escopo e Entregáveis:
- [ ] **Configuração do Ambiente:** Criar repositório e `docker-compose.yml` para rodar na VPS KVM com:
  - `acp-api`: FastAPI rodando com Python 3.12+ e Uvicorn.
  - `acp-postgres`: PostgreSQL 16 com volume persistente e script básico de backup.
  - `acp-redis`: Redis 7 para cache e filas.
- [ ] **Modelagem de Dados (SQLAlchemy / Alembic):**
  - Tabelas: `users`, `wallets`, `transactions`, `merchants`, `orders`.
  - Campo de constraints de segurança: `max_per_order`, `daily_limit`, `balance`.
- [ ] **Módulo da Wallet & Travas de Segurança (FastAPI):**
  - Endpoint de recarga de saldo (sandbox simulando recebimento de Pix).
  - Máquina de débito com lock transacional (`SELECT ... FOR UPDATE` no Postgres) para garantir concorrência segura contra duplo gasto.
  - Cálculo e retenção da taxa de intermediação (1,5% a 2%) no momento do débito.

### 🎯 GOAL da Semana 1 (Critério de Conclusão):
> **Teste de Concorrência & Integridade Financeira Aprovado:**
> Um script de teste automatizado dispara **10 requisições simultâneas de débito de R$ 100,00** contra uma carteira configurada com **R$ 500,00 de saldo**. O sistema processa com exatidão matemática 5 transações com sucesso, retém a taxa de 2% (R$ 10,00 acumulados), rejeita as outras 5 por saldo insuficiente com código HTTP 402/422, e encerra com saldo final de R$ 0,00 sem nenhuma corrida de dados (*race condition*).

---

## Semana 2: Motor de Busca, Parser Rápido com Jev & Scraper Leve

### Escopo e Entregáveis:
- [ ] **Scraper HTTP de Leitura:**
  - Cliente HTTP assíncrono com `curl_cffi` para simulação de TLS de navegadores reais (evitando bloqueios simples de WAF).
  - Parser ultrarrápido com `selectolax` para extrair listagens de produtos no Mercado Livre.
- [ ] **Camada de Decisão Rápida (TypeSafe AI - Jev):**
  - Integração do SDK/API do Jev para classificar em < 200ms se a página é um anúncio real, identificar se o vendedor possui boa reputação e checar disponibilidade de estoque.
- [ ] **Best Payment Price Engine:**
  - Extração e comparação do preço em cartão vs. desconto à vista no Pix.
  - Cálculo do Menor Preço Efetivo adicionando o take-rate de 1,5% da plataforma.
- [ ] **Endpoints de Catálogo & Reputação:**
  - `POST /api/v1/search`: Busca normalizada com filtros de preço e quantidade mínima.
  - `GET /api/v1/merchant/status`: Verificação de domínio na allowlist de comerciantes seguros.

### 🎯 GOAL da Semana 2 (Critério de Conclusão):
> **Busca Rápida de Menor Preço Efetivo com Zero Tokens LLM:**
> Uma chamada `POST /api/v1/search` com o termo *"iPhone 15 128GB"* retorna em menos de **1,5 segundo** uma lista normalizada com pelo menos 5 ofertas reais do Mercado Livre. O JSON identifica com exatidão o desconto de Pix à vista (ex: R$ 4.769,10 vs. R$ 5.299,00 no cartão), o preço final já computado com a taxa de 1,5% do ACP e o score de confiabilidade do vendedor, sem ter consumido nenhum token de LLMs tradicionais caros no processo de extração.

---

## Semana 3: Orquestração de Checkout (Híbrido vs. Autônomo) & Webhook BaaS

### Escopo e Entregáveis:
- [ ] **Conector de Loja Aberta (Mock / Shopify Dev Store):**
  - Implementação do endpoint de compra autônoma: consome a Storefront API da loja, gera o pedido, debita a carteira e emite recibo instantâneo.
- [ ] **Motor de Checkout Híbrido (Mercado Livre):**
  - Gerador de link de carrinho/checkout montado e higienizado com os SKUs e quantidades solicitadas para aprovação com 1 clique humano.
- [ ] **Integração de Sandbox do BaaS (Asaas ou Efí):**
  - Webhook de notificação de Pix recebido (para recargas automáticas de carteira).
  - Ordem de envio de Pix de teste da conta da plataforma para a conta da loja no fluxo autônomo.
- [ ] **Endpoint `POST /api/v1/checkout`:**
  - Roteamento inteligente: se a loja for fechada (Meli/Shopee), retorna payload com link humano; se for parceira verificada, executa pagamento autônomo da carteira.

### 🎯 GOAL da Semana 3 (Critério de Conclusão):
> **Execução Ponta a Ponta dos Dois Modos de Compra:**
> 1. **Modo Autônomo:** Uma requisição de checkout para uma loja parceira simula com sucesso o débito de R$ 500,00 da carteira, a retenção de R$ 10,00 (2%) na conta da plataforma e a emissão do Pix de R$ 500,00 no sandbox bancário, retornando status `completed` com recibo em menos de 3 segundos.
> 2. **Modo Híbrido:** Uma requisição de checkout para o Mercado Livre identifica o ecossistema fechado e retorna status `pending_human_approval` com uma URL válida que abre o carrinho pré-configurado no navegador.

---

## Semana 4: Servidor MCP Local & Teste de Tração com Agente Real (CrewAI / Claude)

### Escopo e Entregáveis:
- [ ] **Desenvolvimento do Local MCP Server (TypeScript / Node.js):**
  - Pacote CLI/MCP com `@modelcontextprotocol/sdk`.
  - Exposição das 4 ferramentas oficiais via protocolo `stdio`:
    1. `search_products`
    2. `track_price_and_stock`
    3. `get_merchant_status`
    4. `checkout`
- [ ] **Worker de Rastreamento com Redis (Celery / ARQ):**
  - Agendador de monitoramento de preços 24/7.
  - Trava de intervalo mínimo (60 segundos) e warning automático no retorno da tool caso o usuário configure frequências que causem alto consumo.
- [ ] **Validação com Framework de Agentes (CrewAI / Claude Desktop / Cursor):**
  - Criar um script de exemplo com um agente autônomo conectado ao servidor MCP via `stdio`.

### 🎯 GOAL da Semana 4 (GOAL FINAL DO MVP):
> **Missão Completa do Agente Autônomo em Produção Local:**
> Um agente autônomo configurado no **CrewAI** ou no **Claude Desktop** recebe o seguinte objetivo em linguagem natural:
> *"Pesquise o iPhone 15, verifique se há estoque para 2 unidades e, se o preço à vista no Pix estiver abaixo de R$ 5.000,00 cada, compre usando o meu saldo pré-pago na loja parceira; caso encontre apenas no Mercado Livre, me entregue o link do carrinho pronto."*
> 
> O agente:
> 1. Invoca `search_products` via MCP.
> 2. Analisa as opções e seleciona o melhor preço com desconto do Pix.
> 3. Invoca `checkout` via MCP.
> 4. O backend valida a carteira, debita o saldo com taxa retida e retorna o comprovante estruturado.
> 5. O agente finaliza a execução e reporta o sucesso ao usuário com tempo total inferior a 15 segundos.

---

## Resumo das Entregas Semanais

| Semana | Foco Principal | GOAL de Conclusão |
| :--- | :--- | :--- |
| **Semana 1** | Infra KVM, Docker & Wallet Segura | Teste de concorrência com 10 débitos simultâneos sem race conditions. |
| **Semana 2** | Busca, Jev Classifier & Desconto Pix | Busca estruturada em < 1.5s com decomposição de preço Pix e zero LLM tokens. |
| **Semana 3** | Checkout Autônomo vs. Híbrido & Pix BaaS | Compra autônoma liquidada no BaaS e geração de link no Meli. |
| **Semana 4** | Servidor MCP Local & Agente Autônomo | Agente CrewAI/Claude executa pesquisa e checkout de ponta a ponta via MCP. |
