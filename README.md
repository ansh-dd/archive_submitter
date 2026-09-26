# PRJ-09 — Robust Website Archive Submitter & Automated Backup Repository

A VS Code-ready implementation of the Pillai internship PRJ-09 assignment. It discovers public URLs for one or more domains, normalizes and fingerprints pages, detects new/changed content, creates persistent archival jobs, records archive history, supports retry/recovery, and exposes a live Next.js dashboard.

## What makes this version technically robust

- **Async bounded crawler** using `httpx.AsyncClient` with configurable concurrency.
- **SSRF defenses**: only public HTTP/HTTPS targets are allowed; localhost/private/link-local/reserved addresses and embedded credentials are rejected. Every redirect target is revalidated.
- **Robots-aware crawling** and same-domain scope enforcement.
- **Response-size limits** and crawl depth/page limits to prevent runaway scans.
- **URL normalization and deduplication** including tracking-parameter removal.
- **SHA-256 content fingerprints** for `NEW`, `CHANGED`, and `UNCHANGED` state.
- **Incremental archiving**: a page with the same content fingerprint is not queued again unless force re-archive is selected.
- **Persistent idempotent archive jobs** with retry count, availability time, failure classification, and exponential backoff.
- **Crash recovery** for stale `PROCESSING` jobs.
- **Scheduled rescans** with local scheduler or Celery Beat.
- **PostgreSQL + Redis + Celery production architecture** through Docker Compose.
- **SQLite embedded mode** for easy VS Code development on Windows.
- **System health and performance metrics** in the API/dashboard.
- **CSV/JSON inventory export**.
- **Optional Playwright fallback** for JavaScript-rendered pages.
- **Docker and GitHub Actions CI**.
- **Automated tests** for URL normalization, content hashing, archive mock behavior, and security blocking.

## Project structure

```text
seo/
├── backend/
│   ├── app/
│   │   ├── main.py            # FastAPI routes
│   │   ├── crawler.py         # async crawler + sitemap/robots discovery
│   │   ├── content.py         # stable SHA-256 page fingerprint
│   │   ├── security.py        # SSRF/public-target validation
│   │   ├── archive.py         # archive provider adapters
│   │   ├── worker.py          # persistent archive worker
│   │   ├── scheduler.py       # recurring scan scheduler
│   │   ├── celery_app.py      # Celery configuration
│   │   ├── tasks.py           # distributed tasks
│   │   ├── js_renderer.py     # optional Playwright renderer
│   │   ├── models.py          # database schema
│   │   └── db.py
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-playwright.txt
│   └── Dockerfile
├── frontend/
│   ├── app/
│   ├── lib/
│   └── Dockerfile
├── docker-compose.yml
├── setup-local.bat
├── run-backend.bat
├── run-frontend.bat
├── run-docker.bat
└── .github/workflows/ci.yml
```

# Option A — easiest local VS Code mode (recommended first)

If your folder is:

```text
D:\Ansh\Study\Sem_7\Internship\seo
```

open that exact folder in VS Code.

### Important when replacing the older project

The robust version has additional database columns. If the old project already created `backend\archive.db` and you do not need its test data, delete it once:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo"
.\reset-local-db.bat
```

Or manually delete `backend\archive.db`.

## One-time setup

From the project root:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo"
.\setup-local.bat
```

Manual equivalent:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo\backend"
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env

cd "D:\Ansh\Study\Sem_7\Internship\seo\frontend"
npm install
Copy-Item .env.local.example .env.local
```

## Run locally

Terminal 1:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo"
.\run-backend.bat
```

Terminal 2:

```powershell
cd "D:\Ansh\Study\Sem_7\Internship\seo"
.\run-frontend.bat
```

Open:

- Dashboard: `http://localhost:3000`
- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`
- Health: `http://127.0.0.1:8000/api/system/health`

The local configuration defaults to:

```env
DATABASE_URL=sqlite:///./archive.db
TASK_MODE=embedded
ARCHIVE_PROVIDER=mock
```

`mock` is intentionally a development provider; it does **not** create a real public archive.

# Option B — robust Docker architecture

Install Docker Desktop, then from the root:

```powershell
docker compose up --build
```

Docker starts:

```text
Next.js frontend  :3000
FastAPI backend   :8000
PostgreSQL        internal
Redis             internal
Celery worker     internal
Celery Beat       internal
```

This is the architecture to describe in the final technical presentation even if you demonstrate local mode first.

# How the incremental pipeline works

```text
Domain
  ↓
robots.txt + sitemap.xml + HTML links
  ↓
Normalize + same-domain filter + deduplicate
  ↓
Safe bounded HTTP fetch
  ↓
SHA-256 meaningful-content fingerprint
  ↓
NEW / CHANGED / UNCHANGED
  ↓
Persistent repository
  ↓
Archive only new/changed content
  ↓
Idempotent queue
  ↓
Archive provider
  ↓
Success / retry with backoff / permanent failure
  ↓
Historical archive record
```

# Scheduled scans

Open a domain details page and click **Enable daily schedule**. The local scheduler checks due scans in embedded mode. Under Docker, Celery Beat dispatches due scans.

# Optional Playwright support

Use this only after the normal crawler is working:

```powershell
cd backend
.\.venv\Scripts\python.exe -m pip install -r requirements-playwright.txt
.\.venv\Scripts\python.exe -m playwright install chromium
```

Then set:

```env
ENABLE_PLAYWRIGHT=true
```

Playwright is a fallback, not the primary crawler, because browser rendering is significantly heavier than HTTP crawling.

# Archive provider note

Keep `ARCHIVE_PROVIDER=mock` during development. The `wayback` adapter is isolated in `backend/app/archive.py`. Before a final real submission demonstration, verify the archival service's current published submission method and terms. This project intentionally does not bypass CAPTCHA, authentication, access controls, or rate limits.

# Run tests

```powershell
cd backend
.\.venv\Scripts\python.exe -m pytest -q
```

Expected for this package:

```text
11 passed
```

# Recommended demonstration

1. Show `/api/system/health` or the dashboard system health section.
2. Add a public domain.
3. Start scan and show bounded crawler progress/results.
4. Open URL inventory and explain normalization, robots status, content size, and SHA-256 fingerprint.
5. Queue **Archive new/changed** with mock provider.
6. Show queue state, duration, retries, and historical repository.
7. Scan the same site again and show `UNCHANGED` pages being skipped.
8. Modify/test against a site with changed content and show `CHANGED` detection.
9. Stop/restart the backend and show queue persistence/recovery.
10. Enable a scheduled scan.
11. Export inventory to CSV/JSON.
12. Explain how Docker switches the same application to PostgreSQL + Redis + Celery workers.

# Main viva terms

**Asynchronous crawling, bounded concurrency, URL normalization, robots.txt, SSRF protection, content fingerprinting, incremental backup, idempotency, persistent queue, exponential backoff, failure recovery, provider abstraction, scheduled jobs, PostgreSQL, Redis, Celery, observability, Docker, CI/CD.**
