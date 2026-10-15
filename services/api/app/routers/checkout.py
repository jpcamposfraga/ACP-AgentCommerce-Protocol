import uuid
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.config import settings
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.schemas.checkout import CheckoutRequest, CheckoutResponse, PaymentReceipt
from app.services.connectors.hybrid_meli import build_meli_handoff_url
from app.services.connectors.storefront import StorefrontPartnerClient
from app.services.baas import BaaSPixClient

router = APIRouter(prefix="/api/v1/checkout", tags=["checkout"])

storefront_client = StorefrontPartnerClient()
baas_client = BaaSPixClient()

CLOSED_MARKETPLACES = {
    "mercadolivre.com.br",
    "produto.mercadolivre.com.br",
    "www.mercadolivre.com.br",
    "shopee.com.br",
}


@router.post("", response_model=CheckoutResponse)
async def process_checkout(
    request: CheckoutRequest,
    db: AsyncSession = Depends(get_db)
):
    if not request.order_items:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nenhum item fornecido para checkout"
        )

    first_item = request.order_items[0]
    primary_domain = first_item.merchant_domain.strip().lower()

    # 1. ROTEAMENTO PARA MODO HÍBRIDO (Ecossistemas fechados / Mercado Livre / Shopee)
    if any(primary_domain == closed or primary_domain.endswith("." + closed) for closed in CLOSED_MARKETPLACES):
        handoff_url = build_meli_handoff_url(
            product_id_or_url=first_item.product_id_or_url,
            quantity=first_item.quantity
        )
        return CheckoutResponse(
            order_id=f"order_hybrid_{uuid.uuid4().hex[:8]}",
            status="pending_human_approval",
            execution_type="human_handoff",
            total_debited=0.0,
            handoff_url=handoff_url,
            receipt=None,
            message="Pedido preparado para aprovação com 1 clique humano."
        )

    # 2. ROTEAMENTO PARA MODO AUTÔNOMO (Lojas Parceiras / Storefronts abertas)
    total_order_amount = round(
        sum(item.quantity * item.unit_price for item in request.order_items),
        2
    )
    acp_fee = round(total_order_amount * settings.ACP_PLATFORM_FEE_PCT, 2)
    total_needed = round(total_order_amount + acp_fee, 2)

    # Localiza carteira no banco
    stmt = select(Wallet).where(Wallet.id == request.wallet_id)
    res = await db.execute(stmt)
    wallet = res.scalar_one_or_none()

    if not wallet or not wallet.is_active:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Carteira não encontrada ou inativa"
        )

    # Trava de governança: max_per_order
    if total_needed > wallet.max_per_order:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Valor excede o limite máximo por ordem (max_per_order: R$ {wallet.max_per_order:.2f})"
        )

    # Trava de governança: daily_limit
    today = datetime.now(timezone.utc).date()
    spent_today = wallet.spent_today if wallet.last_spend_date == today else 0.0

    if spent_today + total_needed > wallet.daily_limit:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Valor excede o limite diário da carteira (daily_limit: R$ {wallet.daily_limit:.2f})"
        )

    # Saldo suficiente
    if wallet.balance < total_needed:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Saldo insuficiente. Necessário: R$ {total_needed:.2f}, Disponível: R$ {wallet.balance:.2f}"
        )

    # Débito atômico condicional
    new_spent = spent_today + total_needed
    update_stmt = (
        update(Wallet)
        .where(Wallet.id == request.wallet_id, Wallet.balance >= total_needed)
        .values(
            balance=Wallet.balance - total_needed,
            spent_today=new_spent,
            last_spend_date=today
        )
    )
    update_res = await db.execute(update_stmt)
    if update_res.rowcount == 0:
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail="Falha no débito atômico. Saldo insuficiente ou concorrência detectada."
        )

    # Criação do pedido na Storefront API da loja parceira
    partner_order = await storefront_client.create_order(
        items=request.order_items,
        shipping_profile_id=request.shipping_profile_id
    )

    # Liquidação financeira imediata via BaaS Pix
    payout = await baas_client.send_pix_payout(
        amount=total_order_amount,
        pix_key=partner_order.pix_key,
        description=f"ACP Checkout {partner_order.order_id}"
    )

    # Registro da transação no ledger
    transaction = Transaction(
        wallet_id=request.wallet_id,
        amount=total_needed,
        platform_fee=acp_fee,
        net_amount=total_order_amount,
        type="DEBIT_PURCHASE",
        status="COMPLETED",
        reference_id=payout["end_to_end_id"],
        description=f"Compra autônoma #{partner_order.order_id} em {primary_domain}"
    )
    db.add(transaction)
    await db.commit()

    receipt = PaymentReceipt(
        pix_end_to_end_id=payout["end_to_end_id"],
        paid_at=payout["timestamp"],
        amount_transferred=total_order_amount,
        acp_fee_retained=acp_fee
    )

    return CheckoutResponse(
        order_id=partner_order.order_id,
        status="completed",
        execution_type="autonomous",
        total_debited=total_needed,
        handoff_url=None,
        receipt=receipt,
        message="Compra autônoma concluída com sucesso via saldo pré-pago e liquidação Pix."
    )
