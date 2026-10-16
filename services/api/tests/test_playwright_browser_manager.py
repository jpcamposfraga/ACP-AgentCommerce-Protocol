import pytest
from app.services.checkout_worker.browser_manager import BrowserManager
from app.core.config import settings


@pytest.mark.asyncio
async def test_browser_manager_settings_and_init():
    manager = BrowserManager()
    assert manager.timeout_seconds == settings.PLAYWRIGHT_TIMEOUT_SECONDS
    assert manager.headless == settings.PLAYWRIGHT_HEADLESS


@pytest.mark.asyncio
async def test_browser_manager_context_lifecycle(monkeypatch):
    class MockPage:
        async def close(self):
            pass

    class MockContext:
        def __init__(self):
            self.closed = False

        def set_default_timeout(self, timeout):
            pass

        async def new_page(self):
            return MockPage()

        async def close(self):
            self.closed = True

    class MockBrowser:
        def __init__(self):
            self.closed = False

        async def new_context(self, **kwargs):
            return MockContext()

        async def close(self):
            self.closed = True

    class MockChromium:
        async def launch(self, **kwargs):
            return MockBrowser()

    class MockPlaywright:
        def __init__(self):
            self.chromium = MockChromium()

        async def stop(self):
            pass

    async def mock_async_playwright():
        class ContextManager:
            async def start(self):
                return MockPlaywright()

        return ContextManager()

    monkeypatch.setattr(
        "app.services.checkout_worker.browser_manager.async_playwright",
        mock_async_playwright
    )

    manager = BrowserManager()
    context = await manager.create_context()
    assert context is not None
    await manager.close()
