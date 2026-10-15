from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.schemas.webhook import BaaSPixWebhook

router = APIRouter(prefix="/api/v1/webhooks", tags=["webhooks"])


@router.post("/pix")
async def handle_pix_webhook(
    payload: BaaSPixWebhook,
    db: AsyncSession = Depends(get_db)
):
    # 1. Checagem de Idempotência: se o end_to_end_id já foi liquidado, retorna sucesso sem duplicar
    tx_stmt = select(Transaction).where(Transaction.reference_id == payload.end_to_end_id)
    tx_result = await db.execute(tx_stmt)
    existing_tx = tx_result.scalar_one_or_none()

    if existing_tx:
        return {
            "status": "already_processed",
            "wallet_id": payload.wallet_id,
            "end_to_end_id": payload.end_to_end_id,
        }

    # 2. Localiza a carteira
    wallet_stmt = select(Wallet).where(Wallet.id == payload.wallet_id)
    wallet_res = await db.execute(wallet_stmt)
    wallet = wallet_res.scalar_one_or_none()

    if not wallet:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Wallet not found"
        )

    # 3. Incremento atômico de saldo
    update_stmt = (
        update(Wallet)
        .where(Wallet.id == payload.wallet_id)
        .values(balance=Wallet.balance + payload.amount)
    )
    await db.execute(update_stmt)

    # 4. Registra histórico da transação
    new_tx = Transaction(
        wallet_id=payload.wallet_id,
        amount=payload.amount,
        platform_fee=0.0,
        net_amount=payload.amount,
        type="TOPUP",
        status="COMPLETED",
        reference_id=payload.end_to_end_id,
        description=f"Pix cash-in {payload.payment_id}",
    )
    db.add(new_tx)
    await db.commit()

    return {
        "status": "credited",
        "wallet_id": payload.wallet_id,
        "amount": payload.amount,
        "end_to_end_id": payload.end_to_end_id,
    }
