import pytest
from app.services.checkout_worker.pix_extractor import PixExtractor
from app.services.checkout_worker.strategies.generic import GenericGuestCheckoutStrategy
from app.services.checkout_worker.strategies.nuvemshop import NuvemshopCheckoutStrategy
from app.models.shipping import ShippingProfile


def test_pix_extractor_extracts_emv_payload_from_textarea():
    html_sample = """
    <div class="pix-container">
      <h3>Pague com Pix</h3>
      <textarea id="pix-copy-paste">00020126580014br.gov.bcb.pix0136123e4567-e89b-12d3-a456-42661417400052040000530398654010.005802BR5913Loja Exemplo6009SAO PAULO62070503***6304ABCD</textarea>
    </div>
    """
    code = PixExtractor.extract_payload(html_sample)
    assert code is not None
    assert code.startswith("00020126580014br.gov.bcb.pix")
    assert "6304ABCD" in code


def test_pix_extractor_extracts_payload_from_button_attribute():
    html_sample = """
    <button class="btn-copy" data-clipboard-text="00020126580014br.gov.bcb.pix0136abc-def-ghi52040000530398654050.005802BR5910Loja Teste6009SAO PAULO62070503***63041234">
      Copiar Código Pix
    </button>
    """
    code = PixExtractor.extract_payload(html_sample)
    assert code is not None
    assert "br.gov.bcb.pix" in code


def test_pix_extractor_returns_none_when_no_pix_found():
    html_sample = "<div><p>Obrigado pelo seu pedido. Enviaremos os detalhes por e-mail.</p></div>"
    assert PixExtractor.extract_payload(html_sample) is None


@pytest.mark.asyncio
async def test_generic_strategy_fill_and_submit():
    calls = []

    class MockLocator:
        def __init__(self, selector):
            self.selector = selector

        async def fill(self, value):
            calls.append(("fill", self.selector, value))

        async def click(self):
            calls.append(("click", self.selector))

        async def count(self):
            return 1

    class MockPage:
        def locator(self, selector):
            return MockLocator(selector)

        async def wait_for_timeout(self, ms):
            pass

        async def content(self):
            return """
            <div id="pix-wrapper">
              <span class="brcode">00020126580014br.gov.bcb.pix0136test-payload52040000530398654010.005802BR5910Loja6009SP62070503***63049999</span>
            </div>
            """

    profile = ShippingProfile(
        recipient_name="Carlos Eduardo",
        cpf_cnpj="12345678909",
        phone="11999998888",
        postal_code="01310-100",
        street="Avenida Paulista",
        number="1500",
        complement="Apto 42",
        neighborhood="Bela Vista",
        city="São Paulo",
        state="SP"
    )

    strategy = GenericGuestCheckoutStrategy()
    page = MockPage()
    await strategy.fill_shipping(page, profile)
    assert any(c[0] == "fill" and "Carlos Eduardo" in str(c[2]) for c in calls)
    assert any(c[0] == "fill" and "12345678909" in str(c[2]) for c in calls)

    pix_code = await strategy.select_pix_and_submit(page)
    assert pix_code is not None
    assert "br.gov.bcb.pix" in pix_code
