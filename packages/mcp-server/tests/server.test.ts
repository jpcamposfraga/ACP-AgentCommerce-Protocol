import { test, describe } from 'node:test';
import assert from 'node:assert/strict';
import { createServer } from '../dist/index.js';

describe('ACP MCP Server Factory', () => {
  test('createServer returns properly initialized McpServer with all 6 tools', () => {
    const server = createServer();
    assert.ok(server);
    const tools = Object.keys((server as any)._registeredTools);
    assert.deepEqual(
      tools.sort(),
      ['checkout', 'deposit_wallet', 'get_merchant_status', 'manage_shipping_address', 'search_products', 'track_price_and_stock'].sort()
    );
  });
});
