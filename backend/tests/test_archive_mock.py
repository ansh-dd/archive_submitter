from app.archive import MockProvider


def test_mock_provider_is_explicit_demo_capture():
    result = MockProvider().submit('https://example.com/')
    assert result.success is True
    assert result.archive_identifier == 'LOCAL-DEMO'
    assert 'example.invalid' in result.archive_url
