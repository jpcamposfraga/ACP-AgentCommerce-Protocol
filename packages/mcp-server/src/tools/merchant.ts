import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { AcpApiClient } from '../api-client.js';

export function registerMerchantTool(server: McpServer, client: AcpApiClient) {
  server.tool(
    'get_merchant_status',
    'Verifica se o domínio do lojista é certificado pelo ACP (Verified Merchant Shield), se está na lista negra ou se requer hand-off humano.',
    {
      domain: z.string().min(3).describe("Domínio do lojista a ser auditado (ex: 'mercadolivre.com.br', 'amazon.com.br')")
    },
    async ({ domain }) => {
      try {
        const data = await client.getMerchantStatus(domain);
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
              text: `Erro ao consultar status do lojista: ${err.message}`
            }
          ]
        };
      }
    }
  );
}
