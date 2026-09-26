import ipaddress
import socket
from urllib.parse import urlsplit

BLOCKED_HOSTS = {'localhost', 'localhost.localdomain'}


def assert_public_http_url(url: str) -> None:
    parts = urlsplit(url)
    if parts.scheme not in {'http', 'https'} or not parts.hostname:
        raise ValueError('Only public http/https URLs are allowed.')
    if parts.username or parts.password:
        raise ValueError('URLs containing embedded credentials are not allowed.')
    host = parts.hostname.lower().rstrip('.')
    if host in BLOCKED_HOSTS or host.endswith('.local'):
        raise ValueError('Local/private hosts are not allowed.')
    try:
        infos = socket.getaddrinfo(host, None)
    except socket.gaierror as exc:
        raise ValueError('Domain could not be resolved.') from exc
    if not infos:
        raise ValueError('Domain could not be resolved.')
    for info in infos:
        ip = ipaddress.ip_address(info[4][0])
        if (
            ip.is_private or ip.is_loopback or ip.is_link_local or ip.is_multicast
            or ip.is_reserved or ip.is_unspecified
        ):
            raise ValueError('Private, loopback, link-local, multicast, or reserved addresses are not allowed.')
