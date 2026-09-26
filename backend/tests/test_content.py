from app.content import stable_content_hash


def test_html_hash_ignores_whitespace_and_script_changes():
    a = b'<html><body><h1>Hello world</h1><script>var a=1</script></body></html>'
    b = b'<html><body>  <h1>Hello   world</h1> <script>var a=999</script></body></html>'
    assert stable_content_hash(a, 'text/html') == stable_content_hash(b, 'text/html')


def test_content_change_changes_hash():
    a = b'<html><body>Hello</body></html>'
    b = b'<html><body>Hello updated</body></html>'
    assert stable_content_hash(a, 'text/html') != stable_content_hash(b, 'text/html')
