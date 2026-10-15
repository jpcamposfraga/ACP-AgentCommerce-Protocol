import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { AcpApiClient } from '../api-client.js';
import { registerSearchTool } from './search.js';
import { registerTrackTool } from './track.js';
import { registerMerchantTool } from './merchant.js';
import { registerCheckoutTool } from './checkout.js';

export function registerAllTools(server: McpServer, client: AcpApiClient) {
  registerSearchTool(server, client);
  registerTrackTool(server, client);
  registerMerchantTool(server, client);
  registerCheckoutTool(server, client);
}
