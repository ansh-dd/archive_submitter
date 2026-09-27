"""JavaScript page renderer using Playwright."""

from __future__ import annotations

import asyncio

from .security import assert_public_http_url


async def render_html(url: str) -> str:

    # Security check before opening the URL.
    assert_public_http_url(url)

    try:
        from playwright.async_api import async_playwright

    except ImportError as exc:

        raise RuntimeError(
            "Playwright is not installed. "
            "Install requirements-playwright.txt "
            "and run playwright install chromium."
        ) from exc


    async with async_playwright() as p:

        browser = await p.chromium.launch(
            headless=True
        )

        try:

            page = await browser.new_page(
                viewport={
                    "width": 1366,
                    "height": 768
                }
            )

            # Do NOT use networkidle for sites such as YouTube.
            await page.goto(
                url,
                wait_until="domcontentloaded",
                timeout=30000
            )

            # Give JavaScript time to create the page.
            await page.wait_for_timeout(3000)

            # Wait briefly for links to appear.
            try:

                await page.wait_for_selector(
                    "a[href]",
                    timeout=8000
                )

            except Exception:
                pass


            # Scroll a few times so lazy-loaded public content
            # has a chance to appear.
            for _ in range(3):

                await page.evaluate(
                    """
                    window.scrollTo(
                        0,
                        document.body.scrollHeight
                    )
                    """
                )

                await page.wait_for_timeout(1200)


            # Return the fully rendered DOM.
            html = await page.content()

            return html

        finally:

            await browser.close()