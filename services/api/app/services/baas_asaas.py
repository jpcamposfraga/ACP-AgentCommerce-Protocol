import re
from typing import Optional
from datetime import datetime, timezone
import httpx


class AsaasClient:
    """
    Cliente oficial assíncrono para a API REST v3 do Asaas BaaS.
    Gerencia emissões de transferências Pix (Cash-out para lojistas)
    e geração de cobranças Pix com QR Code / Copia-e-Cola (Cash-in para carteiras).
    """

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.asaas.com/v3",
        transport: Optional[httpx.BaseTransport] = None
    ):
        self.api_key = api_key.strip()
        self.base_url = base_url.rstrip("/") + "/"
        self.transport = transport

    def _get_client(self) -> httpx.AsyncClient:
        headers = {
            "access_token": self.api_key,
            "Content-Type": "application/json",
            "User-Agent": "AgentCommerceProtocol/1.0",
        }
        return httpx.AsyncClient(
            base_url=self.base_url,
            headers=headers,
            timeout=15.0,
            transport=self.transport
        )

    def detect_pix_key_type(self, pix_key: str) -> str:
        key = pix_key.strip()
        if "@" in key:
            return "EMAIL"

        # UUID / EVP (Chave Aleatória)
        if re.match(r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$", key):
            return "EVP"

        # Limpeza para checagem numérica
        digits = re.sub(r"[^\d]", "", key)

        if key.startswith("+55") or (key.startswith("55") and len(digits) in (12, 13)):
            return "PHONE"

        if len(digits) == 14:
            return "CNPJ"

        if len(digits) == 11:
            if "." in key or "-" in key or digits[2] != "9":
                return "CPF"
            if int(digits[:2]) >= 11 and digits[2] == "9":
                return "PHONE"
            return "CPF"

        if len(digits) == 10:
            return "PHONE"

        return "EVP"

    async def send_pix_transfer(
        self,
        value: float,
        pix_key: str,
        pix_key_type: Optional[str] = None,
        description: str = ""
    ) -> dict:
        key_type = pix_key_type or self.detect_pix_key_type(pix_key)
        payload = {
            "value": round(value, 2),
            "pixAddressKey": pix_key.strip(),
            "pixAddressKeyType": key_type,
            "description": description[:100] if description else "ACP Pix Payout",
            "scheduleDate": None
        }

        async with self._get_client() as client:
            resp = await client.post("transfers", json=payload)
            if resp.status_code not in (200, 201):
                err_text = resp.text
                try:
                    err_json = resp.json()
                    errors = err_json.get("errors", [])
                    if errors:
                        err_text = "; ".join(e.get("description", "") for e in errors)
                except Exception:
                    pass
                raise ValueError(f"Falha ao enviar Pix no Asaas ({resp.status_code}): {err_text}")

            return resp.json()

    async def get_or_create_customer(self, name: str, cpf_cnpj: Optional[str] = None) -> str:
        async with self._get_client() as client:
            payload = {
                "name": name or "Cliente ACP",
                "cpfCnpj": cpf_cnpj
            }
            resp = await client.post("customers", json=payload)
            if resp.status_code in (200, 201):
                return resp.json().get("id", "")
            return "cus_default_acp"

    async def create_pix_charge(
        self,
        value: float,
        description: str,
        external_reference: str,
        customer_name: Optional[str] = "Cliente ACP",
        customer_cpf_cnpj: Optional[str] = None
    ) -> dict:
        async with self._get_client() as client:
            # 1. Cria ou obtém cliente
            cust_payload = {"name": customer_name or "Cliente ACP"}
            if customer_cpf_cnpj:
                cust_payload["cpfCnpj"] = customer_cpf_cnpj

            cust_resp = await client.post("customers", json=cust_payload)
            customer_id = cust_resp.json().get("id", "cus_default") if cust_resp.status_code in (200, 201) else "cus_default"

            # 2. Cria cobrança Pix
            today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
            charge_payload = {
                "customer": customer_id,
                "billingType": "PIX",
                "value": round(value, 2),
                "dueDate": today,
                "description": description[:100],
                "externalReference": external_reference,
                "postalService": False
            }
            resp = await client.post("payments", json=charge_payload)
            if resp.status_code not in (200, 201):
                err_text = resp.text
                try:
                    err_json = resp.json()
                    errors = err_json.get("errors", [])
                    if errors:
                        err_text = "; ".join(e.get("description", "") for e in errors)
                except Exception:
                    pass
                raise ValueError(f"Falha ao gerar cobrança no Asaas ({resp.status_code}): {err_text}")

            payment_data = resp.json()
            payment_id = payment_data.get("id")

            # 3. Busca QR Code e Copia-e-Cola com retry resiliente
            qr_data = {}
            for _ in range(4):
                qr_resp = await client.get(f"payments/{payment_id}/pixQrCode")
                if qr_resp.status_code == 200:
                    qr_data = qr_resp.json()
                    if qr_data.get("payload"):
                        break
                import asyncio
                await asyncio.sleep(0.5)

            return {
                "payment_id": payment_id,
                "value": round(value, 2),
                "copy_paste_payload": qr_data.get("payload", ""),
                "encoded_image": qr_data.get("encodedImage", ""),
                "expiration_date": qr_data.get("expirationDate", "")
            }
