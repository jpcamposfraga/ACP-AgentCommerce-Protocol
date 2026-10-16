import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { AcpApiClient } from '../api-client.js';

export function registerDepositTool(server: McpServer, client: AcpApiClient) {
  server.tool(
    'deposit_wallet',
    'Solicita recarga via Pix para uma carteira ACP. Retorna o QR Code em arte UTF-8 para escanear na tela do monitor com o celular, o link de imagem PNG direto para visualização no navegador e o código Pix Copia-e-Cola.',
    {
      wallet_id: z.string().min(1).describe('Identificador da carteira pré-paga no ACP'),
      amount: z.number().positive().describe('Valor em Reais a ser recarregado (ex: 50.0)'),
      customer_name: z.string().optional().describe('Nome do titular pagador (opcional)')
    },
    async (args) => {
      try {
        const data = await client.depositWallet(args);
        const webUrl = data.qr_code_url.startsWith('http')
          ? data.qr_code_url
          : `http://localhost:8000${data.qr_code_url}`;

        const formattedText = [
          `### 💳 Cobrança Pix para Recarga de Carteira`,
          `• **ID da Cobrança:** ${data.payment_id}`,
          `• **Valor da Recarga:** R$ ${data.value.toFixed(2)}`,
          `• **Expira em:** ${data.expiration_date}`,
          ``,
          `#### 📱 Escanear QR Code com a Câmera do Celular:`,
          `\`\`\``,
          data.qr_code_terminal || 'QR Code indisponível em modo texto',
          `\`\`\``,
          ``,
          `• **Visualizar Imagem no Navegador:** [Abrir QR Code PNG](${webUrl})`,
          ``,
          `#### 📋 Pix Copia-e-Cola:`,
          `\`${data.copy_paste_payload}\``,
          ``,
          `*Assim que o pagamento for concluído no aplicativo do seu banco, o saldo será creditado automaticamente na sua carteira ACP.*`
        ].join('\n');

        return {
          content: [
            {
              type: 'text',
              text: formattedText
            }
          ]
        };
      } catch (err: any) {
        return {
          isError: true,
          content: [
            {
              type: 'text',
              text: `Erro ao gerar recarga Pix: ${err.message}`
            }
          ]
        };
      }
    }
  );
}
