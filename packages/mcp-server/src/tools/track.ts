import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { AcpApiClient } from '../api-client.js';

export function registerTrackTool(server: McpServer, client: AcpApiClient) {
  server.tool(
    'track_price_and_stock',
    'Registra monitoramento contínuo de preço e estoque de um produto no ACP com trava de segurança de intervalo mínimo de 60 segundos.',
    {
      product_url_or_id: z.string().min(1).describe("URL direta ou ID do produto (ex: MLB-1001)"),
      target_price: z.number().positive().describe("Preço alvo desejado em Reais"),
      target_payment_method: z.enum(['pix', 'credit_card', 'any']).default('pix').describe("Método de pagamento alvo"),
      min_stock: z.number().int().min(1).default(1).describe("Estoque mínimo exigido"),
      check_interval_seconds: z.number().int().default(300).describe("Intervalo de checagem em segundos (mínimo de 60s)"),
      webhook_url: z.string().url().optional().describe("Webhook opcional para receber alertas quando a meta for atingida")
    },
    async (args) => {
      try {
        const data = await client.trackPrice(args);
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
              text: `Erro ao registrar monitoramento: ${err.message}`
            }
          ]
        };
      }
    }
  );
}
