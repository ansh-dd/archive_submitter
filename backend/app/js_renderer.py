"""Optional JavaScript renderer.

Install backend/requirements-playwright.txt and run `playwright install chromium`, then set
ENABLE_PLAYWRIGHT=true. The core crawler works without this module.
"""
from __future__ import annotations
from .security import assert_public_http_url


async def render_html(url: str) -> str:
    assert_public_http_url(url)
    try:
        from playwright.async_api import async_playwright
    except ImportError as exc:
        raise RuntimeError('Playwright is not installed. See requirements-playwright.txt.') from exc
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        await page.goto(url, wait_until='networkidle', timeout=30000)
        html = await page.content()
        await browser.close()
        return html
