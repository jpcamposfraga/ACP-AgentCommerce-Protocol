import { test, describe, beforeEach, afterEach } from 'node:test';
import assert from 'node:assert/strict';
import { AcpApiClient } from '../src/api-client.ts';

describe('AcpApiClient', () => {
  let originalFetch: typeof globalThis.fetch;

  beforeEach(() => {
    originalFetch = globalThis.fetch;
  });

  afterEach(() => {
    globalThis.fetch = originalFetch;
  });

  test('searchProducts sends POST to /api/v1/search with correct body', async () => {
    let capturedUrl = '';
    let capturedMethod = '';
    let capturedBody = '';

    globalThis.fetch = (async (url: string | URL | Request, init?: RequestInit) => {
      capturedUrl = url.toString();
      capturedMethod = init?.method || '';
      capturedBody = init?.body?.toString() || '';

      return new Response(JSON.stringify({
        results: [
          {
            product_id: 'MLB-1001',
            title: 'iPhone 15',
            pricing: { best_effective_price: 4769.0 }
          }
        ],
        total_results: 1
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }) as typeof globalThis.fetch;

    const client = new AcpApiClient('http://localhost:8000');
    const result = await client.searchProducts({ query: 'iPhone 15', prefer_best_cash_price: true });

    assert.equal(capturedUrl, 'http://localhost:8000/api/v1/search');
    assert.equal(capturedMethod, 'POST');
    assert.deepEqual(JSON.parse(capturedBody), { query: 'iPhone 15', prefer_best_cash_price: true });
    assert.equal(result.total_results, 1);
    assert.equal(result.results[0].product_id, 'MLB-1001');
  });

  test('getMerchantStatus sends GET to /api/v1/merchant/status?domain=...', async () => {
    let capturedUrl = '';

    globalThis.fetch = (async (url: string | URL | Request) => {
      capturedUrl = url.toString();
      return new Response(JSON.stringify({
        domain: 'mercadolivre.com.br',
        verification_status: 'verified',
        fraud_risk_score: 0.05
      }), { status: 200, headers: { 'Content-Type': 'application/json' } });
    }) as typeof globalThis.fetch;

    const client = new AcpApiClient('http://localhost:8000');
    const result = await client.getMerchantStatus('mercadolivre.com.br');

    assert.equal(capturedUrl, 'http://localhost:8000/api/v1/merchant/status?domain=mercadolivre.com.br');
    assert.equal(result.verification_status, 'verified');
  });

  test('checkout sends POST to /api/v1/checkout and handles error responses', async () => {
    globalThis.fetch = (async () => {
      return new Response(JSON.stringify({ detail: 'Saldo insuficiente' }), {
        status: 402,
        headers: { 'Content-Type': 'application/json' }
      });
    }) as typeof globalThis.fetch;

    const client = new AcpApiClient('http://localhost:8000');
    await assert.rejects(
      async () => {
        await client.checkout({
          wallet_id: 'w_123',
          order_items: [{ product_id_or_url: 'MLB-1', quantity: 1, unit_price: 500, merchant_domain: 'meli' }]
        });
      },
      {
        message: /Saldo insuficiente/
      }
    );
  });
});
