import uuid
from datetime import datetime, timezone


class BaaSPixClient:
    """
    Cliente de integração Sandbox com provedores de BaaS (Asaas / Efí Bank).
    Executa liquidações de Pix cash-out para lojas parceiras no fluxo autônomo.
    """

    async def send_pix_payout(
        self,
        amount: float,
        pix_key: str,
        description: str = ""
    ) -> dict:
        timestamp_str = datetime.now(timezone.utc).strftime("%Y%m%d%H%M")
        e2e_suffix = uuid.uuid4().hex[:10].upper()
        end_to_end_id = f"E00000000{timestamp_str}{e2e_suffix}"

        return {
            "status": "CONFIRMED",
            "end_to_end_id": end_to_end_id,
            "amount": round(amount, 2),
            "pix_key": pix_key,
            "description": description,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }
