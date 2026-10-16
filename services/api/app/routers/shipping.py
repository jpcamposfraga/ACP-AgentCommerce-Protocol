from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.models.wallet import Wallet
from app.models.shipping import ShippingProfile
from app.schemas.shipping import ShippingProfileCreate, ShippingProfileUpdate, ShippingProfileResponse
from app.services.viacep import ViaCepClient

router = APIRouter(prefix="/api/v1/shipping-profiles", tags=["Shipping Profiles"])
viacep_client = ViaCepClient()


@router.post("", response_model=ShippingProfileResponse, status_code=status.HTTP_201_CREATED)
async def create_shipping_profile(
    payload: ShippingProfileCreate,
    db: AsyncSession = Depends(get_db)
):
    # 1. Verifica se a carteira existe
    w_stmt = select(Wallet).where(Wallet.id == payload.wallet_id)
    w_res = await db.execute(w_stmt)
    wallet = w_res.scalar_one_or_none()
    if not wallet:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Wallet not found")

    # 2. Se logradouro ou cidade não foram preenchidos, consulta ViaCEP
    street = payload.street
    neighborhood = payload.neighborhood
    city = payload.city
    state = payload.state

    if not street or not city:
        cep_data = await viacep_client.lookup(payload.postal_code)
        if cep_data:
            street = street or cep_data.get("street", "")
            neighborhood = neighborhood or cep_data.get("neighborhood", "")
            city = city or cep_data.get("city", "")
            state = state or cep_data.get("state", "")

    # 3. Se for default, desmarca outros perfis da mesma carteira
    if payload.is_default:
        await db.execute(
            update(ShippingProfile)
            .where(ShippingProfile.wallet_id == payload.wallet_id)
            .values(is_default=False)
        )

    profile = ShippingProfile(
        wallet_id=payload.wallet_id,
        recipient_name=payload.recipient_name,
        cpf_cnpj=payload.cpf_cnpj,
        phone=payload.phone,
        postal_code=payload.postal_code,
        street=street or "Não informado",
        number=payload.number,
        complement=payload.complement,
        neighborhood=neighborhood or "Centro",
        city=city or "Não informado",
        state=state or "SP",
        is_default=payload.is_default
    )
    db.add(profile)
    await db.commit()
    await db.refresh(profile)
    return profile


@router.get("/wallet/{wallet_id}", response_model=list[ShippingProfileResponse])
async def list_shipping_profiles_by_wallet(
    wallet_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = (
        select(ShippingProfile)
        .where(ShippingProfile.wallet_id == wallet_id)
        .order_by(ShippingProfile.is_default.desc(), ShippingProfile.created_at.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()


@router.get("/{profile_id}", response_model=ShippingProfileResponse)
async def get_shipping_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ShippingProfile).where(ShippingProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de entrega não encontrado")
    return profile


@router.patch("/{profile_id}/default", response_model=ShippingProfileResponse)
async def set_default_shipping_profile(
    profile_id: str,
    db: AsyncSession = Depends(get_db)
):
    stmt = select(ShippingProfile).where(ShippingProfile.id == profile_id)
    result = await db.execute(stmt)
    profile = result.scalar_one_or_none()
    if not profile:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Perfil de entrega não encontrado")

    # Desmarca outros da mesma carteira
    await db.execute(
        update(ShippingProfile)
        .where(ShippingProfile.wallet_id == profile.wallet_id)
        .values(is_default=False)
    )
    profile.is_default = True
    await db.commit()
    await db.refresh(profile)
    return profile
