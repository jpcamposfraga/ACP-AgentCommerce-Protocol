import re
from typing import Optional
import httpx


class ViaCepClient:
    """
    Cliente assíncrono para consulta e validação de CEP na API pública gratuita do ViaCEP.
    Permite auto-completar logradouro, bairro, cidade e UF sem erros de digitação.
    """

    def __init__(self, timeout: float = 5.0):
        self.timeout = timeout

    async def lookup(self, cep: str) -> dict:
        clean_cep = re.sub(r"[^\d]", "", cep)
        if len(clean_cep) != 8:
            return {}

        url = f"https://viacep.com.br/ws/{clean_cep}/json/"
        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                resp = await client.get(url)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("erro"):
                        return {}
                    return {
                        "postal_code": data.get("cep", cep),
                        "street": data.get("logradouro", ""),
                        "neighborhood": data.get("bairro", ""),
                        "city": data.get("localidade", ""),
                        "state": data.get("uf", ""),
                        "complement": data.get("complemento", "")
                    }
            except Exception:
                # Falha graciosa de rede não bloqueia o fluxo do usuário
                return {}
        return {}
