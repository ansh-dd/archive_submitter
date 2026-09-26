import pytest
from app.security import assert_public_http_url


@pytest.mark.parametrize('url', [
    'http://127.0.0.1',
    'http://localhost',
    'http://[::1]',
    'ftp://example.com/file',
    'file:///etc/passwd',
])
def test_private_or_unsupported_urls_are_rejected(url):
    with pytest.raises(ValueError):
        assert_public_http_url(url)


def test_embedded_credentials_rejected():
    with pytest.raises(ValueError):
        assert_public_http_url('https://user:pass@example.com/')
