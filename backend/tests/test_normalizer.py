from app.crawler import normalize_url


def test_normalize_removes_fragment_and_tracking():
    assert normalize_url('HTTPS://Example.COM/about/?utm_source=x&b=2&a=1#team') == 'https://example.com/about?a=1&b=2'


def test_normalize_default_port_and_trailing_slash():
    assert normalize_url('https://Example.com:443/test/') == 'https://example.com/test'
