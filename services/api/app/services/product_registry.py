from collections import OrderedDict
from typing import Optional


class ProductRegistry:
    """
    Registro em memória (LRU Cache) para mapear Product IDs às suas URLs canônicas autênticas.
    Resolve o desacoplamento quando clientes MCP enviam apenas o product_id para checkout,
    garantindo que o ACP sempre acesse o path canônico do anúncio ou catálogo.
    """

    def __init__(self, max_size: int = 5000):
        self.max_size = max_size
        self._cache: OrderedDict[str, str] = OrderedDict()

    def _normalize_key(self, product_id: str) -> str:
        clean = product_id.strip().upper()
        if clean.startswith("MLB-"):
            clean = "MLB" + clean[4:]
        return clean

    def register(self, product_id: str, url: str) -> None:
        if not product_id or not url:
            return
        key = self._normalize_key(product_id)
        if key in self._cache:
            self._cache.move_to_end(key)
        self._cache[key] = url
        if len(self._cache) > self.max_size:
            self._cache.popitem(last=False)

    def get_url(self, product_id: str) -> Optional[str]:
        if not product_id:
            return None
        key = self._normalize_key(product_id)
        if key in self._cache:
            self._cache.move_to_end(key)
            return self._cache[key]
        return None


product_registry = ProductRegistry()
