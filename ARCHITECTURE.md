# Technical Architecture — PRJ-09

## Local development mode

```text
Browser :3000
    │
    ▼
Next.js dashboard
    │ REST
    ▼
FastAPI :8000
    ├── Async crawler
    ├── Incremental change detector
    ├── Embedded archive worker
    ├── Embedded recurring scheduler
    └── SQLite repository
```

## Production / robust mode

```text
                         ┌──────────────────┐
                         │     Next.js      │
                         │    Dashboard     │
                         └────────┬─────────┘
                                  │ REST
                                  ▼
                         ┌──────────────────┐
                         │     FastAPI      │
                         │ API + validation │
                         └──────┬─────┬─────┘
                                │     │
                  metadata/state│     │ tasks
                                ▼     ▼
                     ┌────────────┐  ┌─────────┐
                     │ PostgreSQL │  │  Redis  │
                     └────────────┘  └────┬────┘
                                         │
                             ┌───────────┴───────────┐
                             ▼                       ▼
                      Celery workers             Celery Beat
                      ├── Crawl tasks            scheduled scans
                      └── Archive jobs
                             │
              ┌──────────────┼──────────────┐
              ▼              ▼              ▼
           HTTPX         Playwright*     Archive provider
      bounded async      JS fallback*      adapters

* optional
```

## Reliability decisions

- Persistent queue state lives in the database; Redis transports Celery tasks in production mode.
- PostgreSQL workers use `FOR UPDATE SKIP LOCKED` when claiming archive jobs so concurrent workers do not intentionally claim the same row.
- Archive jobs include an `idempotency_key` based on URL, provider, and content fingerprint.
- Temporary failures use exponential backoff by moving `available_at` into the future rather than sleeping the worker.
- Stale processing jobs can be recovered after interruption.
- SHA-256 fingerprints stop unchanged content from being unnecessarily re-archived.

## Security boundaries

- Only `http` and `https` are accepted.
- Private, loopback, link-local, multicast, reserved, `.local`, and credential-bearing URLs are rejected.
- Redirect destinations are validated before following them.
- Crawler remains on the configured hostname.
- robots.txt rules are honored.
- Response body size, crawl depth, page count, and concurrency are bounded.
- Archive integrations do not bypass CAPTCHA, rate limits, authentication, or access controls.

## Data model

- `domains` — domain configuration and recurring scan schedule.
- `crawl_runs` — scan history/performance.
- `urls` — discovered URL inventory, HTTP metadata, fingerprints, change status.
- `archive_jobs` — persistent idempotent queue state and retry metadata.
- `archive_submissions` — immutable-ish historical submission records/proof links.
