from __future__ import annotations

import asyncio
import gzip
import time
import xml.etree.ElementTree as ET
from collections import deque
from dataclasses import dataclass
from datetime import datetime, timezone
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit, urlunsplit
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from sqlalchemy.orm import Session

from .config import settings
from .content import stable_content_hash
from .models import CrawlRun, Domain, URLRecord
from .security import assert_public_http_url


TRACKING_PREFIXES = ("utm_",)
TRACKING_KEYS = {"fbclid", "gclid", "mc_cid", "mc_eid"}
REDIRECT_CODES = {301, 302, 303, 307, 308}


def utcnow():
    return datetime.now(timezone.utc)


def normalize_url(url: str) -> str:
    p = urlsplit(url.strip())

    if p.scheme.lower() not in {"http", "https"} or not p.hostname:
        raise ValueError("Only HTTP/HTTPS URLs can be normalized.")

    scheme = p.scheme.lower()
    host = p.hostname.lower().rstrip(".")
    port = p.port

    netloc = host

    if port and not (
        (scheme == "http" and port == 80)
        or (scheme == "https" and port == 443)
    ):
        netloc = f"{host}:{port}"

    path = p.path or "/"

    if path != "/" and path.endswith("/"):
        path = path.rstrip("/")

    filtered = []

    for k, v in parse_qsl(p.query, keep_blank_values=True):
        lk = k.lower()

        if lk in TRACKING_KEYS or lk.startswith(TRACKING_PREFIXES):
            continue

        filtered.append((k, v))

    query = urlencode(sorted(filtered), doseq=True)

    return urlunsplit((scheme, netloc, path, query, ""))


def same_host(url: str, hostname: str) -> bool:
    return (
        (urlsplit(url).hostname or "").lower().rstrip(".")
        == hostname.lower().rstrip(".")
    )


def _extract_sitemaps_from_robots(text: str) -> list[str]:
    found: list[str] = []

    for line in text.splitlines():
        if line.lower().startswith("sitemap:"):
            value = line.split(":", 1)[1].strip()

            if value:
                found.append(value)

    return found


def _parse_sitemap_bytes(
    content: bytes,
    source_url: str,
) -> tuple[list[str], list[str]]:

    if source_url.lower().endswith(".gz"):
        try:
            content = gzip.decompress(content)
        except OSError:
            pass

    root = ET.fromstring(content)

    tag = root.tag.rsplit("}", 1)[-1].lower()

    locs = [
        (el.text or "").strip()
        for el in root.iter()
        if el.tag.rsplit("}", 1)[-1].lower() == "loc"
        and el.text
    ]

    if tag == "sitemapindex":
        return [], locs

    return locs, []


@dataclass
class FetchResult:
    requested_url: str
    final_url: str
    status_code: int
    content: bytes
    content_type: str
    headers: dict[str, str]


async def _safe_fetch(
    client: httpx.AsyncClient,
    url: str,
    semaphore: asyncio.Semaphore,
    max_redirects: int = 5,
) -> FetchResult:

    current = url
    max_bytes = settings.max_response_size_mb * 1024 * 1024

    for _ in range(max_redirects + 1):

        # Validate every redirect target to defend against SSRF
        # through redirect chains.
        assert_public_http_url(current)

        async with semaphore:
            async with client.stream(
                "GET",
                current,
                follow_redirects=False,
            ) as response:

                if (
                    response.status_code in REDIRECT_CODES
                    and response.headers.get("location")
                ):
                    current = urljoin(
                        current,
                        response.headers["location"],
                    )
                    continue

                declared = response.headers.get("content-length")

                if (
                    declared
                    and declared.isdigit()
                    and int(declared) > max_bytes
                ):
                    raise ValueError(
                        f"Response exceeds "
                        f"{settings.max_response_size_mb} MB limit."
                    )

                chunks: list[bytes] = []
                total = 0

                async for chunk in response.aiter_bytes():
                    total += len(chunk)

                    if total > max_bytes:
                        raise ValueError(
                            f"Response exceeds "
                            f"{settings.max_response_size_mb} MB limit."
                        )

                    chunks.append(chunk)

                return FetchResult(
                    requested_url=url,
                    final_url=str(response.url),
                    status_code=response.status_code,
                    content=b"".join(chunks),
                    content_type=response.headers.get(
                        "content-type",
                        "",
                    ),
                    headers={
                        k.lower(): v
                        for k, v in response.headers.items()
                    },
                )

    raise ValueError("Too many redirects.")


async def _discover(
    domain: Domain,
) -> tuple[dict[str, dict], int]:

    headers = {
        "User-Agent": settings.user_agent,
        "Accept": "text/html,application/xml,text/xml,*/*;q=0.5",
    }

    semaphore = asyncio.Semaphore(
        max(1, settings.max_concurrent_requests)
    )

    timeout = httpx.Timeout(settings.request_timeout)

    discovered: dict[str, dict] = {}
    fetch_count = 0

    async with httpx.AsyncClient(
        timeout=timeout,
        headers=headers,
    ) as client:

        # -------------------------------------------------
        # ROBOTS.TXT
        # -------------------------------------------------

        robots_url = urljoin(
            domain.base_url,
            "/robots.txt",
        )

        robot_parser: RobotFileParser | None = RobotFileParser()
        robot_parser.set_url(robots_url)

        sitemap_seeds = [
            urljoin(
                domain.base_url,
                "/sitemap.xml",
            )
        ]

        try:
            rr = await _safe_fetch(
                client,
                robots_url,
                semaphore,
            )

            if rr.status_code < 400:

                robots_text = rr.content.decode(
                    "utf-8",
                    errors="ignore",
                )

                robot_parser.parse(
                    robots_text.splitlines()
                )

                sitemap_seeds.extend(
                    _extract_sitemaps_from_robots(
                        robots_text
                    )
                )

            else:
                robot_parser = None

        except Exception:
            robot_parser = None

        # -------------------------------------------------
        # SITEMAP DISCOVERY
        # -------------------------------------------------

        sitemap_queue = deque(
            dict.fromkeys(sitemap_seeds)
        )

        sitemap_seen: set[str] = set()
        sitemap_count = 0

        while (
            sitemap_queue
            and sitemap_count < settings.max_sitemap_urls
        ):

            sm = sitemap_queue.popleft()

            if sm in sitemap_seen:
                continue

            sitemap_seen.add(sm)

            try:

                if not same_host(
                    sm,
                    domain.hostname,
                ):
                    continue

                resp = await _safe_fetch(
                    client,
                    sm,
                    semaphore,
                )

                if resp.status_code >= 400:
                    continue

                urls, child_maps = _parse_sitemap_bytes(
                    resp.content,
                    sm,
                )

                for child in child_maps:

                    if same_host(
                        child,
                        domain.hostname,
                    ):
                        sitemap_queue.append(child)

                for raw in urls:

                    if not same_host(
                        raw,
                        domain.hostname,
                    ):
                        continue

                    norm = normalize_url(raw)

                    discovered.setdefault(
                        norm,
                        {
                            "original_url": raw,
                            "source": "sitemap",
                            "http_status": None,
                            "redirect_url": None,
                            "content_type": None,
                            "content_length": None,
                            "content_hash": None,
                            "etag": None,
                            "last_modified": None,
                            "robots_allowed": True,
                        },
                    )

                    sitemap_count += 1

                    if (
                        sitemap_count
                        >= settings.max_sitemap_urls
                    ):
                        break

            except Exception:
                continue

        # -------------------------------------------------
        # BASE URL
        # -------------------------------------------------

        base_norm = normalize_url(
            domain.base_url
        )

        discovered.setdefault(
            base_norm,
            {
                "original_url": domain.base_url,
                "source": "seed",
                "http_status": None,
                "redirect_url": None,
                "content_type": None,
                "content_length": None,
                "content_hash": None,
                "etag": None,
                "last_modified": None,
                "robots_allowed": True,
            },
        )

        queue: deque[
            tuple[str, str, int]
        ] = deque(
            (
                v["original_url"],
                v["source"],
                0,
            )
            for v in discovered.values()
        )

        crawled: set[str] = set()

        # -------------------------------------------------
        # FETCH PAGE
        # -------------------------------------------------

        async def fetch_page(
            raw_url: str,
            source: str,
            depth: int,
        ):
            nonlocal fetch_count

            norm = normalize_url(raw_url)

            if (
                norm in crawled
                or depth > settings.max_crawl_depth
            ):
                return norm, [], None

            crawled.add(norm)

            # Check robots.txt
            if (
                robot_parser
                and not robot_parser.can_fetch(
                    settings.user_agent,
                    norm,
                )
            ):

                record = discovered.setdefault(
                    norm,
                    {
                        "original_url": raw_url,
                        "source": source,
                    },
                )

                record.update(
                    {
                        "robots_allowed": False,
                        "http_status": None,
                        "redirect_url": None,
                        "content_type": None,
                        "content_length": None,
                        "content_hash": None,
                        "etag": None,
                        "last_modified": None,
                    }
                )

                return norm, [], None

            try:

                result = await _safe_fetch(
                    client,
                    norm,
                    semaphore,
                )

                fetch_count += 1

                final_norm = normalize_url(
                    result.final_url
                )

                record = discovered.setdefault(
                    norm,
                    {
                        "original_url": raw_url,
                        "source": source,
                    },
                )

                record.update(
                    {
                        "robots_allowed": True,
                        "http_status": result.status_code,
                        "redirect_url": (
                            result.final_url
                            if final_norm != norm
                            else None
                        ),
                        "content_type": result.content_type,
                        "content_length": len(
                            result.content
                        ),
                        "content_hash": (
                            stable_content_hash(
                                result.content,
                                result.content_type,
                            )
                            if result.status_code < 400
                            else None
                        ),
                        "etag": result.headers.get(
                            "etag"
                        ),
                        "last_modified": (
                            result.headers.get(
                                "last-modified"
                            )
                        ),
                    }
                )

                # Only parse successful HTML pages
                if (
                    result.status_code >= 400
                    or "text/html"
                    not in result.content_type.lower()
                ):
                    return norm, [], result

                soup = BeautifulSoup(
                    result.content,
                    "html.parser",
                )

                candidates: list[
                    tuple[str, str, int]
                ] = []

                # -----------------------------------------
                # CANONICAL URL
                # -----------------------------------------

                canonical = soup.find(
                    "link",
                    rel=lambda v: (
                        v
                        and "canonical"
                        in (
                            v
                            if isinstance(v, list)
                            else [v]
                        )
                    ),
                )

                if (
                    canonical
                    and canonical.get("href")
                ):
                    candidates.append(
                        (
                            urljoin(
                                result.final_url,
                                canonical["href"],
                            ),
                            "canonical",
                            depth + 1,
                        )
                    )

                # -----------------------------------------
                # STANDARD HTML LINKS
                # -----------------------------------------

                for link in soup.find_all(
                    "a",
                    href=True,
                ):

                    candidates.append(
                        (
                            urljoin(
                                result.final_url,
                                link["href"],
                            ),
                            "html",
                            depth + 1,
                        )
                    )

                # -----------------------------------------
                # RSS / ATOM FEEDS
                # -----------------------------------------

                for link in soup.find_all(
                    "link",
                    href=True,
                ):

                    rel = (
                        " ".join(
                            link.get("rel", [])
                        )
                        if isinstance(
                            link.get("rel"),
                            list,
                        )
                        else str(
                            link.get("rel") or ""
                        )
                    )

                    typ = str(
                        link.get("type") or ""
                    )

                    if (
                        "alternate" in rel.lower()
                        and (
                            "rss" in typ.lower()
                            or "atom" in typ.lower()
                        )
                    ):

                        candidates.append(
                            (
                                urljoin(
                                    result.final_url,
                                    link["href"],
                                ),
                                "feed",
                                depth + 1,
                            )
                        )

                # -----------------------------------------
                # CHECK NUMBER OF STATIC INTERNAL LINKS
                # -----------------------------------------

                static_internal_links = set()

                for (
                    candidate_url,
                    _,
                    _,
                ) in candidates:

                    try:
                        candidate_norm = normalize_url(
                            candidate_url
                        )

                        if (
                            same_host(
                                candidate_norm,
                                domain.hostname,
                            )
                            and candidate_norm != norm
                        ):
                            static_internal_links.add(
                                candidate_norm
                            )

                    except ValueError:
                        continue

                # -----------------------------------------
                # PLAYWRIGHT FALLBACK
                # -----------------------------------------
                # Trigger browser rendering when static
                # HTML contains very few useful internal
                # links. This helps with JavaScript-heavy
                # websites.

                if (
                    settings.enable_playwright
                    and len(static_internal_links) < 3
                ):

                    try:
                        from .js_renderer import (
                            render_html,
                        )

                        rendered = await render_html(
                            result.final_url
                        )

                        rendered_soup = BeautifulSoup(
                            rendered,
                            "html.parser",
                        )

                        for link in rendered_soup.find_all(
                            "a",
                            href=True,
                        ):

                            candidate_url = urljoin(
                                result.final_url,
                                link["href"],
                            )

                            try:
                                candidate_norm = (
                                    normalize_url(
                                        candidate_url
                                    )
                                )

                            except ValueError:
                                continue

                            if (
                                same_host(
                                    candidate_norm,
                                    domain.hostname,
                                )
                                and candidate_norm != norm
                            ):

                                candidates.append(
                                    (
                                        candidate_url,
                                        "playwright",
                                        depth + 1,
                                    )
                                )

                    except Exception as exc:

                        print(
                            "Playwright rendering "
                            f"failed for "
                            f"{result.final_url}: "
                            f"{exc}"
                        )

                return norm, candidates, result

            except Exception as exc:

                record = discovered.setdefault(
                    norm,
                    {
                        "original_url": raw_url,
                        "source": source,
                    },
                )

                record.update(
                    {
                        "robots_allowed": True,
                        "http_status": None,
                        "redirect_url": None,
                        "content_type": None,
                        "content_length": None,
                        "content_hash": None,
                        "etag": None,
                        "last_modified": None,
                        "fetch_error": str(exc)[:1000],
                    }
                )

                return norm, [], None

        # -------------------------------------------------
        # CRAWL QUEUE
        # -------------------------------------------------

        while (
            queue
            and len(crawled)
            < settings.max_crawl_pages
        ):

            batch: list[
                tuple[str, str, int]
            ] = []

            while (
                queue
                and len(batch)
                < settings.max_concurrent_requests
                and len(crawled) + len(batch)
                < settings.max_crawl_pages
            ):

                raw, source, depth = queue.popleft()

                try:
                    norm = normalize_url(raw)

                except ValueError:
                    continue

                if (
                    norm not in crawled
                    and same_host(
                        norm,
                        domain.hostname,
                    )
                ):
                    batch.append(
                        (
                            raw,
                            source,
                            depth,
                        )
                    )

            if not batch:
                continue

            results = await asyncio.gather(
                *(
                    fetch_page(*item)
                    for item in batch
                )
            )

            for _, candidates, _ in results:

                for (
                    candidate,
                    source,
                    depth,
                ) in candidates:

                    try:
                        norm = normalize_url(
                            candidate
                        )

                    except ValueError:
                        continue

                    if (
                        not same_host(
                            norm,
                            domain.hostname,
                        )
                        or norm in discovered
                    ):
                        continue

                    discovered[norm] = {
                        "original_url": candidate,
                        "source": source,
                        "http_status": None,
                        "redirect_url": None,
                        "content_type": None,
                        "content_length": None,
                        "content_hash": None,
                        "etag": None,
                        "last_modified": None,
                        "robots_allowed": True,
                    }

                    queue.append(
                        (
                            candidate,
                            source,
                            depth,
                        )
                    )

            if settings.crawl_delay:
                await asyncio.sleep(
                    settings.crawl_delay
                )

    return discovered, fetch_count


def crawl_domain(
    db: Session,
    domain_id: int,
) -> None:

    domain = db.get(
        Domain,
        domain_id,
    )

    if not domain:
        return

    started = time.perf_counter()

    run = CrawlRun(
        domain_id=domain.id,
        status="RUNNING",
    )

    domain.status = "SCANNING"

    db.add(run)
    db.commit()
    db.refresh(run)

    try:

        assert_public_http_url(
            domain.base_url
        )

        discovered, fetch_count = asyncio.run(
            _discover(domain)
        )

        existing_rows = {
            u.normalized_url: u
            for u in db.query(URLRecord)
            .filter(
                URLRecord.domain_id == domain.id
            )
            .all()
        }

        now = utcnow()

        new_count = 0
        changed_count = 0

        for norm, detail in discovered.items():

            new_hash = detail.get(
                "content_hash"
            )

            if norm in existing_rows:

                row = existing_rows[norm]

                old_hash = row.content_hash

                row.last_seen_at = now
                row.last_checked_at = now

                row.robots_allowed = detail.get(
                    "robots_allowed",
                    True,
                )

                if (
                    detail.get("http_status")
                    is not None
                ):
                    row.http_status = detail[
                        "http_status"
                    ]

                row.redirect_url = detail.get(
                    "redirect_url"
                )

                row.content_type = detail.get(
                    "content_type"
                )

                row.content_length = detail.get(
                    "content_length"
                )

                row.etag = detail.get(
                    "etag"
                )

                row.last_modified = detail.get(
                    "last_modified"
                )

                if new_hash:

                    if (
                        old_hash
                        and old_hash != new_hash
                    ):

                        row.previous_content_hash = (
                            old_hash
                        )

                        row.change_status = (
                            "CHANGED"
                        )

                        changed_count += 1

                    elif old_hash == new_hash:

                        row.change_status = (
                            "UNCHANGED"
                        )

                    else:

                        row.change_status = "NEW"

                    row.content_hash = new_hash

            else:

                db.add(
                    URLRecord(
                        domain_id=domain.id,
                        original_url=detail[
                            "original_url"
                        ],
                        normalized_url=norm,
                        discovery_source=detail[
                            "source"
                        ],
                        http_status=detail.get(
                            "http_status"
                        ),
                        redirect_url=detail.get(
                            "redirect_url"
                        ),
                        content_type=detail.get(
                            "content_type"
                        ),
                        content_length=detail.get(
                            "content_length"
                        ),
                        content_hash=new_hash,
                        etag=detail.get(
                            "etag"
                        ),
                        last_modified=detail.get(
                            "last_modified"
                        ),
                        change_status="NEW",
                        robots_allowed=detail.get(
                            "robots_allowed",
                            True,
                        ),
                        discovered_at=now,
                        last_seen_at=now,
                        last_checked_at=now,
                    )
                )

                new_count += 1

        # -------------------------------------------------
        # SUCCESS
        # -------------------------------------------------

        run.status = "SUCCESS"
        run.urls_found = len(discovered)
        run.new_urls_found = new_count
        run.changed_urls_found = changed_count
        run.pages_fetched = fetch_count
        run.finished_at = now

        run.duration_ms = int(
            (time.perf_counter() - started)
            * 1000
        )

        domain.last_scan_at = now
        domain.status = "READY"

        db.commit()

    except Exception as exc:

        # -------------------------------------------------
        # FAILURE
        # -------------------------------------------------

        run.status = "FAILED"

        run.error_message = str(exc)[:4000]

        run.finished_at = utcnow()

        run.duration_ms = int(
            (time.perf_counter() - started)
            * 1000
        )

        domain.status = "ERROR"

        db.commit()