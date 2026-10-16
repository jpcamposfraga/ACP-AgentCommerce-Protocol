import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { z } from 'zod';
import { AcpApiClient } from '../api-client.js';

export function registerShippingTool(server: McpServer, client: AcpApiClient) {
  server.tool(
    'manage_shipping_address',
    'Gerencia endereços de entrega no Shipping Vault do ACP. Permite cadastrar novo endereço (com busca automática de CEP pelo ViaCEP) ou listar endereços existentes para uma carteira.',
    {
      action: z.enum(['register', 'list']).describe("Ação a ser executada: 'register' para cadastrar novo endereço ou 'list' para listar endereços"),
      wallet_id: z.string().min(1).describe('Identificador da carteira pré-paga vinculada'),
      recipient_name: z.string().optional().describe('Nome completo do destinatário (obrigatório para cadastro)'),
      cpf_cnpj: z.string().optional().describe('CPF ou CNPJ para emissão de NF-e (obrigatório para cadastro)'),
      phone: z.string().optional().describe('Telefone / WhatsApp para contato da transportadora (obrigatório para cadastro)'),
      postal_code: z.string().optional().describe('CEP do endereço (obrigatório para cadastro, ex: 01310-100)'),
      number: z.string().optional().describe('Número do imóvel (obrigatório para cadastro)'),
      complement: z.string().optional().describe('Complemento do imóvel (opcional: Apto, Bloco, etc.)'),
      street: z.string().optional().describe('Logradouro (opcional, se omitido será preenchido automaticamente pelo ViaCEP)'),
      neighborhood: z.string().optional().describe('Bairro (opcional, se omitido será preenchido automaticamente pelo ViaCEP)'),
      city: z.string().optional().describe('Cidade (opcional, se omitido será preenchido automaticamente pelo ViaCEP)'),
      state: z.string().optional().describe('Estado/UF (opcional, se omitido será preenchido automaticamente pelo ViaCEP)'),
      is_default: z.boolean().default(true).describe('Define se este endereço será o padrão para compras futuras')
    },
    async (args) => {
      try {
        if (args.action === 'list') {
          const profiles = await client.listShippingProfiles(args.wallet_id);
          return {
            content: [
              {
                type: 'text',
                text: JSON.stringify(profiles, null, 2)
              }
            ]
          };
        }

        // Cadastro
        if (!args.recipient_name || !args.cpf_cnpj || !args.phone || !args.postal_code || !args.number) {
          return {
            isError: true,
            content: [
              {
                type: 'text',
                text: 'Para cadastrar um endereço de entrega, os seguintes campos são obrigatórios: recipient_name, cpf_cnpj, phone, postal_code e number.'
              }
            ]
          };
        }

        const profile = await client.createShippingProfile({
          wallet_id: args.wallet_id,
          recipient_name: args.recipient_name,
          cpf_cnpj: args.cpf_cnpj,
          phone: args.phone,
          postal_code: args.postal_code,
          number: args.number,
          complement: args.complement,
          street: args.street,
          neighborhood: args.neighborhood,
          city: args.city,
          state: args.state,
          is_default: args.is_default
        });

        const formattedText = [
          `### 📦 Endereço de Entrega Cadastrado com Sucesso!`,
          `• **ID do Perfil:** ${profile.id}`,
          `• **Destinatário:** ${profile.recipient_name}`,
          `• **CPF/CNPJ:** ${profile.cpf_cnpj}`,
          `• **Telefone:** ${profile.phone}`,
          `• **Endereço:** ${profile.street}, nº ${profile.number}${profile.complement ? ` (${profile.complement})` : ''}`,
          `• **Bairro/Cidade:** ${profile.neighborhood} - ${profile.city}/${profile.state}`,
          `• **CEP:** ${profile.postal_code}`,
          `• **Endereço Padrão:** ${profile.is_default ? 'Sim' : 'Não'}`,
          ``,
          `*Este endereço está salvo no Shipping Vault e será utilizado automaticamente nas suas próximas compras autônomas.*`
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
              text: `Erro ao gerenciar endereço de entrega: ${err.message}`
            }
          ]
        };
      }
    }
  );
}
