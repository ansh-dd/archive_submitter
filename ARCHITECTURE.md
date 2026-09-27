# Technical Architecture - PRJ-09

## Website Archive Submitter & Automated Backup Repository

PRJ-09 is a multi-domain website crawling, archival submission, and historical backup system.

The implemented architecture separates the web interface, API, persistent repository, task queue, background workers, crawler, JavaScript renderer, scheduler, and archive providers.

---

## 1. Final Working Architecture

```text
                         +----------------------+
                         |     Web Browser      |
                         |   localhost:3000     |
                         +----------+-----------+
                                    |
                                    | HTTP / REST
                                    v
                         +----------------------+
                         |   Next.js Frontend   |
                         | Dashboard / Queue /  |
                         | Repository / Details |
                         +----------+-----------+
                                    |
                                    | REST API
                                    v
                         +----------------------+
                         |   FastAPI Backend    |
                         |   localhost:8000     |
                         +----+------------+----+
                              |            |
                    metadata  |            | task dispatch
                              v            v
                  +----------------+   +----------------+
                  |   Supabase /   |   |  Redis Cloud   |
                  |   PostgreSQL   |   | Task Broker +  |
                  |                |   | Result Backend |
                  +----------------+   +--------+-------+
                                               |
                           +-------------------+-------------------+
                           |                                       |
                           v                                       v
                 +---------------------+                 +------------------+
                 |    Celery Worker    |                 |   Celery Beat    |
                 | Background Tasks    |                 | Scheduled Scans  |
                 +----------+----------+                 +------------------+
                            |
                 +----------+-----------+
                 |                      |
                 v                      v
        +------------------+   +--------------------+
        |  Async Crawler   |   | Archive Providers  |
        | HTTPX + BS4      |   |                    |
        +--------+---------+   | Wayback Machine    |
                 |             | Archive.today*     |
                 |             | Mock provider      |
                 v             +--------------------+
        +------------------+
        | Playwright       |
        | JS Fallback      |
        +------------------+

* Archive.today is treated as manual-only because no verified
  documented public automation API is configured. The project
  does not bypass CAPTCHA, authentication, rate limits, or
  access restrictions.
```

---

## 2. Main Components

### Next.js Frontend

The frontend provides:

- Domain dashboard
- Domain detail pages
- URL inventory
- Queue monitoring
- Repository search
- Archive service filtering
- Submission status filtering
- Archive history
- Stored archive links
- CSV/JSON export
- Scheduled scan controls
- Scan and archive actions

Default local URL:

```text
http://localhost:3000
```

---

### FastAPI Backend

FastAPI provides the REST API used by the frontend.

Main responsibilities:

- Domain management
- Crawl requests
- Archive queue creation
- Repository queries
- Export endpoints
- Health monitoring
- Scheduling configuration
- Job status reporting

Default local URL:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Health endpoint:

```text
http://127.0.0.1:8000/api/system/health
```

---

## 3. Database Layer

The final tested environment uses:

```text
Supabase PostgreSQL
```

The database persists the complete archival repository.

Main tables:

```text
domains
crawl_runs
urls
archive_jobs
archive_submissions
```

### domains

Stores:

- Domain
- Scan status
- Schedule configuration
- Last scan information
- Domain-level statistics

### crawl_runs

Stores:

- Scan start time
- Scan completion time
- Number of discovered URLs
- Number of fetched URLs
- New URL count
- Changed URL count
- Scan status
- Performance information

### urls

Stores:

- Original URL
- Normalized URL
- Discovery source
- HTTP status
- Content size
- SHA-256 fingerprint
- New/changed state
- Last discovery time

### archive_jobs

Stores persistent archive queue state:

- URL
- Archive provider
- Status
- Retry count
- Available time
- Started time
- Completion time
- Error information
- Content fingerprint

### archive_submissions

Stores historical archive results:

- Submission service
- Submission timestamp
- Result
- Archive URL
- Archive identifier
- Error details

---

## 4. Redis and Celery

The final tested deployment uses Redis Cloud as the Celery broker and result backend.

Redis provides durable task transport between FastAPI and Celery workers.

Celery performs background processing so long-running crawling or archival work does not block the web API.

Main tasks include:

```text
crawl_domain_task
process_archive_queue
dispatch_scheduled_scans
```

---

## 5. Celery Beat

Celery Beat periodically dispatches scheduled work.

It supports recurring scans configured from the domain dashboard.

Example workflow:

```text
Celery Beat
    |
    v
Check scheduled domains
    |
    v
Dispatch crawl task
    |
    v
Celery Worker
```

---

## 6. URL Discovery Pipeline

The crawler attempts to discover relevant public URLs using:

- Internal HTML links
- sitemap.xml
- Sitemap indexes
- robots.txt references
- Canonical URLs
- Pagination
- Relevant feed/navigation links
- JavaScript-rendered links through Playwright where needed

The crawler remains inside the configured hostname.

---

## 7. JavaScript-Rendered Pages

Playwright is available as a fallback for JavaScript-heavy websites.

Normal crawling uses HTTP first because it is faster and consumes fewer resources.

When too few useful internal links are found from static HTML, Playwright can:

1. Launch Chromium.
2. Load the page.
3. Wait for DOM content.
4. Wait for links.
5. Scroll the page.
6. Extract the rendered HTML.
7. Discover additional links.

This was tested successfully with JavaScript-heavy pages.

---

## 8. URL Processing

Before URLs are stored or archived, the system performs:

```text
URL discovery
    |
    v
Normalization
    |
    v
Tracking parameter removal
    |
    v
Fragment handling
    |
    v
Same-domain validation
    |
    v
Duplicate removal
    |
    v
HTTP fetch
    |
    v
SHA-256 fingerprint
    |
    v
Repository storage
```

---

## 9. Incremental Backup

Each successfully fetched page receives a SHA-256 content fingerprint.

The fingerprint allows the system to classify content as:

```text
NEW
CHANGED
UNCHANGED
```

Normal archive processing queues only URLs that require a new archive submission.

Users can also explicitly request:

```text
Force re-archive all
```

This allows a new historical snapshot even when content has not changed.

---

## 10. Internet Archive / Wayback Machine

The production archive provider uses the Internet Archive Save Page Now service.

Authentication credentials are read from environment variables.

The flow is:

```text
Archive job
    |
    v
Celery Worker
    |
    v
POST Save Page Now
    |
    v
Receive job identifier
    |
    v
Poll archive status
    |
    +---- pending ----> poll again
    |
    +---- error ------> record FAILED
    |
    +---- success ----> store Wayback URL
```

Successful records contain a real archive link similar to:

```text
https://web.archive.org/web/<timestamp>/<original_url>
```

The working implementation has been verified with real public Wayback snapshots.

---

## 11. Archive.today / Archive.is

Archive.today / Archive.is was investigated as required by the assignment.

The project contains a provider representation for it, but automated submission is intentionally not performed because no verified documented public automation API is configured.

The provider returns:

```text
MANUAL_SUBMISSION_REQUIRED
```

The implementation does not attempt to bypass:

- CAPTCHA
- Authentication
- Rate limits
- Access controls
- Other security restrictions

---

## 12. Persistent Queue and Recovery

Archive jobs are stored in PostgreSQL rather than existing only inside worker memory.

This enables recovery after worker interruption.

The following scenario was successfully tested:

```text
Celery Worker stopped
    |
    v
Archive request created
    |
    v
Job stored as PENDING
    |
    v
Worker remains offline
    |
    v
Celery Worker restarted
    |
    v
Worker reconnects to Redis
    |
    v
Pending archive job processed
    |
    v
Wayback submission succeeds
    |
    v
Status changes to SUCCESS
```

This verifies interruption and resume capability.

---

## 13. Failure Handling

Archive failures are recorded rather than stopping the entire application.

Recorded information includes:

- Error code
- Error message
- Retry count
- Start time
- Completion time
- Failed URL
- Archive service

Temporary failures can use retry/backoff logic.

Individual failures do not terminate processing of other archive jobs.

---

## 14. Concurrency and Job Safety

The worker architecture is designed to prevent duplicate job processing.

Important mechanisms include:

- Persistent job states
- Idempotency logic
- Content fingerprint checks
- Database locking
- Controlled worker processing
- Retry counters
- Delayed retry availability
- Duplicate archive prevention

PostgreSQL workers can safely claim work without intentionally processing the same queue item concurrently.

---

## 15. Repository and Search

The Repository page provides:

- Search by domain
- Search by URL
- Filter by archive service
- Filter by submission status
- Submission timestamp
- Submission status
- Content fingerprint
- Duration
- Stored archive URL
- Multiple historical submissions

This allows the user to determine whether a URL has already been archived and inspect previous submissions.

---

## 16. Large Website Handling

The system has been designed to support large URL inventories.

Scalability mechanisms include:

- Database-backed repository
- Background workers
- Async HTTP crawling
- Bounded concurrency
- Crawl page limits
- Crawl depth limits
- Response size limits
- Deduplication
- Persistent queue
- Incremental scanning
- Batch-style processing
- Redis task distribution

Large multi-thousand-URL inventories were tested during development.

---

## 17. Security Boundaries

The crawler applies several security controls.

Only:

```text
http://
https://
```

URLs are accepted.

The system rejects inappropriate targets such as:

- Loopback addresses
- Private network addresses
- Link-local addresses
- Reserved addresses
- Multicast addresses
- `.local` hosts
- URLs containing embedded credentials

Redirect destinations are revalidated before being followed.

Additional protections include:

- Same-domain crawling
- robots.txt awareness
- Response-size limits
- Crawl limits
- Timeout controls
- Archive rate-limit handling
- No CAPTCHA bypass

---

## 18. Health Monitoring

The system exposes a health endpoint.

Example:

```json
{
  "api": "healthy",
  "database": "healthy",
  "redis": "healthy",
  "task_mode": "celery",
  "archive_provider": "wayback",
  "crawler_concurrency": 5,
  "max_response_size_mb": 10
}
```

This verifies connectivity between:

```text
FastAPI
PostgreSQL
Redis
Celery configuration
Archive configuration
```

---

## 19. Current Final Runtime

The tested local runtime is:

```text
Frontend:
Next.js

Backend:
FastAPI

Crawler:
HTTPX + BeautifulSoup

JavaScript rendering:
Playwright + Chromium

Database:
Supabase PostgreSQL

Task broker:
Redis Cloud

Background processing:
Celery Worker

Scheduling:
Celery Beat

Primary automated archive provider:
Internet Archive / Wayback Machine

Secondary investigated provider:
Archive.today / Archive.is
(manual-only safe handling)
```

---

## 20. End-to-End Workflow

```text
User adds domain
    |
    v
FastAPI stores domain
    |
    v
Scan requested
    |
    v
Celery crawl task
    |
    v
HTTP crawler
    |
    +--> Playwright fallback if required
    |
    v
URL normalization and deduplication
    |
    v
HTTP metadata collection
    |
    v
SHA-256 fingerprinting
    |
    v
Supabase repository
    |
    v
Archive new/changed
    |
    v
Persistent archive_jobs queue
    |
    v
Redis / Celery
    |
    v
Wayback Save Page Now
    |
    v
SUCCESS / FAILED
    |
    v
archive_submissions history
    |
    v
Repository / Open archive
```

---

## 21. Reliability Summary

The architecture provides:

- Persistent state
- Background processing
- Multi-domain support
- Incremental backups
- Change detection
- Retry handling
- Failure isolation
- Worker restart recovery
- Real archive proof URLs
- Scheduled scans
- Searchable historical repository
- JavaScript rendering fallback
- CSV/JSON exports
- Health monitoring

The result is a complete website archival repository architecture rather than a simple web crawler.