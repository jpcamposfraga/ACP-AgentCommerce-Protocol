from typing import Optional
from curl_cffi.requests import AsyncSession
from app.services.scrapers.mercadolivre import RawListing


class ShopifyDiscoveryConnector:
    """
    Conector de Descoberta Nativa e Aberta para lojas Shopify.
    Opera consumindo endpoints públicos JSON (/products.json e /cart/add.js)
    sem depender de nenhum plugin, permissão ou parceria instalada pelo lojista.
    """

    def parse_products_json(self, data: dict, store_domain: str, query: str = "") -> list[RawListing]:
        products = data.get("products", [])
        listings: list[RawListing] = []
        lower_query = query.lower().strip()

        for prod in products:
            title = prod.get("title", "")
            if lower_query and lower_query not in title.lower():
                continue

            handle = prod.get("handle", "")
            url = f"https://{store_domain}/products/{handle}"
            images = prod.get("images", [])
            image_url = images[0].get("src") if images else None

            variants = prod.get("variants", [])
            if not variants:
                continue

            # Prioriza a primeira variante disponível
            first_var = next((v for v in variants if v.get("available", True)), variants[0])
            variant_id = str(first_var.get("id"))
            try:
                price = float(first_var.get("price", 0.0))
            except (ValueError, TypeError):
                price = 0.0

            listings.append(
                RawListing(
                    product_id=variant_id,
                    title=title,
                    url=url,
                    display_price=price,
                    cash_price=None,
                    seller_name=store_domain,
                    seller_reputation="official_store",
                    image_url=image_url
                )
            )

        return listings

    def build_cart_url(self, domain: str, variant_id: str, quantity: int = 1) -> str:
        """
        Gera link direto de checkout / pré-preenchimento de carrinho no padrão universal Shopify.
        """
        clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")
        return f"https://{clean_domain}/cart/{variant_id}:{quantity}"

    async def search_store(self, domain: str, query: str = "", limit: int = 10) -> list[RawListing]:
        clean_domain = domain.replace("https://", "").replace("http://", "").strip("/")
        url = f"https://{clean_domain}/products.json?limit={limit * 2}"
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
            "Accept": "application/json",
        }
        async with AsyncSession(timeout=10.0, headers=headers) as session:
            resp = await session.get(url)
            if resp.status_code == 200:
                data = resp.json()
                listings = self.parse_products_json(data, clean_domain, query)
                return listings[:limit]
            return []
