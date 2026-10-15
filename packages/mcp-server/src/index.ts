#!/usr/bin/env node
import { McpServer } from '@modelcontextprotocol/sdk/server/mcp.js';
import { StdioServerTransport } from '@modelcontextprotocol/sdk/server/stdio.js';
import { AcpApiClient } from './api-client.js';
import { registerAllTools } from './tools/index.js';

/**
 * Cria e configura uma instância do servidor MCP do ACP.
 */
export function createServer(apiClient?: AcpApiClient): McpServer {
  const server = new McpServer({
    name: 'agent-commerce-protocol',
    version: '0.1.0'
  });

  const client = apiClient || new AcpApiClient();
  registerAllTools(server, client);

  return server;
}

/**
 * Inicia o servidor conectado ao transporte stdio para comunicação JSON-RPC com LLMs.
 */
export async function runServer(): Promise<void> {
  const server = createServer();
  const transport = new StdioServerTransport();
  await server.connect(transport);
  console.error('AgentCommerce Protocol (ACP) MCP Server rodando via stdio.');
}

// Inicia se executado diretamente
const isDirectExecution = process.argv[1] && (
  import.meta.url === `file://${process.argv[1]}` ||
  process.argv[1].endsWith('index.ts') ||
  process.argv[1].endsWith('index.js')
);

if (isDirectExecution) {
  runServer().catch((error) => {
    console.error('Erro fatal ao iniciar servidor MCP:', error);
    process.exit(1);
  });
}
