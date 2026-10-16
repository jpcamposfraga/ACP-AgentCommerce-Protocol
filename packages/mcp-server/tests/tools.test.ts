import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { registerAllTools } from '../dist/tools/index.js';
import { AcpApiClient } from '../dist/api-client.js';

describe('MCP Tools Registration', () => {
  test('registers all 6 ACP tools on McpServer', () => {
    const server = new McpServer({ name: 'test-server', version: '0.1.0' });
    const mockClient = new AcpApiClient('http://localhost:8000');

    registerAllTools(server, mockClient);

    const registeredToolNames = Object.keys((server as any)._registeredTools);
    assert.ok(registeredToolNames.includes('search_products'), 'search_products must be registered');
    assert.ok(registeredToolNames.includes('track_price_and_stock'), 'track_price_and_stock must be registered');
    assert.ok(registeredToolNames.includes('get_merchant_status'), 'get_merchant_status must be registered');
    assert.ok(registeredToolNames.includes('checkout'), 'checkout must be registered');
    assert.ok(registeredToolNames.includes('deposit_wallet'), 'deposit_wallet must be registered');
    assert.ok(registeredToolNames.includes('manage_shipping_address'), 'manage_shipping_address must be registered');
    assert.equal(registeredToolNames.length, 6);
  });

  test('deposit_wallet tool handler returns formatted terminal and url', async () => {
    const server = new McpServer({ name: 'test-server', version: '0.1.0' });
    const mockClient = {
      depositWallet: async (params: any) => ({
        payment_id: 'pay_123',
        wallet_id: params.wallet_id,
        value: params.amount,
        copy_paste_payload: '00020126580014br.gov.bcb.pix...',
        qr_code_terminal: '██  ██',
        qr_code_url: '/api/v1/wallets/w_1/pix-deposit/pay_123/qrcode.png',
        expiration_date: '2026-10-17'
      })
    } as unknown as AcpApiClient;

    registerAllTools(server, mockClient);

    const tool = (server as any)._registeredTools['deposit_wallet'];
    assert.ok(tool, 'deposit_wallet tool exists');

    const result = await tool.handler({ wallet_id: 'w_1', amount: 25.0 }, {});
    assert.ok(result.content);
    assert.equal(result.content[0].type, 'text');
    assert.ok(result.content[0].text.includes('QR Code'));
    assert.ok(result.content[0].text.includes('00020126580014br.gov.bcb.pix...'));
  });

  test('manage_shipping_address tool handler registers address', async () => {
    const server = new McpServer({ name: 'test-server', version: '0.1.0' });
    const mockClient = {
      createShippingProfile: async (params: any) => ({
        id: 'sp_new_99',
        wallet_id: params.wallet_id,
        recipient_name: params.recipient_name,
        street: 'Av Paulista',
        city: 'São Paulo',
        state: 'SP',
        is_default: true
      }),
      listShippingProfiles: async () => []
    } as unknown as AcpApiClient;

    registerAllTools(server, mockClient);

    const tool = (server as any)._registeredTools['manage_shipping_address'];
    assert.ok(tool, 'manage_shipping_address tool exists');

    const result = await tool.handler({
      action: 'register',
      wallet_id: 'w_1',
      recipient_name: 'Carlos Alberto',
      cpf_cnpj: '12345678909',
      phone: '11999998888',
      postal_code: '01310-100',
      number: '100'
    }, {});
    assert.ok(result.content);
    assert.equal(result.content[0].type, 'text');
    assert.ok(result.content[0].text.includes('Carlos Alberto'));
    assert.ok(result.content[0].text.includes('sp_new_99'));
  });
});
