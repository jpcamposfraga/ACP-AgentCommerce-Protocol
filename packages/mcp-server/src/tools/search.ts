import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { AcpApiClient } from '../api-client.ts';

export function registerSearchTool(server: McpServer, client: AcpApiClient) {
  server.tool(
    'search_products',
    'Pesquisa produtos na web e marketplaces (Mercado Livre, lojas abertas, etc.) com decomposição do Menor Preço Efetivo (Pix à vista) e score de confiança anti-golpe.',
    {
      query: z.string().min(1).describe("Termo de pesquisa do produto (ex: 'iPhone 15 128GB')"),
      min_quantity: z.number().int().min(1).default(1).describe("Quantidade mínima necessária"),
      max_unit_price: z.number().positive().optional().describe("Preço unitário máximo aceitável em Reais"),
      prefer_best_cash_price: z.boolean().default(true).describe("Priorizar menor preço efetivo considerando desconto à vista no Pix"),
      merchant_filter: z.enum(['all', 'verified_only', 'closed_marketplaces_only']).default('all').describe("Filtro de tipos de lojistas")
    },
    async (args) => {
      try {
        const data = await client.searchProducts(args);
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
              text: `Erro ao buscar produtos: ${err.message}`
            }
          ]
        };
      }
    }
  );
}
