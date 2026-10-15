"""
AgentCommerce Protocol (ACP) - Missão de Exemplo com Agente Autônomo
====================================================================
Este script demonstra a execução autônoma de um agente conectado ao ACP
para cumprir o seguinte objetivo em linguagem natural:

"Pesquise o iPhone 15, verifique se há estoque para 2 unidades e, se o preço à vista
no Pix estiver abaixo de R$ 5.000,00 cada, compre usando o meu saldo pré-pago na loja parceira;
caso encontre apenas no Mercado Livre, me entregue o link do carrinho pronto."
"""

import asyncio
import json
import httpx

ACP_API_BASE = "http://localhost:8000"


async def run_autonomous_mission():
    print("=" * 70)
    print("🤖 INICIANDO MISSÃO AUTÔNOMA DO AGENTE VIA ACP")
    print("=" * 70)

    async with httpx.AsyncClient(base_url=ACP_API_BASE, timeout=15.0) as client:
        # 1. SETUP: Criar ou verificar carteira pré-paga do agente
        print("\n💳 1. Inicializando carteira pré-paga com R$ 12.000,00...")
        wallet_res = await client.post("/api/v1/wallets", json={
            "user_id": "agente_comprador_demo",
            "max_per_order": 15000.0,
            "daily_limit": 20000.0
        })
        wallet = wallet_res.json()
        wallet_id = wallet["id"]

        # Recarrega saldo via webhook Pix simulado
        await client.post("/api/v1/webhooks/pix", json={
            "event": "pix_received",
            "payment_id": "topup_demo_01",
            "wallet_id": wallet_id,
            "amount": 12000.0,
            "end_to_end_id": "E_DEMO_TOPUP_12000"
        })
        print(f"   ✅ Carteira configurada: {wallet_id} | Saldo: R$ 12.000,00")

        # 2. FERRAMENTA MCP: search_products
        print("\n🔍 2. Agente invocando tool MCP 'search_products'...")
        search_res = await client.post("/api/v1/search", json={
            "query": "iPhone 15 128GB",
            "min_quantity": 2,
            "prefer_best_cash_price": True
        })
        search_data = search_res.json()
        total_found = search_data["total_results"]
        results = search_data["results"]
        print(f"   ✅ {total_found} ofertas encontradas e classificadas com zero tokens LLM.")

        for i, item in enumerate(results[:3], start=1):
            pricing = item["pricing"]
            print(f"   [{i}] {item['title'][:40]}... | Preço Vitrine: R$ {pricing['display_price']} | Pix Efetivo: R$ {pricing['best_effective_price']} (Desc: {pricing['cash_discount_pct']}%)")

        best_item = results[0]
        best_price = best_item["pricing"]["best_effective_price"]
        print(f"\n🧠 3. Agente analisando menor preço: R$ {best_price:.2f} via Pix.")

        # 4. DECISÃO DE COMPRA AUTÔNOMA VS HÍBRIDA
        if best_price <= 5000.0:
            print("\n🛒 4A. Preço abaixo do teto de R$ 5.000,00! Executando Compra Autônoma...")
            checkout_res = await client.post("/api/v1/checkout", json={
                "wallet_id": wallet_id,
                "order_items": [
                    {
                        "product_id_or_url": "SKU-IPHONE-15-PARCEIRO",
                        "quantity": 2,
                        "unit_price": best_price,
                        "merchant_domain": "lojaparceira.com.br"
                    }
                ],
                "shipping_profile_id": "sp_deposito_central"
            })
            checkout_data = checkout_res.json()
            print("   ✅ COMPRA AUTÔNOMA LIQUIDADA COM SUCESSO!")
            print(f"   - Order ID: {checkout_data['order_id']}")
            print(f"   - Total Debitado: R$ {checkout_data['total_debited']:.2f}")
            print(f"   - Pix E2E ID: {checkout_data['receipt']['pix_end_to_end_id']}")
            print(f"   - Taxa 2% Retida: R$ {checkout_data['receipt']['acp_fee_retained']:.2f}")

        # Demonstração do Modo Híbrido se o produto estivesse no Mercado Livre
        print("\n🔗 4B. Cenário Alternativo (Mercado Livre / Ecossistema Fechado):")
        meli_res = await client.post("/api/v1/checkout", json={
            "wallet_id": wallet_id,
            "order_items": [
                {
                    "product_id_or_url": "MLB-1001",
                    "quantity": 2,
                    "unit_price": best_price,
                    "merchant_domain": "mercadolivre.com.br"
                }
            ],
            "shipping_profile_id": "sp_deposito_central"
        })
        meli_data = meli_res.json()
        print(f"   - Status: {meli_data['status']} ({meli_data['execution_type']})")
        print(f"   - Link Direto 1-Clique: {meli_data['handoff_url']}")

    print("\n" + "=" * 70)
    print("🎯 MISSÃO CONCLUÍDA COM 100% DE SUCESSO")
    print("=" * 70)


if __name__ == "__main__":
    asyncio.run(run_autonomous_mission())
