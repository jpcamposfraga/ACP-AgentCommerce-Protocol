import logging
from typing import Optional
from playwright.async_api import async_playwright, Browser, BrowserContext, Playwright
from app.core.config import settings

logger = logging.getLogger(__name__)


class BrowserManager:
    """
    Gerencia o ciclo de vida do Chromium assíncrono para o Playwright Checkout Worker.
    Implementa reutilização de browser singleton para evitar overhead de inicialização,
    configuração de locale pt-BR e isolamento de BrowserContexts por pedido.
    """

    _instance: Optional["BrowserManager"] = None
    _playwright: Optional[Playwright] = None
    _browser: Optional[Browser] = None

    def __init__(
        self,
        headless: Optional[bool] = None,
        timeout_seconds: Optional[int] = None
    ):
        self.headless = settings.PLAYWRIGHT_HEADLESS if headless is None else headless
        self.timeout_seconds = settings.PLAYWRIGHT_TIMEOUT_SECONDS if timeout_seconds is None else timeout_seconds

    async def _ensure_browser(self) -> Browser:
        if self._browser is None or not self._browser.is_connected():
            if self._playwright is None:
                pw_cm = await async_playwright()
                self._playwright = await pw_cm.start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
                args=[
                    "--no-sandbox",
                    "--disable-setuid-sandbox",
                    "--disable-dev-shm-usage",
                    "--disable-blink-features=AutomationControlled"
                ]
            )
        return self._browser

    async def create_context(self) -> BrowserContext:
        """
        Cria um novo contexto de navegação isolado com fingerprint brasileiro e viewport padrão.
        """
        browser = await self._ensure_browser()
        context = await browser.new_context(
            viewport={"width": 1280, "height": 800},
            locale="pt-BR",
            timezone_id="America/Sao_Paulo",
            user_agent=(
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/124.0.0.0 Safari/537.36"
            )
        )
        context.set_default_timeout(self.timeout_seconds * 1000)
        return context

    async def close(self):
        """
        Encerra com segurança o browser e o runtime do Playwright.
        """
        if self._browser:
            try:
                await self._browser.close()
            except Exception as e:
                logger.warning(f"Erro ao fechar browser Playwright: {e}")
            finally:
                self._browser = None

        if self._playwright:
            try:
                await self._playwright.stop()
            except Exception as e:
                logger.warning(f"Erro ao parar Playwright: {e}")
            finally:
                self._playwright = None
