export interface SearchParams {
  query: string;
  min_quantity?: number;
  max_unit_price?: number;
  prefer_best_cash_price?: boolean;
  merchant_filter?: 'all' | 'verified_only' | 'closed_marketplaces_only';
}

export interface ProductPricing {
  display_price: number;
  best_effective_price: number;
  best_payment_method: string;
  cash_discount_pct: number;
  fee_acp_estimated: number;
}

export interface MerchantInfo {
  domain: string;
  is_verified: boolean;
  trust_score: number;
}

export interface ProductSearchResult {
  product_id: string;
  title: string;
  url: string;
  merchant: MerchantInfo;
  pricing: ProductPricing;
  stock_available: number;
  execution_type: 'autonomous' | 'human_handoff';
}

export interface SearchResponse {
  results: ProductSearchResult[];
  total_results: number;
}

export interface TrackerParams {
  product_url_or_id: string;
  target_price: number;
  target_payment_method?: 'pix' | 'credit_card' | 'any';
  min_stock?: number;
  check_interval_seconds?: number;
  webhook_url?: string;
}

export interface TrackerResponse {
  tracker_id: string;
  status: string;
  product_url_or_id: string;
  target_price: number;
  current_best_price: number;
  check_interval_seconds: number;
  warning?: string | null;
}

export interface MerchantStatusResponse {
  domain: string;
  verification_status: 'verified' | 'unverified' | 'blacklisted';
  has_well_known_acp_signature: boolean;
  allowed_execution_modes: string[];
  fraud_risk_score: number;
}

export interface CheckoutItem {
  product_id_or_url: string;
  quantity: number;
  unit_price: number;
  merchant_domain: string;
}

export interface CheckoutParams {
  wallet_id: string;
  order_items: CheckoutItem[];
  shipping_profile_id?: string;
  idempotency_key?: string;
}

export interface PaymentReceipt {
  pix_end_to_end_id: string;
  paid_at: string;
  amount_transferred: number;
  acp_fee_retained: number;
}

export interface CheckoutResponse {
  order_id: string;
  status: 'completed' | 'pending_human_approval' | 'failed';
  execution_type: 'autonomous' | 'human_handoff';
  total_debited: number;
  handoff_url?: string | null;
  receipt?: PaymentReceipt | null;
  message?: string | null;
}

export class AcpApiClient {
  private baseUrl: string;

  constructor(baseUrl?: string) {
    this.baseUrl = baseUrl || process.env.ACP_API_URL || 'http://localhost:8000';
  }

  private async request<T>(endpoint: string, options: RequestInit = {}): Promise<T> {
    const url = `${this.baseUrl}${endpoint}`;
    const headers = {
      'Content-Type': 'application/json',
      ...(options.headers || {})
    };

    let res: Response;
    try {
      res = await fetch(url, { ...options, headers });
    } catch (err: any) {
      throw new Error(`Falha de conexão com o backend ACP (${url}): ${err.message}`);
    }

    if (!res.ok) {
      let errorDetail = res.statusText;
      try {
        const errorJson: any = await res.json();
        errorDetail = errorJson.detail || JSON.stringify(errorJson);
      } catch {
        // Ignora erro de parse caso a resposta não seja json
      }
      throw new Error(`Erro na API ACP [HTTP ${res.status}]: ${errorDetail}`);
    }

    return (await res.json()) as T;
  }

  async searchProducts(params: SearchParams): Promise<SearchResponse> {
    return this.request<SearchResponse>('/api/v1/search', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  async trackPrice(params: TrackerParams): Promise<TrackerResponse> {
    return this.request<TrackerResponse>('/api/v1/trackers', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }

  async getMerchantStatus(domain: string): Promise<MerchantStatusResponse> {
    const query = encodeURIComponent(domain);
    return this.request<MerchantStatusResponse>(`/api/v1/merchant/status?domain=${query}`, {
      method: 'GET'
    });
  }

  async checkout(params: CheckoutParams): Promise<CheckoutResponse> {
    return this.request<CheckoutResponse>('/api/v1/checkout', {
      method: 'POST',
      body: JSON.stringify(params)
    });
  }
}
