from __future__ import annotations
from dataclasses import dataclass
from urllib.parse import quote
import re
import httpx

from .config import settings


@dataclass
class ArchiveResult:
    success: bool
    archive_url: str | None = None
    archive_identifier: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    error: str | None = None


class ArchiveProvider:
    name = 'base'

    def submit(self, url: str) -> ArchiveResult:
        raise NotImplementedError


class WaybackProvider(ArchiveProvider):
    name = 'wayback'

    def submit(self, url: str) -> ArchiveResult:
        endpoint = f"{settings.wayback_save_base}{quote(url, safe=':/?=&%#;+,@')}"
        try:
            # This integration intentionally does not bypass authentication, CAPTCHA, or rate limits.
            with httpx.Client(timeout=45, follow_redirects=False, headers={'User-Agent': settings.user_agent}) as client:
                response = client.post(endpoint)
            if response.status_code in {200, 201, 302}:
                location = response.headers.get('content-location') or response.headers.get('location')
                archive_url = None
                if location:
                    if location.startswith('http'):
                        archive_url = location
                    elif location.startswith('/'):
                        archive_url = f'https://web.archive.org{location}'
                    else:
                        archive_url = f'https://web.archive.org/{location}'
                if not archive_url:
                    match = re.search(r'https?://web\.archive\.org/web/[^\s"<]+', response.text)
                    archive_url = match.group(0) if match else None
                return ArchiveResult(True, archive_url=archive_url, archive_identifier=location, http_status=response.status_code)
            code = f'HTTP_{response.status_code}'
            message = f'Wayback submission returned HTTP {response.status_code}.'
            if response.status_code in {401, 403, 429}:
                message += ' No authentication/rate-limit/CAPTCHA bypass is attempted.'
            return ArchiveResult(False, http_status=response.status_code, error_code=code, error=message)
        except httpx.TimeoutException as exc:
            return ArchiveResult(False, error_code='TIMEOUT', error=str(exc))
        except httpx.HTTPError as exc:
            return ArchiveResult(False, error_code='NETWORK_ERROR', error=str(exc))


class MockProvider(ArchiveProvider):
    name = 'mock'

    def submit(self, url: str) -> ArchiveResult:
        # Development/demo provider only. It does NOT create a public archive.
        return ArchiveResult(
            True,
            archive_url=f'https://example.invalid/mock-archive?url={quote(url, safe="")}',
            archive_identifier='LOCAL-DEMO',
            http_status=200,
        )


def get_provider(name: str | None = None) -> ArchiveProvider:
    selected = (name or settings.archive_provider).lower()
    if selected == 'mock':
        return MockProvider()
    if selected == 'wayback':
        return WaybackProvider()
    raise ValueError(f'Unsupported archive provider: {selected}')
