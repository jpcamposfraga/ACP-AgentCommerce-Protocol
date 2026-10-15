import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { registerAllTools } from '../src/tools/index.ts';
import { AcpApiClient } from '../src/api-client.ts';

describe('MCP Tools Registration', () => {
  test('registers all 4 official ACP tools on McpServer', () => {
    const server = new McpServer({ name: 'test-server', version: '0.1.0' });
    const mockClient = new AcpApiClient('http://localhost:8000');

    registerAllTools(server, mockClient);

    const registeredToolNames = Object.keys((server as any)._registeredTools);
    assert.ok(registeredToolNames.includes('search_products'), 'search_products must be registered');
    assert.ok(registeredToolNames.includes('track_price_and_stock'), 'track_price_and_stock must be registered');
    assert.ok(registeredToolNames.includes('get_merchant_status'), 'get_merchant_status must be registered');
    assert.ok(registeredToolNames.includes('checkout'), 'checkout must be registered');
    assert.equal(registeredToolNames.length, 4);
  });

  test('search_products tool handler executes and returns formatted content', async () => {
    const server = new McpServer({ name: 'test-server', version: '0.1.0' });
    const mockClient = {
      searchProducts: async (params: any) => ({
        results: [
          {
            product_id: 'MLB-1001',
            title: 'Apple iPhone 15 128GB',
            pricing: { best_effective_price: 4769.0 }
          }
        ],
        total_results: 1
      })
    } as unknown as AcpApiClient;

    registerAllTools(server, mockClient);

    const tool = (server as any)._registeredTools['search_products'];
    assert.ok(tool, 'search_products tool exists');

    const result = await tool.handler({ query: 'iPhone 15' }, {});
    assert.ok(result.content);
    assert.equal(result.content[0].type, 'text');
    const parsed = JSON.parse(result.content[0].text);
    assert.equal(parsed.total_results, 1);
    assert.equal(parsed.results[0].product_id, 'MLB-1001');
  });
});
