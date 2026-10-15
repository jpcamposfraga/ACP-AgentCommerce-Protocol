import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { AcpApiClient } from '../api-client.ts';
import { registerSearchTool } from './search.ts';
import { registerTrackTool } from './track.ts';
import { registerMerchantTool } from './merchant.ts';
import { registerCheckoutTool } from './checkout.ts';

export function registerAllTools(server: McpServer, client: AcpApiClient) {
  registerSearchTool(server, client);
  registerTrackTool(server, client);
  registerMerchantTool(server, client);
  registerCheckoutTool(server, client);
}
