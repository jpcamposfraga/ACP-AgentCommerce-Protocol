import re
from typing import Optional
from urllib.parse import quote, urlsplit, urlunsplit
from curl_cffi.requests import AsyncSession
from selectolax.lexbor import LexborHTMLParser
from app.services.scrapers.base import BaseScraper, RawListing


def clean_meli_url(raw_url: str) -> str:
    """
    Higieniza a URL do Mercado Livre descartando fragmentos (#polycard_client...)
    e parâmetros internos de rastreamento de busca (&tracking_id, &sid, &searchVariation, etc.),
    preservando o domínio original e o path canônico (/p/MLB... ou produto.mercadolivre.com.br/MLB-...).
    """
    if not raw_url:
        return ""
    parts = urlsplit(raw_url)
    return urlunsplit((parts.scheme or "https", parts.netloc, parts.path, "", ""))


class MercadoLivreScraper(BaseScraper):
    """
    Scraper de alto desempenho para o Mercado Livre utilizando
    curl_cffi (evasão TLS fingerprint Chrome 124) e selectolax (parser HTML Lexbor em C).
    """

    domain = "mercadolivre.com.br"
    region = "BR"
    currency = "BRL"
    execution_type = "human_handoff"
    is_verified = True

    def parse_price(self, text: str) -> Optional[float]:
        if not text:
            return None
        cleaned = re.sub(r"[^\d,\.]", "", text).strip()
        if not cleaned:
            return None
        if "," in cleaned and "." in cleaned:
            cleaned = cleaned.replace(".", "").replace(",", ".")
        elif "," in cleaned:
            cleaned = cleaned.replace(",", ".")
        elif "." in cleaned:
            parts = cleaned.split(".")
            if len(parts[-1]) == 3:
                cleaned = "".join(parts)
        try:
            return float(cleaned)
        except ValueError:
            return None

    def parse_search_results(self, html: str, limit: int = 10) -> list[RawListing]:
        parser = LexborHTMLParser(html)
        items = parser.css(".ui-search-layout__item")
        if not items:
            items = parser.css(".poly-card")
        listings: list[RawListing] = []

        for item in items:
            if len(listings) >= limit:
                break

            link_el = item.css_first("a.poly-component__title") or item.css_first("a.ui-search-link") or item.css_first("a")
            if not link_el:
                continue

            url = clean_meli_url(link_el.attributes.get("href", ""))
            title_el = item.css_first(".ui-search-item__title")
            title = title_el.text(strip=True) if title_el else link_el.text(strip=True) or link_el.attributes.get("title", "")
            if not title:
                continue

            id_match = re.search(r"(MLB-?\d+)", url, re.IGNORECASE)
            product_id = id_match.group(1).upper() if id_match else f"MLB-{len(listings)+1}"

            fraction_el = item.css_first(".andes-money-amount__fraction")
            fraction_text = fraction_el.text(strip=True) if fraction_el else ""
            cents_el = item.css_first(".andes-money-amount__cents")
            cents_text = cents_el.text(strip=True) if cents_el else ""

            if fraction_text:
                full_price_str = f"{fraction_text},{cents_text}" if cents_text else fraction_text
                display_price = self.parse_price(full_price_str) or 0.0
            else:
                display_price = 0.0

            cash_price = None
            pix_el = item.css_first(".ui-search-price__discount-payment") or item.css_first(".poly-component__discount-payment")
            if pix_el:
                pix_text = pix_el.text(strip=True)
                pix_match = re.search(r"R\$\s*([\d\.,]+)", pix_text)
                if pix_match:
                    cash_price = self.parse_price(pix_match.group(1))

            official_el = item.css_first(".ui-search-official-store-label")
            seller_info_el = item.css_first(".ui-search-item__seller-info") or item.css_first(".poly-component__seller")

            if official_el:
                seller_name = official_el.text(strip=True)
                seller_reputation = "official_store"
            elif seller_info_el:
                seller_name = seller_info_el.text(strip=True)
                info_lower = seller_name.lower()
                if "platinum" in info_lower:
                    seller_reputation = "platinum"
                elif "gold" in info_lower:
                    seller_reputation = "gold"
                elif "líder" in info_lower or "lider" in info_lower:
                    seller_reputation = "leader"
                elif "novo" in info_lower:
                    seller_reputation = "new"
                else:
                    seller_reputation = "standard"
            else:
                seller_name = ""
                seller_reputation = "standard"

            img_el = item.css_first("img.poly-component__picture") or item.css_first("img.ui-search-result-image__element") or item.css_first("img")
            image_url = img_el.attributes.get("src") or img_el.attributes.get("data-src") if img_el else None

            listings.append(
                RawListing(
                    product_id=product_id,
                    title=title,
                    url=url,
                    display_price=display_price,
                    cash_price=cash_price,
                    seller_name=seller_name,
                    seller_reputation=seller_reputation,
                    image_url=image_url,
                )
            )

        return listings

    async def search(self, query: str, limit: int = 10) -> list[RawListing]:
        encoded_query = quote(query)
        url = f"https://lista.mercadolivre.com.br/{encoded_query}"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9",
        }
        async with AsyncSession(timeout=10.0, headers=headers) as session:
            resp = await session.get(url)
            return self.parse_search_results(resp.text, limit=limit)
