from app.services.product_registry import ProductRegistry, product_registry


def test_product_registry_store_and_lookup():
    reg = ProductRegistry(max_size=50)
    reg.register("MLB2096580517", "https://www.mercadolivre.com.br/caderno-desenho/p/MLB2096580517")

    # Lookup by identical ID
    assert reg.get_url("MLB2096580517") == "https://www.mercadolivre.com.br/caderno-desenho/p/MLB2096580517"

    # Lookup by hyphenated ID
    assert reg.get_url("MLB-2096580517") == "https://www.mercadolivre.com.br/caderno-desenho/p/MLB2096580517"

    # Lookup by lowercase
    assert reg.get_url("mlb-2096580517") == "https://www.mercadolivre.com.br/caderno-desenho/p/MLB2096580517"


def test_product_registry_evicts_oldest_when_exceeding_max_size():
    reg = ProductRegistry(max_size=3)
    reg.register("ID1", "https://example.com/1")
    reg.register("ID2", "https://example.com/2")
    reg.register("ID3", "https://example.com/3")
    reg.register("ID4", "https://example.com/4")

    assert reg.get_url("ID1") is None
    assert reg.get_url("ID2") == "https://example.com/2"
    assert reg.get_url("ID4") == "https://example.com/4"


def test_singleton_instance_is_available():
    assert isinstance(product_registry, ProductRegistry)
