# AgentCommerce Protocol (ACP)

A camada de execução, segurança e pagamentos para agentes autônomos de compra.

## Problem Statement
> **How might we** permitir que agentes de IA pesquisem, monitorem e comprem produtos em lote com segurança orçamentária e proteção contra fraudes, eliminando a fricção das interfaces humanas sem violar regras anti-bot de grandes plataformas?

## Recommended Direction
Construir uma ferramenta headless e servidor **MCP (*Model Context Protocol*) / REST API** voltada para desenvolvedores de agentes (CrewAI, LangChain, AutoGen). A plataforma se posiciona como o **"Plaid do E-commerce para Agentes"**, atuando como middleware de integração entre frameworks de IA e plataformas de comércio eletrônico.

A arquitetura opera sob três pilares essenciais:
1. **Roteamento Híbrido de Compra:** 
   - **Ecossistemas Fechados (Mercado Livre, Shopee):** O agente executa busca de dados públicos, monitoramento de preços e auditoria de lotes, mas entrega ao usuário final um link direto de carrinho/checkout pré-preenchido para aprovação com 1 clique humano (evitando a guerra técnica contra captchas, biometria e 2FA).
   - **Lojas Abertas / Parceiras (Shopify, VTEX, APIs B2B):** O agente finaliza a compra de forma 100% autônoma via API usando o saldo da carteira pré-paga.
2. **Autonomous Wallet & Best Payment Engine:** Carteira pré-paga recarregada via Pix (e futuramente stablecoins/USDC), com travas programáveis estritas (teto por transação, limite diário, preço teto). O motor avalia as condições de pagamento da loja e prioriza automaticamente o método de menor custo efetivo (ex: capturando o desconto de 10% do Pix à vista usando a liquidez pré-alocada da carteira).
3. **Verified Merchant Shield & Triagem de Domínios:** Protocolo de assinatura digital e allowlist de lojistas. Agentes podem pesquisar na web aberta, mas compras autônomas são restritas a domínios com certificado e reputação atestada, mitigando *Honeypot Stores* e *Prompt Injections de Preços*.
4. **Navegação Inteligente com Modelo de Decisão Rápida (System 1 / Jev):** No pipeline de scraping e extração de ofertas, utilização de modelos de decisão não-autoregressivos ultra-rápidos (como Jev) para classificar legitimidade de páginas, extrair preços por forma de pagamento e checar estoque em <200ms, economizando 90% dos tokens de LLMs caros.

**Modelo de Monetização:** Taxa de intermediação (*take-rate*) de **1,5% a 2%** sobre o volume bruto de compras realizadas via saldo pré-pago da plataforma.

## Mecânica de Busca, Navegação e Pagamento

### 1. Web Aberta vs. Whitelist (Como o Agente opera)
* **Busca:** O agente pode explorar o catálogo do ACP ou rastrear a web aberta.
* **Classificação no Checkout:**
  * **Lojas na Whitelist Verificada:** Compra autônoma autorizada sem intervenção humana, se respeitar as travas da carteira.
  * **Ecossistemas Fechados (Meli/Shopee):** Geração de deep link de carrinho/checkout formatado para 1 clique do humano.
  * **Lojas Desconhecidas / Não Verificadas:** Bloqueio de compra autônoma; aviso de segurança ao agente com opção de hand-off humano.

### 2. Otimizador de Formas de Pagamento (Captura de Descontos à Vista)
Muitos e-commerces exibem um preço de vitrine (cartão parcelado), mas oferecem 5% a 15% de desconto no Pix. Como a carteira do ACP possui liquidez imediata pré-paga, o motor normaliza o preço para o **Menor Preço Efetivo**:
$$\text{Preço Efetivo} = \min(\text{Preço Pix}, \text{Preço Boleto}, \text{Preço 1x Cartão}) + \text{Taxa ACP (1,5\%)}$$

### 3. Camada de Decisão Ultrarrápida (System 1 / Jev)
Para evitar que o agente gaste milhares de tokens de raciocínio (LLMs generalistas caros) lendo árvores de HTML e avaliando seletividade de produtos:
* O crawler do ACP emprega o **Jev** para decisões estruturadas de 70-300ms:
  * *Esta página é um produto real ou página de busca/categoria?*
  * *O produto está em estoque para a quantidade solicitada?*
  * *O vendedor possui reputação confiável?*
  * *Qual é o preço no Pix vs. Cartão?*

### 4. Liquidação Financeira M2M & Vault de Endereços
* **Liquidação via BaaS (Banking-as-a-Service):** O ACP integra-se a APIs de BaaS (Efí, Asaas, Stark Bank). Quando o pedido é criado na loja via Storefront API com opção Pix, a loja devolve o Pix Copia-e-Cola. O backend do ACP debita o saldo pré-pago, retém a taxa de 1,5% e executa o envio do Pix diretamente à conta da loja em < 3 segundos.
* **Shipping Vault Profiles (Segurança contra Injeção de Prompt):** Endereços de entrega não trafegam como strings abertas no prompt do LLM. O usuário cadastra perfis previamente no cofre da carteira (ex: `"profile_id": "galpao_sp"`). O agente apenas referencia o ID. Isso impede que agentes comprometidos por prompt injection desviem encomendas para endereços maliciosos e economiza centenas de tokens.
* **Segurança de Chaves:** As credenciais de API do agente operam sob o princípio do menor privilégio (`order:pay`), sendo incapazes de realizar saques ou transferências avulsas fora da allowlist de lojistas verificados.

### 5. Topologia do Sistema: Local-First com Cloud Gateway Mínimo
* **Local (Máquina do Desenvolvedor):** Servidor MCP leve em TypeScript/Node.js (`npx -y @agent-commerce/mcp-server`), conectando-se diretamente aos frameworks de IA locais (CrewAI, LangChain, Claude Desktop) via `stdio`.
* **Nuvem (Backend ACP Central em KVM / Docker Compose):**
  * **Hospedagem MVP:** VPS KVM dedicada (Hostinger) rodando uma stack unificada via Docker Compose:
    - `acp-api`: Backend assíncrono em Python com **FastAPI** e Pydantic.
    - `acp-postgres`: Banco de dados relacional com integridade ACID para transações da carteira e histórico de pedidos (com rotina diária de backup via `pg_dump`).
    - `acp-redis`: Cache de consultas de catálogo e filas de tarefas para trackers de preços (Celery / ARQ).
  * **Mecânica de Custódia e Recolhimento de Taxas (Take-rate 1,5% a 2%):**
    - A plataforma opera uma conta PJ integrada a uma API de **BaaS (Asaas ou Efí Bank)**.
    - O cliente recarrega a carteira via Pix gerado pelo BaaS; o valor entra na conta escrow PJ da plataforma e é creditado no ledger virtual do PostgreSQL.
    - Na compra, o backend debita o valor do produto + a taxa de 1,5%-2% do saldo do usuário e liquida apenas o valor líquido do produto via Pix para o lojista parceiro.
    - A taxa de intermediação permanece retida na conta PJ como receita operacional da empresa, pronta para transferência automática.
  * **Registry de Lojistas:** Endpoint para validação de certificados e domínios da allowlist.

---

## Contratos da API & MCP Tools

### 1. `search_products`
Pesquisa em catálogo integrado e parceiros agregados com cálculo do melhor preço por método de pagamento.
```json
// Input Schema
{
  "query": "string (ex: 'iPhone 15 128GB')",
  "min_quantity": 1,
  "max_unit_price": 5000.00,
  "prefer_best_cash_price": true,
  "merchant_filter": "all | verified_only | closed_marketplaces_only"
}

// Output Schema
{
  "results": [
    {
      "product_id": "prod_abc123",
      "title": "Apple iPhone 15 128GB Preto",
      "merchant": {
        "domain": "kabum.com.br",
        "is_verified": true,
        "trust_score": 0.98
      },
      "pricing": {
        "display_price": 5299.00,
        "best_effective_price": 4769.10,
        "best_payment_method": "pix",
        "cash_discount_pct": 10.0,
        "fee_acp_estimated": 71.53
      },
      "stock_available": 45,
      "execution_type": "autonomous" // ou "human_handoff"
    }
  ]
}
```

### 2. `track_price_and_stock`
Registra monitoramento com callback quando o produto atinge o desconto ou estoque desejado.
```json
// Input Schema
{
  "product_url_or_id": "https://...",
  "target_price": 4500.00,
  "target_payment_method": "pix",
  "min_stock": 5,
  "webhook_url": "https://agent-backend.com/webhook/alerts"
}

// Output Schema
{
  "tracker_id": "tr_789xyz",
  "status": "active",
  "current_best_price": 4769.10,
  "check_interval_seconds": 300
}
```

### 3. `get_merchant_status`
Valida se um domínio terceiro possui credenciais e selo anti-fraude.
```json
// Input Schema
{
  "domain": "exemplo-lojista.com.br"
}

// Output Schema
{
  "domain": "exemplo-lojista.com.br",
  "verification_status": "verified | unverified | blacklisted",
  "has_well_known_acp_signature": true,
  "allowed_execution_modes": ["autonomous", "human_handoff"],
  "fraud_risk_score": 0.02
}
```

### 4. `checkout`
Executa a ordem de compra respeitando as travas de segurança da carteira.
```json
// Input Schema
{
  "order_items": [
    {
      "product_id_or_url": "prod_abc123",
      "quantity": 10,
      "max_accepted_unit_price": 4800.00
    }
  ],
  "payment_preference": "best_price", // "pix" | "wallet" | "credit_card"
  "allow_human_handoff_fallback": true
}

// Output Schema (Cenário Autônomo)
{
  "order_id": "ord_99901",
  "status": "completed",
  "execution_mode": "autonomous",
  "financial_summary": {
    "subtotal": 47691.00,
    "payment_method_applied": "pix",
    "cash_savings": 5299.00,
    "acp_platform_fee": 715.36,
    "wallet_debited": 48406.36,
    "remaining_wallet_balance": 1593.64
  }
}

// Output Schema (Cenário Híbrido / Ecossistema Fechado)
{
  "order_id": "ord_99902",
  "status": "pending_human_approval",
  "execution_mode": "human_handoff",
  "reason": "CLOSED_ECOSYSTEM_MERCADOLIVRE",
  "handoff_payload": {
    "approval_url": "https://mercadolivre.com.br/checkout/cart?ref=acp_...",
    "expires_at": "2026-10-11T14:30:00Z",
    "instructions": "Envie esta URL ao usuário final para confirmação de 1 clique."
  }
}
```

---

## Key Assumptions to Validate
- [ ] **Adoção do Desenvolvedor de IA:** Criadores de agentes de automação preferem plugar um servidor MCP padronizado e documentado a construir e manter scrapers frágeis por conta própria. *(Validação: disponibilizar o pacote MCP open-source e mensurar instalações e chamadas ativas de ferramentas).*
- [ ] **Aceitação do Checkout Híbrido:** Usuários e empresas aceitam que compras em plataformas fechadas (Meli/Shopee) exijam 1 clique humano final de aprovação no link gerado. *(Validação: entrevistas e testes de usabilidade com operadores de procurement).*
- [ ] **Resistência à Taxa de 2%:** O comprador corporativo não vê atrito na taxa percentual de 1,5% a 2% em troca de proteção contra alucinações e facilidade de compra em lote. *(Validação: teste com ordens simuladas e orçamentos reais).*
- [ ] **Eficácia da Allowlist contra Honeypots:** Um sistema simples de verificação de domínio (`/.well-known/agent-commerce.json` ou assinatura de chave) é suficiente para garantir a idoneidade da loja para o agente.

## MVP Scope & Cronograma (4 Semanas)
> O plano de execução detalhado com os goals semanais está documentado em:  
> 🔗 [mvp-4-weeks-implementation-plan.md](file:///C:/Users/elast/docs/plans/mvp-4-weeks-implementation-plan.md)  
> 
> A visão arquitetural de longo prazo para escala e expansão para os EUA está em:  
> 🔗 [scalability-and-global-expansion.md](file:///C:/Users/elast/docs/plans/scalability-and-global-expansion.md)

O MVP testa a viabilidade da comunicação do agente, a trava da carteira e os dois modos de compra (híbrido e autônomo):

* **MCP Server & REST API:**
  - Implementação das 4 ferramentas documentadas (`search_products`, `track_price_and_stock`, `get_merchant_status`, `checkout`).
* **Scraper de Leitura (Mercado Livre):**
  - Consulta somente de leitura para extrair preço, título, reputação do vendedor e estoque disponível.
  - Gerador de link de carrinho/checkout formatado para o fluxo híbrido.
* **1 Conector de Loja Aberta (Mock / Shopify Dev Store):**
  - Execução de pedido ponta a ponta com chamada de API e débito em carteira com captura do desconto de Pix.
* **Wallet com Travas Básicas:**
  - Controle de saldo pré-pago (sandbox com recarga simulada ou Pix de teste).
  - Regras de bloqueio automático caso o agente tente comprar acima do limite configurado.
* **Allowlist de Lojistas Verificados (Mock inicial):**
  - Checagem simples para permitir compras autônomas apenas em parceiros autorizados.

## Not Doing (O que fica categoricamente FORA do MVP e por quê)
- **Nenhum Frontend Web / Painel Visual:** O consumidor inicial é o desenvolvedor de IA e o próprio agente. Dashboards visuais aumentam o custo e tempo de validação sem testar a hipótese central.
- **Nada de Automação de Checkout Headless no Mercado Livre / Shopee:** Tentar burlar captchas e 2FA gera fragilidade crítica, custo alto de proxies residenciais e risco de bloqueio de contas.
- **Nada de Cartão de Crédito Tradicional (Stripe / Gateways de Cartão):** Taxas de 3% a 4% e risco de chargeback inviabilizam o take-rate de 1,5% a 2%. O MVP opera com Pix / Saldo pré-pago.
- **Sem Expansão Global Imediata (ACH/SEPA/Bancos Estrangeiros):** Foco geográfico inicial no Brasil (Pix). A camada internacional será resolvida na v2 via stablecoins (USDC).
- **Sem Responsabilidade de Marketplace:** A plataforma é um intermediador tecnológico de protocolos e segurança, sem custódia de mercadorias físicas nem responsabilidade por garantias/defeitos.

## Open Questions
1. Qual vertical de produtos em lote (eletrônicos para revenda, insumos de escritório, componentes de TI) possui maior demanda reprimida por compras automatizadas?
2. Como normalizar os atributos técnicos e SKUs vindos de múltiplos fornecedores para que o agente compare produtos equivalentes de forma precisa?
3. O protocolo de verificação de lojas (*Verified Merchant*) deve evoluir para um padrão aberto da comunidade ou uma autoridade certificadora própria?
