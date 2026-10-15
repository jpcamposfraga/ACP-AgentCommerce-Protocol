import re
from urllib.parse import urlparse, urlunparse

ALLOWED_MELI_DOMAINS = {
    "mercadolivre.com.br",
    "produto.mercadolivre.com.br",
    "www.mercadolivre.com.br",
    "mercadolibre.com",
}


def build_meli_handoff_url(product_id_or_url: str, quantity: int = 1) -> str:
    """
    Gera link direto e higienizado para o carrinho/checkout do Mercado Livre,
    removendo parâmetros maliciosos ou de rastreamento e configurando a quantidade.
    """
    qty = max(1, quantity)

    # 1. Se for uma URL completa
    if product_id_or_url.startswith("http://") or product_id_or_url.startswith("https://"):
        parsed = urlparse(product_id_or_url)
        domain = parsed.netloc.lower()
        if not any(domain == allowed or domain.endswith("." + allowed) for allowed in ALLOWED_MELI_DOMAINS):
            raise ValueError(f"Domínio inválido para handoff Mercado Livre: {domain}")

        clean_url = urlunparse((
            "https",
            parsed.netloc,
            parsed.path,
            "",
            f"quantity={qty}",
            "",
        ))
        return clean_url

    # 2. Se for um ID (ex: MLB-1001 ou MLB1001)
    cleaned_id = product_id_or_url.strip().upper()
    if not re.match(r"^MLB-?\d+", cleaned_id):
        raise ValueError(f"Identificador inválido do Mercado Livre: {product_id_or_url}")

    if not cleaned_id.startswith("MLB-"):
        cleaned_id = "MLB-" + cleaned_id[3:]

    return f"https://produto.mercadolivre.com.br/{cleaned_id}?quantity={qty}"
