# Assignment Coverage Checklist

## Mandatory core

- [x] Single-domain support
- [x] Multi-domain architecture
- [x] Internal HTML link discovery
- [x] `sitemap.xml` and sitemap-index discovery
- [x] `robots.txt` sitemap references and crawl rules
- [x] Canonical/feed link discovery
- [x] URL normalization and duplicate prevention
- [x] Redirect and HTTP-status recording
- [x] Persistent repository
- [x] Automated submission queue
- [x] Success/failure and archive proof storage
- [x] Controlled retry/backoff
- [x] Resume/recovery after interruption
- [x] Dashboard
- [x] Repository search/history
- [x] Large-site limits and database-backed processing
- [x] Multi-domain statistics
- [x] CSV/JSON export

## Robust/bonus implementation

- [x] Async bounded crawler
- [x] SHA-256 change detection before re-archiving
- [x] Scheduled recurring scans
- [x] PostgreSQL-ready configuration
- [x] Redis + Celery distributed task mode
- [x] Docker Compose
- [x] GitHub Actions CI
- [x] SSRF/public-target protection
- [x] Response-size protection
- [x] Idempotent archive jobs
- [x] Failure codes and performance timing
- [x] Optional Playwright JS rendering fallback
- [ ] Additional archive provider beyond mock/Wayback adapter
- [ ] Full visual diff between archived snapshot bodies
- [ ] 50+ domain load test report

## Final demonstration reminder

Use `ARCHIVE_PROVIDER=mock` for safe development. For a real archive submission demo, verify the provider's currently permitted public submission workflow immediately before the demo and do not bypass any service control.
