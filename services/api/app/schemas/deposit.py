from typing import Optional
from pydantic import BaseModel, Field


class PixDepositRequest(BaseModel):
    amount: float = Field(..., gt=0, description="Valor em Reais a ser recarregado na carteira")
    customer_name: Optional[str] = Field(default="Cliente ACP", description="Nome do titular pagador")
    customer_cpf_cnpj: Optional[str] = Field(default=None, description="CPF ou CNPJ do pagador (opcional)")


class PixDepositResponse(BaseModel):
    payment_id: str = Field(..., description="ID da cobrança Pix no provedor BaaS")
    wallet_id: str = Field(..., description="ID da carteira que receberá o crédito")
    value: float = Field(..., description="Valor nominal da recarga")
    copy_paste_payload: str = Field(..., description="Código Pix Copia-e-Cola (padrão EMV QRCPS)")
    qr_code_base64: str = Field(..., description="QR Code em imagem codificada Base64")
    qr_code_terminal: str = Field(default="", description="QR Code desenhado em blocos UTF-8 para terminal ou chat")
    qr_code_url: str = Field(default="", description="URL HTTP direta para visualização da imagem PNG no navegador")
    expiration_date: str = Field(..., description="Data/hora de expiração do QR Code")
