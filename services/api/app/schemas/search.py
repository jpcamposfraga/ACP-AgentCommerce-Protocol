from typing import Literal
from pydantic import BaseModel, Field

class SearchRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Termo de pesquisa do produto")
    min_quantity: int = Field(default=1, ge=1, description="Quantidade mínima necessária")
    max_unit_price: float | None = Field(default=None, gt=0, description="Preço unitário máximo aceitável")
    prefer_best_cash_price: bool = Field(default=True, description="Priorizar o menor preço com desconto à vista (Pix)")
    merchant_filter: Literal["all", "verified_only", "closed_marketplaces_only"] = Field(
        default="all",
        description="Filtro de tipos de lojistas"
    )
    region: Literal["BR", "US", "GLOBAL"] = Field(
        default="BR",
        description="Região geográfica para busca de ofertas"
    )
    currency: Literal["BRL", "USD", "EUR"] = Field(
        default="BRL",
        description="Moeda esperada para exibição e cálculo"
    )
    allowed_domains: list[str] | None = Field(
        default=None,
        description="Whitelist opcional de domínios confiáveis para restringir a busca"
    )

class ProductPricing(BaseModel):
    display_price: float = Field(..., description="Preço de vitrine / parcelado")
    best_effective_price: float = Field(..., description="Menor preço efetivo com taxa ACP embutida")
    best_payment_method: str = Field(default="pix", description="Método de pagamento com maior desconto")
    cash_discount_pct: float = Field(default=0.0, description="Percentual de desconto à vista")
    fee_acp_estimated: float = Field(default=0.0, description="Taxa de intermediação estimada do ACP")
    currency: str = Field(default="BRL", description="Moeda de cotação")

class MerchantInfo(BaseModel):
    domain: str = Field(..., description="Domínio da loja ou marketplace")
    is_verified: bool = Field(default=False, description="Possui selo e assinatura digital ACP")
    trust_score: float = Field(default=0.5, ge=0.0, le=1.0, description="Score de confiabilidade (0 a 1)")

class ProductSearchResult(BaseModel):
    product_id: str = Field(..., description="ID único do produto na origem")
    title: str = Field(..., description="Título do produto")
    url: str = Field(..., description="URL direta da oferta")
    merchant: MerchantInfo = Field(..., description="Informações do comerciante")
    pricing: ProductPricing = Field(..., description="Precificação e oportunidades de desconto")
    stock_available: int = Field(default=1, ge=0, description="Quantidade em estoque")
    execution_type: Literal["autonomous", "human_handoff"] = Field(
        default="human_handoff",
        description="Tipo de execução suportado (autônomo para parceiros, hand-off para ecossistemas fechados)"
    )

class SearchResponse(BaseModel):
    results: list[ProductSearchResult] = Field(default_factory=list)
    total_results: int = Field(default=0)
