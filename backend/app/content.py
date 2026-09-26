from __future__ import annotations
import hashlib
import re
from bs4 import BeautifulSoup


def stable_content_hash(content: bytes, content_type: str | None = None) -> str:
    """Hash meaningful page content so incremental scans can identify changes.

    For HTML, scripts/styles/noscript content and repeated whitespace are removed to reduce
    false positives from presentation-only changes. Other content is hashed as raw bytes.
    """
    ctype = (content_type or '').lower()
    if 'html' not in ctype:
        return hashlib.sha256(content).hexdigest()
    text = content.decode('utf-8', errors='ignore')
    soup = BeautifulSoup(text, 'html.parser')
    for tag in soup(['script', 'style', 'noscript']):
        tag.decompose()
    normalized = re.sub(r'\s+', ' ', soup.get_text(' ', strip=True)).strip()
    return hashlib.sha256(normalized.encode('utf-8')).hexdigest()
