from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field, ConfigDict


class ShippingProfileCreate(BaseModel):
    wallet_id: str = Field(..., description="ID da carteira vinculada ao perfil de entrega")
    recipient_name: str = Field(..., min_length=2, description="Nome completo do destinatário da encomenda")
    cpf_cnpj: str = Field(..., min_length=11, description="CPF ou CNPJ para emissão obrigatória de NF-e")
    phone: str = Field(..., min_length=8, description="Telefone / WhatsApp com DDD para contato da transportadora")
    postal_code: str = Field(..., min_length=8, description="CEP do endereço de entrega")
    street: Optional[str] = Field(default="", description="Logradouro (Rua, Avenida, etc.)")
    number: str = Field(..., min_length=1, description="Número do imóvel")
    complement: Optional[str] = Field(default=None, description="Complemento (Apto, Bloco, Sala, etc.)")
    neighborhood: Optional[str] = Field(default="", description="Bairro")
    city: Optional[str] = Field(default="", description="Cidade")
    state: Optional[str] = Field(default="", description="Estado (UF - 2 letras)")
    is_default: bool = Field(default=True, description="Define se é o endereço principal de entrega")


class ShippingProfileUpdate(BaseModel):
    recipient_name: Optional[str] = None
    phone: Optional[str] = None
    street: Optional[str] = None
    number: Optional[str] = None
    complement: Optional[str] = None
    neighborhood: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    is_default: Optional[bool] = None


class ShippingProfileResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    wallet_id: str
    recipient_name: str
    cpf_cnpj: str
    phone: str
    postal_code: str
    street: str
    number: str
    complement: Optional[str] = None
    neighborhood: str
    city: str
    state: str
    is_default: bool
    created_at: datetime
