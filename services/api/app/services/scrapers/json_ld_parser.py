import json
import re
from typing import Optional
from selectolax.lexbor import LexborHTMLParser
from app.services.scrapers.mercadolivre import RawListing


class JsonLdUniversalExtractor:
    """
    Extrator Universal de Microdados Semânticos Schema.org/Product.
    Permite raspar e indexar preços e disponibilidade em qualquer e-commerce
    (WooCommerce, Magento, VTEX, sites customizados) a partir de tags <script type="application/ld+json">.
    """

    def extract_from_html(self, html: str, base_url: str = "") -> list[RawListing]:
        parser = LexborHTMLParser(html)
        scripts = parser.css('script[type="application/ld+json"]')
        listings: list[RawListing] = []

        for script in scripts:
            raw_text = script.text(strip=True)
            if not raw_text:
                continue

            try:
                data = json.loads(raw_text)
            except json.JSONDecodeError:
                continue

            # Suporta tanto objeto único quanto listas ou grafos @graph
            items_to_check = []
            if isinstance(data, list):
                items_to_check.extend(data)
            elif isinstance(data, dict):
                if "@graph" in data and isinstance(data["@graph"], list):
                    items_to_check.extend(data["@graph"])
                else:
                    items_to_check.append(data)

            for node in items_to_check:
                if not isinstance(node, dict):
                    continue

                type_val = node.get("@type", "")
                if type_val != "Product" and not (isinstance(type_val, list) and "Product" in type_val):
                    continue

                title = node.get("name") or node.get("headline") or ""
                if not title:
                    continue

                sku = str(node.get("sku") or node.get("productID") or node.get("gtin") or "PROD-GENERIC")
                url = node.get("url") or base_url
                images = node.get("image")
                image_url = None
                if isinstance(images, list) and images:
                    image_url = images[0] if isinstance(images[0], str) else images[0].get("url")
                elif isinstance(images, str):
                    image_url = images
                elif isinstance(images, dict):
                    image_url = images.get("url")

                # Ofertas de preço
                offers = node.get("offers", {})
                price = 0.0
                if isinstance(offers, dict):
                    price_val = offers.get("price") or offers.get("lowPrice")
                    try:
                        price = float(price_val)
                    except (ValueError, TypeError):
                        price = 0.0
                elif isinstance(offers, list) and offers:
                    first_offer = offers[0]
                    if isinstance(first_offer, dict):
                        try:
                            price = float(first_offer.get("price", 0.0))
                        except (ValueError, TypeError):
                            price = 0.0

                listings.append(
                    RawListing(
                        product_id=sku,
                        title=title,
                        url=url,
                        display_price=price,
                        cash_price=None,
                        seller_name="open_store",
                        seller_reputation="standard",
                        image_url=image_url
                    )
                )

        return listings
