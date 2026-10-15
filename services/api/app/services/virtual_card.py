import uuid
import random
from datetime import datetime, timezone, timedelta
from app.schemas.checkout import VirtualCardDetails


class VirtualCardService:
    """
    Motor de Emissão de Cartões Virtuais Efêmeros (One-Time Virtual Cards).
    Permite liquidação financeira autônoma de agentes em lojas abertas globais
    (Shopify, WooCommerce, Stripe, varejo internacional) com saldo estritamente travado
    no valor do pedido, impedindo cobranças indevidas ou sobretaxas.
    """

    async def issue_ephemeral_card(
        self,
        amount: float,
        currency: str = "BRL",
        merchant_domain: str = "",
        wallet_id: str = ""
    ) -> VirtualCardDetails:
        card_token = f"vcard_{uuid.uuid4().hex}"
        # Gera PAN simulado padrão BIN Visa comercial
        last_4 = f"{random.randint(1000, 9999)}"
        masked_pan = f"4111********{last_4}"
        cvv = f"{random.randint(100, 999)}"
        
        # Validade de 2 meses para liquidação segura
        exp_date = datetime.now(timezone.utc) + timedelta(days=60)
        expiration = exp_date.strftime("%m/%y")

        return VirtualCardDetails(
            card_token=card_token,
            masked_pan=masked_pan,
            cvv=cvv,
            expiration=expiration,
            exact_amount_locked=round(amount, 2),
            currency=currency.upper(),
            merchant_domain=merchant_domain,
            status="ACTIVE_ONE_TIME"
        )
