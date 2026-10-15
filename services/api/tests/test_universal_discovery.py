import pytest
from app.services.scrapers.mercadolivre import RawListing

def test_shopify_discovery_extracts_products_from_json():
    from app.services.scrapers.shopify_discovery import ShopifyDiscoveryConnector
    sample_shopify_json = {
        "products": [
            {
                "id": 101,
                "title": "Caderno Desenho Artístico A4 200g",
                "handle": "caderno-desenho-artistico-a4",
                "variants": [
                    {"id": 501, "price": "38.50", "available": True}
                ],
                "images": [{"src": "https://img.cdn/art.jpg"}]
            }
        ]
    }
    connector = ShopifyDiscoveryConnector()
    results = connector.parse_products_json(sample_shopify_json, store_domain="artstore.com.br")
    assert len(results) == 1
    assert results[0].title == "Caderno Desenho Artístico A4 200g"
    assert results[0].display_price == 38.50
    assert results[0].product_id == "501"
    cart_url = connector.build_cart_url("artstore.com.br", "501", 2)
    assert cart_url == "https://artstore.com.br/cart/501:2"

def test_json_ld_extractor_extracts_product_microdata():
    from app.services.scrapers.json_ld_parser import JsonLdUniversalExtractor
    sample_html = '''
    <html>
      <head>
        <script type="application/ld+json">
        {
          "@context": "https://schema.org/",
          "@type": "Product",
          "name": "Bloco Desenho 20 Folhas 180g",
          "sku": "CANSON-180",
          "offers": {
            "@type": "Offer",
            "price": "27.90",
            "priceCurrency": "BRL",
            "availability": "https://schema.org/InStock"
          }
        }
        </script>
      </head>
      <body></body>
    </html>
    '''
    extractor = JsonLdUniversalExtractor()
    listings = extractor.extract_from_html(sample_html, base_url="https://lojadepapel.com.br/produto/1")
    assert len(listings) == 1
    assert listings[0].title == "Bloco Desenho 20 Folhas 180g"
    assert listings[0].display_price == 27.90
    assert listings[0].product_id == "CANSON-180"
