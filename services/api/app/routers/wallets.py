import uuid
import base64
from datetime import datetime, timezone, timedelta
from fastapi import APIRouter, Depends, HTTPException, status, Response
from sqlalchemy import select, update, case
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.config import settings, get_settings
from app.models.wallet import Wallet
from app.models.transaction import Transaction
from app.schemas.wallet import WalletCreate, WalletResponse, TopupRequest, DebitRequest, DebitResponse
from app.schemas.deposit import PixDepositRequest, PixDepositResponse
from app.services.baas_asaas import AsaasClient
from app.services.qrcode_service import render_terminal_qr, render_png_qr

router = APIRouter(prefix="/api/v1/wallets", tags=["Wallets"])
_PIX_QR_CACHE: dict[str, bytes] = {}

@router.post("", response_model=WalletResponse, status_code=status.HTTP_201_CREATED)
async def create_wallet(payload: WalletCreate, db: AsyncSession = Depends(get_db)):
    wallet = Wallet(
        user_id=payload.user_id,
        max_per_order=payload.max_per_order,
        daily_limit=payload.daily_limit,
        balance=0.0,
        spent_today=0.0
    )
    db.add(wallet)
    await db.commit()
    await db.refresh(wallet)
    return wallet

@router.get("/{wallet_id}", response_model=WalletResponse)
async def get_wallet(wallet_id: str, db: AsyncSession = Depends(get_db)):
    query = select(Wallet).where(Wallet.id == wallet_id)
    result = await db.execute(query)
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")
    return wallet

@router.post("/{wallet_id}/topup", response_model=WalletResponse)
async def topup_wallet(wallet_id: str, payload: TopupRequest, db: AsyncSession = Depends(get_db)):
    query = select(Wallet).where(Wallet.id == wallet_id).with_for_update()
    result = await db.execute(query)
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    if not wallet.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wallet is inactive")

    wallet.balance = round(wallet.balance + payload.amount, 2)

    transaction = Transaction(
        wallet_id=wallet.id,
        amount=payload.amount,
        platform_fee=0.0,
        net_amount=payload.amount,
        type="TOPUP",
        status="COMPLETED",
        reference_id=payload.reference_id,
        description="Recarga de saldo via Pix / Sandbox"
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)
    return wallet


@router.post("/{wallet_id}/pix-deposit", response_model=PixDepositResponse)
async def create_wallet_pix_deposit(
    wallet_id: str,
    payload: PixDepositRequest,
    db: AsyncSession = Depends(get_db)
):
    query = select(Wallet).where(Wallet.id == wallet_id)
    result = await db.execute(query)
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    if not wallet.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wallet is inactive")

    # 1. Se Asaas estiver configurado, cria cobrança real no Asaas
    if settings.ASAAS_API_KEY:
        client = AsaasClient(
            api_key=settings.ASAAS_API_KEY,
            base_url=settings.ASAAS_BASE_URL
        )
        try:
            charge = await client.create_pix_charge(
                value=payload.amount,
                description=f"Recarga Carteira ACP #{wallet_id}",
                external_reference=wallet_id,
                customer_name=payload.customer_name,
                customer_cpf_cnpj=payload.customer_cpf_cnpj
            )
        except ValueError as err:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=str(err)
            )
        payment_id = charge["payment_id"]
        copy_paste = charge["copy_paste_payload"]
        encoded_image = charge.get("encoded_image") or ""
        if encoded_image.startswith("data:image"):
            encoded_image = encoded_image.split(",", 1)[-1]
        try:
            png_bytes = base64.b64decode(encoded_image) if encoded_image else render_png_qr(copy_paste)
        except Exception:
            png_bytes = render_png_qr(copy_paste)
        _PIX_QR_CACHE[payment_id] = png_bytes
        qr_terminal = render_terminal_qr(copy_paste)
        qr_url = f"/api/v1/wallets/{wallet_id}/pix-deposit/{payment_id}/qrcode.png"

        return PixDepositResponse(
            payment_id=payment_id,
            wallet_id=wallet_id,
            value=charge["value"],
            copy_paste_payload=copy_paste,
            qr_code_base64=charge.get("encoded_image") or "data:image/png;base64,...",
            qr_code_terminal=qr_terminal,
            qr_code_url=qr_url,
            expiration_date=charge.get("expiration_date") or (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
        )

    # 2. Modo Sandbox / Mock
    payment_id = f"pay_sandbox_{uuid.uuid4().hex[:10]}"
    exp = (datetime.now(timezone.utc) + timedelta(days=1)).isoformat()
    mock_copy_paste = (
        f"00020126580014br.gov.bcb.pix0136{uuid.uuid4()}"
        f"520400005303986540{payload.amount:.2f}5802BR5916ACP Carteira"
        f"6009Sao Paulo62070503***6304ABCD"
    )
    png_bytes = render_png_qr(mock_copy_paste)
    _PIX_QR_CACHE[payment_id] = png_bytes
    mock_qr_b64 = "data:image/png;base64," + base64.b64encode(png_bytes).decode("ascii")
    qr_terminal = render_terminal_qr(mock_copy_paste)
    qr_url = f"/api/v1/wallets/{wallet_id}/pix-deposit/{payment_id}/qrcode.png"

    return PixDepositResponse(
        payment_id=payment_id,
        wallet_id=wallet_id,
        value=round(payload.amount, 2),
        copy_paste_payload=mock_copy_paste,
        qr_code_base64=mock_qr_b64,
        qr_code_terminal=qr_terminal,
        qr_code_url=qr_url,
        expiration_date=exp
    )


@router.get("/{wallet_id}/pix-deposit/{payment_id}/qrcode.png")
async def get_pix_deposit_qr_image(wallet_id: str, payment_id: str):
    """
    Retorna a imagem PNG direta do QR Code de recarga para exibição no navegador.
    """
    png_bytes = _PIX_QR_CACHE.get(payment_id)
    if not png_bytes:
        # Fallback gerado a partir do payment_id se o servidor reiniciou
        png_bytes = render_png_qr(f"PIX_CHARGE_{payment_id}")
    return Response(content=png_bytes, media_type="image/png")


@router.post("/{wallet_id}/debit", response_model=DebitResponse)
async def debit_wallet(wallet_id: str, payload: DebitRequest, db: AsyncSession = Depends(get_db)):
    # 1. Consulta inicial para checar existência e travas prévias
    query = select(Wallet).where(Wallet.id == wallet_id).with_for_update()
    result = await db.execute(query)
    wallet = result.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    if not wallet.is_active:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Wallet is inactive")

    # 2. Trava anti-alucinação: Teto máximo por pedido
    if payload.amount > wallet.max_per_order:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            detail=f"Order amount R$ {payload.amount:.2f} exceeds max allowed per order of R$ {wallet.max_per_order:.2f}"
        )

    # 3. Cálculo da Taxa de Intermediação (Take-rate de 1.5% a 2%)
    platform_fee = round(payload.amount * settings.ACP_PLATFORM_FEE_PCT, 2)
    total_debited = round(payload.amount + platform_fee, 2)

    # 4. Atualização Atômica Condicional com Reset Diário Automático
    today = datetime.now(timezone.utc).date()
    spent_base = case((Wallet.last_spend_date == today, Wallet.spent_today), else_=0.0)

    stmt = (
        update(Wallet)
        .where(
            Wallet.id == wallet_id,
            Wallet.is_active.is_(True),
            Wallet.balance >= total_debited,
            (spent_base + payload.amount) <= Wallet.daily_limit
        )
        .values(
            balance=Wallet.balance - total_debited,
            spent_today=spent_base + payload.amount,
            last_spend_date=today
        )
        .execution_options(synchronize_session="fetch")
    )
    update_res = await db.execute(stmt)

    if update_res.rowcount == 0:
        # A atualização falhou: descobre o motivo exato inspecionando o estado atual
        await db.rollback()
        fresh_res = await db.execute(select(Wallet).where(Wallet.id == wallet_id))
        fresh_wallet = fresh_res.scalar_one_or_none()

        current_spent = 0.0 if not fresh_wallet or fresh_wallet.last_spend_date != today else fresh_wallet.spent_today
        if fresh_wallet and round(current_spent + payload.amount, 2) > fresh_wallet.daily_limit:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
                detail=f"Transaction exceeds daily spend limit of R$ {fresh_wallet.daily_limit:.2f}"
            )
        current_bal = fresh_wallet.balance if fresh_wallet else 0.0
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail=f"Insufficient funds. Required: R$ {total_debited:.2f} (Product: R$ {payload.amount:.2f} + Fee: R$ {platform_fee:.2f}), Available: R$ {current_bal:.2f}"
        )

    # 5. Registro da Transação
    transaction = Transaction(
        wallet_id=wallet.id,
        amount=total_debited,
        platform_fee=platform_fee,
        net_amount=payload.amount,
        type="DEBIT_PURCHASE",
        status="COMPLETED",
        reference_id=payload.reference_id,
        description=payload.description or "Compra autônoma via ACP"
    )
    db.add(transaction)
    await db.commit()
    await db.refresh(wallet)

    return DebitResponse(
        success=True,
        transaction_id=transaction.id,
        amount=payload.amount,
        platform_fee=platform_fee,
        total_debited=total_debited,
        remaining_balance=wallet.balance,
        reference_id=payload.reference_id
    )
