from typing import Literal
from pydantic import BaseModel, Field


class CheckoutItem(BaseModel):
    product_id_or_url: str = Field(..., min_length=1, description="Identificador ou link direto do produto")
    quantity: int = Field(default=1, ge=1, description="Quantidade a ser comprada")
    unit_price: float = Field(..., gt=0.0, description="Preço unitário acordado ou cotado")
    merchant_domain: str = Field(..., min_length=3, description="Domínio do lojista ou marketplace")


class CheckoutRequest(BaseModel):
    wallet_id: str = Field(..., min_length=1, description="Identificador da carteira pré-paga no ACP")
    order_items: list[CheckoutItem] = Field(..., min_length=1, description="Itens a serem incluídos na compra")
    shipping_profile_id: str = Field(
        default="default",
        description="Identificador do perfil seguro de entrega no Shipping Vault"
    )
    idempotency_key: str | None = Field(
        default=None,
        description="Chave de idempotência para prevenção de duplicações"
    )
    preferred_autonomous_payment: Literal["auto", "pix", "virtual_card"] = Field(
        default="auto",
        description="Método de pagamento autônomo preferencial"
    )


class VirtualCardDetails(BaseModel):
    card_token: str = Field(..., description="Token seguro do cartão virtual efêmero")
    masked_pan: str = Field(..., description="Número mascarado do cartão para identificação")
    cvv: str = Field(..., description="Código de segurança de 3 dígitos")
    expiration: str = Field(..., description="Data de expiração no formato MM/AA")
    exact_amount_locked: float = Field(..., description="Limite estrito travado para a compra")
    currency: str = Field(default="BRL", description="Moeda de liquidação")
    status: str = Field(default="ACTIVE_ONE_TIME", description="Status do cartão")


class PaymentReceipt(BaseModel):
    pix_end_to_end_id: str = Field(..., description="ID fim-a-fim da transação Pix no Banco Central")
    paid_at: str = Field(..., description="Data/hora de liquidação no formato ISO-8601")
    amount_transferred: float = Field(..., gt=0.0, description="Valor líquido pago ao lojista")
    acp_fee_retained: float = Field(..., ge=0.0, description="Valor retido pela taxa de 2% do ACP")


class CheckoutResponse(BaseModel):
    order_id: str = Field(..., description="Identificador único da ordem gerada")
    status: Literal["completed", "pending_human_approval", "failed"] = Field(
        ...,
        description="Estado da execução do checkout"
    )
    execution_type: Literal["autonomous", "human_handoff"] = Field(
        ...,
        description="Tipo de execução aplicada no roteamento"
    )
    total_debited: float = Field(default=0.0, ge=0.0, description="Valor total debitado da carteira")
    handoff_url: str | None = Field(
        default=None,
        description="URL de carrinho/checkout pré-preenchido para aprovação com 1 clique"
    )
    receipt: PaymentReceipt | None = Field(
        default=None,
        description="Comprovante de liquidação financeira instantânea"
    )
    virtual_card: VirtualCardDetails | None = Field(
        default=None,
        description="Detalhes do cartão virtual efêmero gerado para liquidação"
    )
    message: str | None = Field(default=None, description="Mensagem descritiva ou motivo de falha")
