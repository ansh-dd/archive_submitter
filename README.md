# PRJ-09 - Website Archive Submitter & Automated Backup Repository

A full-stack website archival system developed for the Pillai internship PRJ-09 assignment.

The application discovers public URLs for one or more domains, normalizes and fingerprints pages, detects new or changed content, creates persistent archive jobs, submits URLs to supported archival services, stores archive history, supports retry and recovery, and provides a searchable Next.js dashboard.

---

## 1. Final Working Technology Stack

```text
Frontend
- Next.js
- TypeScript

Backend
- Python
- FastAPI

Crawler
- HTTPX
- BeautifulSoup

JavaScript rendering
- Playwright
- Chromium

Database
- Supabase PostgreSQL

Task broker
- Redis Cloud

Background processing
- Celery Worker

Scheduling
- Celery Beat

Automated archive service
- Internet Archive / Wayback Machine

Secondary investigated archive service
- Archive.today / Archive.is
- Manual-only safe handling
```

---

## 2. Main Features

The implemented project supports:

- Single-domain crawling
- Multi-domain crawling
- Internal link discovery
- sitemap.xml discovery
- Sitemap index handling
- robots.txt references
- Canonical URLs
- Pagination/navigation discovery
- Same-domain crawling
- URL normalization
- Duplicate removal
- HTTP status recording
- Redirect handling
- Failed/inaccessible URL tracking
- SHA-256 page fingerprints
- NEW / CHANGED / UNCHANGED detection
- Incremental backup
- Force re-archive
- Persistent archive queue
- Background workers
- Retry/backoff architecture
- Worker restart recovery
- Real Wayback Machine submission
- Archive URL storage
- Archive identifier storage
- Failed submission tracking
- Submission history
- Repository search
- Archive service filtering
- Submission status filtering
- CSV export
- JSON export
- Scheduled recurring scans
- JavaScript-rendered page discovery with Playwright
- Health monitoring
- Large website handling
- Docker support
- GitHub Actions CI

---

## 3. Project Structure

```text
seo/
|
+-- backend/
|   |
|   +-- app/
|   |   +-- main.py
|   |   +-- crawler.py
|   |   +-- content.py
|   |   +-- security.py
|   |   +-- archive.py
|   |   +-- worker.py
|   |   +-- scheduler.py
|   |   +-- celery_app.py
|   |   +-- tasks.py
|   |   +-- js_renderer.py
|   |   +-- models.py
|   |   +-- db.py
|   |
|   +-- tests/
|   +-- requirements.txt
|   +-- requirements-playwright.txt
|   +-- .env
|   +-- Dockerfile
|
+-- frontend/
|   +-- app/
|   +-- lib/
|   +-- package.json
|   +-- Dockerfile
|
+-- ARCHITECTURE.md
+-- docker-compose.yml
+-- setup-local.bat
+-- run-all.bat
+-- run-worker.bat
+-- run-beat.bat
+-- run-backend.bat
+-- run-frontend.bat
+-- run-docker.bat
+-- README.md
|
+-- .github/
    +-- workflows/
        +-- ci.yml
```

---

## 4. Final Architecture

```text
Browser
   |
   v
Next.js Frontend
   |
   v
FastAPI Backend
   |
   +-------------------------+
   |                         |
   v                         v
Supabase PostgreSQL      Redis Cloud
                             |
                 +-----------+-----------+
                 |                       |
                 v                       v
           Celery Worker             Celery Beat
                 |
        +--------+---------+
        |                  |
        v                  v
     Crawler         Archive Providers
        |                  |
        v                  +--> Wayback Machine
   Playwright              +--> Archive.today*
                            +--> Mock provider
```

`Archive.today / Archive.is` is treated as manual-only because no verified documented public automation API is configured. The project does not bypass CAPTCHA, authentication, rate limits, or other access controls.

See:

```text
ARCHITECTURE.md
```

for the complete technical architecture.

---

# 5. Local Setup

The tested project path is:

```text
D:\Ansh\Study\Sem_7\Internship\seo
```

Open this folder in VS Code.

---

## 6. Backend Setup

Open PowerShell:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo\backend"
```

Create the virtual environment if it does not already exist:

```powershell
python -m venv .venv
```

Install backend dependencies:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

---

## 7. Playwright Setup

Install the optional browser-rendering dependencies:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo\backend"

.\.venv\Scripts\python.exe -m pip install -r requirements-playwright.txt
```

Install Chromium:

```powershell
.\.venv\Scripts\python.exe -m playwright install chromium
```

Enable it in `.env`:

```env
ENABLE_PLAYWRIGHT=true
```

Playwright is used as a fallback for JavaScript-heavy websites when static HTML contains too few useful internal links.

---

## 8. Backend Environment Configuration

Create:

```text
backend\.env
```

Never commit real passwords, Redis credentials, database passwords, or Wayback API keys to GitHub.

Example configuration:

```env
DATABASE_URL=postgresql+psycopg://USERNAME:PASSWORD@HOST:PORT/postgres

REDIS_URL=redis://default:PASSWORD@REDIS_HOST:REDIS_PORT/0
CELERY_BROKER_URL=redis://default:PASSWORD@REDIS_HOST:REDIS_PORT/0
CELERY_RESULT_BACKEND=redis://default:PASSWORD@REDIS_HOST:REDIS_PORT/0

TASK_MODE=celery
EMBEDDED_WORKER=false

ARCHIVE_PROVIDER=wayback

WAYBACK_SAVE_BASE=https://web.archive.org/save
WAYBACK_ACCESS_KEY=YOUR_ACCESS_KEY
WAYBACK_SECRET_KEY=YOUR_SECRET_KEY

ENABLE_PLAYWRIGHT=true
```

The final tested environment uses:

```text
Supabase PostgreSQL
Redis Cloud
Celery
Wayback Machine
Playwright
```

---

## 9. Wayback Machine Credentials

Internet Archive Save Page Now authentication requires credentials.

Generate the required credentials from your Internet Archive account.

Store them only in:

```text
backend\.env
```

using:

```env
WAYBACK_ACCESS_KEY=YOUR_ACCESS_KEY
WAYBACK_SECRET_KEY=YOUR_SECRET_KEY
```

Do not expose these credentials in screenshots, GitHub commits, documentation, or demonstration videos.

---

## 10. Frontend Setup

Open another PowerShell terminal:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo\frontend"
```

Install packages:

```powershell
npm.cmd install
```

Using `npm.cmd` is recommended on Windows if PowerShell blocks `npm.ps1`.

---

# 11. Running the Project

## Start FastAPI + Celery Worker + Celery Beat

From the project root:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo"

.\run-all.bat
```

This starts three backend processes:

```text
FastAPI
Celery Worker
Celery Beat
```

---

## Start Frontend

In another terminal:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo\frontend"

npm.cmd run dev
```

---

## Open the Application

Dashboard:

```text
http://localhost:3000
```

Queue:

```text
http://localhost:3000/queue
```

Repository:

```text
http://localhost:3000/repository
```

FastAPI:

```text
http://127.0.0.1:8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Health:

```text
http://127.0.0.1:8000/api/system/health
```

---

# 12. Health Check

A healthy final environment should return values similar to:

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

This confirms that the application can communicate with:

```text
FastAPI
Supabase PostgreSQL
Redis
Celery configuration
Wayback provider configuration
```

---

# 13. Website Crawling Workflow

```text
User adds domain
    |
    v
Start scan
    |
    v
Celery crawl task
    |
    v
robots.txt / sitemap / HTML discovery
    |
    v
Playwright fallback if required
    |
    v
URL normalization
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
Supabase repository
```

---

# 14. URL Discovery

The crawler can investigate and combine:

- Internal HTML links
- sitemap.xml
- Sitemap indexes
- robots.txt references
- Canonical URLs
- Pagination
- Public navigation links
- Relevant feed links
- JavaScript-rendered links

The crawler remains within the configured hostname.

---

# 15. Incremental Backup

Every fetched page receives a SHA-256 fingerprint.

The system determines whether the page is:

```text
NEW
CHANGED
UNCHANGED
```

A normal:

```text
Archive new/changed
```

operation avoids unnecessarily archiving unchanged content.

The user can explicitly select:

```text
Force re-archive all
```

to create another historical snapshot.

---

# 16. Archive Submission Workflow

```text
Archive new/changed
    |
    v
Persistent archive job
    |
    v
PostgreSQL archive_jobs
    |
    v
Redis
    |
    v
Celery Worker
    |
    v
Internet Archive Save Page Now
    |
    v
Receive job ID
    |
    v
Poll capture status
    |
    +--> SUCCESS
    |
    +--> FAILED
    |
    v
Store archive result
    |
    v
Repository
```

---

# 17. Real Wayback Machine Integration

The project uses the Internet Archive / Wayback Machine as the primary automated archive provider.

Successful captures generate a real URL similar to:

```text
https://web.archive.org/web/<timestamp>/<original_url>
```

The final implementation was tested successfully with real Wayback captures.

The application stores:

- Archive service
- Archive identifier
- Archive URL
- Submission timestamp
- Completion timestamp
- HTTP information
- Status
- Error information
- Content fingerprint

---

# 18. Archive.today / Archive.is

Archive.today / Archive.is was investigated as a secondary target.

The backend includes an Archive.today provider representation.

Because no verified documented public automation API is configured, the provider intentionally returns:

```text
MANUAL_SUBMISSION_REQUIRED
```

The application does not attempt to bypass:

- CAPTCHA
- Authentication
- Access controls
- Rate limits
- Security restrictions

This behavior is intentional.

---

# 19. Persistent Queue and Crash Recovery

Archive jobs are stored persistently in PostgreSQL.

The following recovery scenario was successfully tested:

```text
Celery Worker stopped
    |
    v
Archive job created
    |
    v
Job remains PENDING
    |
    v
Worker restarted
    |
    v
Worker reconnects to Redis
    |
    v
Pending job automatically processed
    |
    v
Wayback submission succeeds
    |
    v
Status becomes SUCCESS
```

This proves that worker interruption does not lose queued archive work.

---

# 20. Failure Handling

Failed archive jobs are stored instead of crashing the system.

A failure record can contain:

```text
FAILED
service
retry_count
error_code
error_message
created_at
started_at
completed_at
duration
URL
domain
```

One failed URL does not stop processing of other jobs.

---

# 21. Repository Page

Open:

```text
http://localhost:3000/repository
```

The Repository page supports:

- Search by domain
- Search by URL
- Filter by archive service
- Filter by submission status
- View successful submissions
- View failed submissions
- View timestamps
- View content fingerprints
- View processing duration
- Open stored archive URLs
- View multiple submissions for the same URL

---

# 22. Queue Page

Open:

```text
http://localhost:3000/queue
```

The Queue page is used to inspect archive processing state and historical jobs.

Possible states include:

```text
PENDING
PROCESSING
SUCCESS
FAILED
```

---

# 23. Scheduled Scans

Open a domain detail page and select:

```text
Enable daily schedule
```

Celery Beat periodically checks for due scheduled scans.

Flow:

```text
Celery Beat
    |
    v
Check due scans
    |
    v
Dispatch task
    |
    v
Redis
    |
    v
Celery Worker
    |
    v
Crawler
```

---

# 24. JavaScript-Rendered Websites

Playwright is used as a browser-rendering fallback.

The renderer:

1. Opens Chromium.
2. Loads the page.
3. Waits for DOM content.
4. Waits for links.
5. Scrolls the page.
6. Extracts rendered HTML.
7. Returns links to the crawler.

This allows discovery on JavaScript-heavy public pages while respecting normal access restrictions.

---

# 25. Large Website Handling

The architecture supports large URL inventories through:

- Async crawling
- Bounded concurrency
- Database persistence
- Background workers
- Redis task distribution
- URL deduplication
- Incremental scans
- Crawl page limits
- Crawl depth limits
- Response-size limits
- Persistent queues

Multi-thousand-URL inventories were tested during development.

---

# 26. Export

A domain inventory can be exported as:

```text
CSV
JSON
```

from the domain detail page.

Example backend endpoints:

```text
/api/domains/<id>/export?format=csv
/api/domains/<id>/export?format=json
```

---

# 27. Security Features

The backend includes SSRF protections.

The crawler rejects inappropriate targets such as:

- localhost
- Private IP ranges
- Loopback IPs
- Link-local IPs
- Reserved addresses
- Multicast addresses
- `.local` hosts
- Credential-bearing URLs

Only:

```text
http
https
```

are accepted.

Redirect targets are revalidated before they are followed.

Additional controls include:

- Same-domain scope
- robots.txt handling
- Response-size limits
- Timeouts
- Crawl depth limits
- Crawl page limits
- Controlled concurrency
- Archive rate-limit handling
- No CAPTCHA bypass

---

# 28. Running Backend Tests

From:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo\backend"
```

run:

```powershell
.\.venv\Scripts\python.exe -m pytest -q
```

The exact pass count may change as tests are added, so use the actual current test output rather than relying on an old fixed number.

---

# 29. Recommended Final Demonstration

A strong demonstration sequence is:

1. Start FastAPI, Celery Worker, Celery Beat, and Next.js.
2. Open the health endpoint.
3. Show PostgreSQL and Redis as healthy.
4. Add a new domain.
5. Start URL discovery.
6. Show discovered URL inventory.
7. Explain HTTP status and SHA-256 fingerprint.
8. Queue one URL for real Wayback archival.
9. Show `PENDING`.
10. Show Celery processing the archive request.
11. Show `SUCCESS`.
12. Click `Open archive`.
13. Show the real Wayback Machine snapshot.
14. Show a failed archive submission in Repository.
15. Stop all Celery workers.
16. Queue a one-URL archive job.
17. Show that it remains `PENDING`.
18. Restart the Celery worker.
19. Show that the stored pending job is automatically resumed.
20. Show the final `SUCCESS`.
21. Re-scan an unchanged page.
22. Explain incremental backup.
23. Show multiple domains.
24. Show Repository search.
25. Show service and status filters.
26. Show archive submission history.
27. Show CSV/JSON export.
28. Show scheduled scans.
29. Explain Playwright support.
30. Explain Archive.today safe/manual-only handling.

---

# 30. Verified Development Results

During development, the project successfully demonstrated:

```text
Real Wayback capture                 PASS
Stored archive URL                   PASS
Open archive link                    PASS
Supabase PostgreSQL                  PASS
Redis Cloud                          PASS
Celery worker                        PASS
Celery Beat                          PASS
Persistent pending queue             PASS
Worker restart recovery              PASS
Failed submission recording          PASS
Incremental fingerprinting           PASS
Multi-domain repository              PASS
Repository search                    PASS
Service/status filtering             PASS
CSV/JSON export                      PASS
Playwright rendering                 PASS
Large URL inventories                PASS
```

---

# 31. Docker

A Docker Compose configuration is included for containerized deployment.

Run:

```powershell
docker compose up --build
```

The Docker architecture can provide:

```text
Next.js
FastAPI
PostgreSQL
Redis
Celery Worker
Celery Beat
```

The actively tested development configuration uses managed Supabase PostgreSQL and Redis Cloud.

---

# 32. Important Security Note

Never commit the following to GitHub:

```text
backend/.env
Database passwords
Redis passwords
Wayback access keys
Wayback secret keys
Supabase credentials
```

Use `.env.example` with placeholders for public repositories.

---

# 33. Main Viva Terms

Important concepts used in this project:

**Asynchronous crawling**

**Bounded concurrency**

**URL normalization**

**URL deduplication**

**robots.txt**

**sitemap.xml**

**SSRF protection**

**SHA-256 content fingerprinting**

**Incremental backup**

**Idempotency**

**Persistent queue**

**Redis**

**Celery**

**Celery Beat**

**PostgreSQL**

**Supabase**

**Exponential backoff**

**Failure recovery**

**Worker restart recovery**

**Provider abstraction**

**Wayback Save Page Now**

**Playwright**

**Background processing**

**Scheduled tasks**

**Docker**

**CI/CD**

**Repository search**

**Historical archive records**

---

# 34. Final Result

The final application functions as a website archival repository rather than only a crawler.

A user can:

```text
Add one or more domains
        |
        v
Discover public URLs
        |
        v
Track new and changed pages
        |
        v
Create persistent archive jobs
        |
        v
Submit pages to Wayback Machine
        |
        v
Store success/failure results
        |
        v
Open real archive snapshots
        |
        v
Search historical submissions
        |
        v
Repeat scans incrementally
```

PRJ-09 therefore combines crawling, automation, archival APIs, persistent queues, databases, browser rendering, incremental backup, scheduling, failure recovery, and a searchable web interface.