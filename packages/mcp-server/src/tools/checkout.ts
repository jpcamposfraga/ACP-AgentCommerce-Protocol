import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { AcpApiClient } from '../api-client.js';

export function registerCheckoutTool(server: McpServer, client: AcpApiClient) {
  server.tool(
    'checkout',
    'Executa o fluxo de checkout com a carteira pré-paga do ACP. Em lojas parceiras verificadas, realiza o pagamento 100% autônomo via Pix BaaS. Em marketplaces fechados (Mercado Livre), gera link direto de carrinho pronto para aprovação com 1 clique humano.',
    {
      wallet_id: z.string().min(1).describe("ID da carteira pré-paga do ACP"),
      order_items: z.array(
        z.object({
          product_id_or_url: z.string().describe("ID ou URL do produto"),
          quantity: z.number().int().min(1).describe("Quantidade a ser comprada"),
          unit_price: z.number().positive().describe("Preço unitário em Reais"),
          merchant_domain: z.string().describe("Domínio da loja (ex: 'mercadolivre.com.br', 'lojaparceira.com.br')")
        })
      ).min(1).describe("Lista de itens incluídos no pedido"),
      shipping_profile_id: z.string().default('default').describe("Identificador do perfil seguro de entrega no Shipping Vault")
    },
    async (args) => {
      try {
        const data = await client.checkout(args);
        return {
          content: [
            {
              type: 'text',
              text: JSON.stringify(data, null, 2)
            }
          ]
        };
      } catch (err: any) {
        return {
          isError: true,
          content: [
            {
              type: 'text',
              text: `Erro ao executar checkout: ${err.message}`
            }
          ]
        };
      }
    }
  );
}
