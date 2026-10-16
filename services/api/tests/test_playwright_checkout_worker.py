import pytest
from app.services.checkout_worker.orchestrator import PlaywrightCheckoutWorker, CheckoutWorkerResult
from app.models.shipping import ShippingProfile


@pytest.mark.asyncio
async def test_worker_success_flow(monkeypatch):
    class MockPage:
        async def goto(self, url, **kwargs):
            pass

        async def close(self):
            pass

        async def screenshot(self, path):
            pass

    class MockContext:
        async def new_page(self):
            return MockPage()

        async def close(self):
            pass

    class MockBrowserManager:
        async def create_context(self):
            return MockContext()

    class MockStrategy:
        async def add_to_cart_and_proceed(self, page, quantity):
            return True

        async def fill_shipping(self, page, profile):
            return True

        async def select_pix_and_submit(self, page):
            return "00020126580014br.gov.bcb.pix0136test-extracted-code5802BR6304ABCD"

    worker = PlaywrightCheckoutWorker(browser_manager=MockBrowserManager())
    worker.get_strategy = lambda domain: MockStrategy()

    profile = ShippingProfile(
        recipient_name="Mariana Souza",
        cpf_cnpj="12345678909",
        phone="11988887777",
        postal_code="01310-100",
        street="Rua Augusta",
        number="500",
        neighborhood="Consolação",
        city="São Paulo",
        state="SP"
    )

    result = await worker.execute(
        url="https://loja-aberta-exemplo.com.br/produto-123",
        quantity=1,
        profile=profile
    )

    assert result.status == "SUCCESS"
    assert result.pix_copia_e_cola.startswith("00020126")
    assert "br.gov.bcb.pix" in result.pix_copia_e_cola
    assert result.order_id is not None


@pytest.mark.asyncio
async def test_worker_captures_screenshot_on_failure(monkeypatch):
    screenshot_paths = []

    class MockPage:
        async def goto(self, url, **kwargs):
            raise RuntimeError("Conexão recusada pelo servidor da loja")

        async def close(self):
            pass

        async def screenshot(self, path):
            screenshot_paths.append(path)

    class MockContext:
        async def new_page(self):
            return MockPage()

        async def close(self):
            pass

    class MockBrowserManager:
        async def create_context(self):
            return MockContext()

    worker = PlaywrightCheckoutWorker(browser_manager=MockBrowserManager())
    profile = ShippingProfile(
        recipient_name="Teste",
        cpf_cnpj="12345678909",
        phone="11999998888",
        postal_code="01310-100",
        street="Rua Augusta",
        number="500",
        neighborhood="Consolação",
        city="São Paulo",
        state="SP"
    )

    result = await worker.execute(
        url="https://loja-falha.com.br/item",
        quantity=1,
        profile=profile
    )

    assert result.status == "FAILED"
    assert "Conexão recusada" in result.error_message
    assert len(screenshot_paths) >= 1
    assert "checkout_failures" in screenshot_paths[0]
