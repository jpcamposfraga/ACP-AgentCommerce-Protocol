import re
from urllib.parse import urlparse, urlunparse
from app.services.product_registry import product_registry

ALLOWED_MELI_DOMAINS = {
    "mercadolivre.com.br",
    "produto.mercadolivre.com.br",
    "www.mercadolivre.com.br",
    "mercadolibre.com",
}


def build_meli_handoff_url(product_id_or_url: str, quantity: int = 1) -> str:
    """
    Gera link direto e higienizado para a página canônica do produto no Mercado Livre,
    removendo parâmetros de rastreamento ou fragments (#polycard_client...) e sem injetar
    parâmetros que causam erro 404 / bloqueio do WAF (como ?quantity=1).
    Se receber apenas o ID, tenta resolver via ProductRegistry para recuperar o link autêntico.
    """
    target = product_id_or_url.strip()

    # 1. Se for uma URL completa HTTP / HTTPS
    if target.startswith("http://") or target.startswith("https://"):
        parsed = urlparse(target)
        domain = parsed.netloc.lower()
        if not any(domain == allowed or domain.endswith("." + allowed) for allowed in ALLOWED_MELI_DOMAINS):
            raise ValueError(f"Domínio inválido para handoff Mercado Livre: {domain}")

        # Retorna URL canônica limpa (esquema, domínio e caminho), descartando query e fragmentos
        return urlunparse((
            "https",
            parsed.netloc,
            parsed.path,
            "",
            "",
            "",
        ))

    # 2. Se for um ID, primeiro tenta resolver no ProductRegistry (cache de busca real)
    cached_url = product_registry.get_url(target)
    if cached_url:
        return build_meli_handoff_url(cached_url, quantity=quantity)

    # 3. Fallback se não estiver no registro
    cleaned_id = target.upper()
    if not re.match(r"^MLB-?\d+", cleaned_id):
        raise ValueError(f"Identificador inválido do Mercado Livre: {product_id_or_url}")

    digits = re.sub(r"[^\d]", "", cleaned_id)

    # Se for catálogo (formato MLB seguido de 8 a 11 dígitos sem hífen original)
    if not cleaned_id.startswith("MLB-") and len(digits) >= 8:
        return f"https://www.mercadolivre.com.br/p/MLB{digits}"

    # Se for item padrão com hífen
    standard_id = cleaned_id if cleaned_id.startswith("MLB-") else f"MLB-{digits}"
    return f"https://produto.mercadolivre.com.br/{standard_id}"
