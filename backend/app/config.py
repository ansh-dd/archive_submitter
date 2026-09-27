import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BASE_DIR / '.env')


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {'1', 'true', 'yes', 'on'}


class Settings:
    app_name = os.getenv('APP_NAME', 'Website Archive Submitter API')
    environment = os.getenv('ENVIRONMENT', 'development')
    database_url = os.getenv('DATABASE_URL', f"sqlite:///{BASE_DIR / 'archive.db'}")
    cors_origins = [x.strip() for x in os.getenv('CORS_ORIGINS', 'http://localhost:3000').split(',') if x.strip()]

    # Crawler
    user_agent = os.getenv('CRAWLER_USER_AGENT', 'PillaiArchiveSubmitter/2.0 (+student project)')
    request_timeout = float(os.getenv('REQUEST_TIMEOUT_SECONDS', '15'))
    max_crawl_pages = int(os.getenv('MAX_CRAWL_PAGES', '500'))
    max_sitemap_urls = int(os.getenv('MAX_SITEMAP_URLS', '10000'))
    max_crawl_depth = int(os.getenv('MAX_CRAWL_DEPTH', '8'))
    max_concurrent_requests = int(os.getenv('MAX_CONCURRENT_REQUESTS', '5'))
    crawl_delay = float(os.getenv('CRAWL_DELAY_SECONDS', '0.10'))
    max_response_size_mb = int(os.getenv('MAX_RESPONSE_SIZE_MB', '10'))
    enable_playwright = _bool('ENABLE_PLAYWRIGHT', False)

    # Archive queue/provider
    archive_provider = os.getenv('ARCHIVE_PROVIDER', 'mock').lower()
    archive_delay = float(os.getenv('ARCHIVE_DELAY_SECONDS', '2'))
    max_archive_retries = int(os.getenv('MAX_ARCHIVE_RETRIES', '4'))
    wayback_save_base = os.getenv('WAYBACK_SAVE_BASE', 'https://web.archive.org/save/')
    wayback_access_key = os.getenv('WAYBACK_ACCESS_KEY', '').strip()
    wayback_secret_key = os.getenv('WAYBACK_SECRET_KEY', '').strip()


    # Processing mode: local embedded workers or Redis/Celery.
    task_mode = os.getenv('TASK_MODE', 'embedded').lower()
    embedded_worker = _bool('EMBEDDED_WORKER', True)
    worker_poll_seconds = float(os.getenv('WORKER_POLL_SECONDS', '2'))
    scheduler_poll_seconds = float(os.getenv('SCHEDULER_POLL_SECONDS', '30'))
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379/0')
    celery_broker_url = os.getenv('CELERY_BROKER_URL', redis_url)
    celery_result_backend = os.getenv('CELERY_RESULT_BACKEND', redis_url)

    # Recurring scans
    default_scan_interval_minutes = int(os.getenv('DEFAULT_SCAN_INTERVAL_MINUTES', '1440'))

settings = Settings()
