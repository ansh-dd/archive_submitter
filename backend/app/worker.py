from __future__ import annotations
import time
from datetime import datetime, timedelta, timezone
from sqlalchemy.orm import joinedload

from .archive import get_provider
from .config import settings
from .db import SessionLocal, engine
from .models import ArchiveJob, ArchiveSubmission


def utcnow():
    return datetime.now(timezone.utc)


def recover_stuck_jobs() -> int:
    db = SessionLocal()
    try:
        cutoff = utcnow() - timedelta(minutes=30)
        jobs = db.query(ArchiveJob).filter(
            ArchiveJob.status == 'PROCESSING',
            (ArchiveJob.started_at.is_(None)) | (ArchiveJob.started_at < cutoff),
        ).all()
        for job in jobs:
            job.status = 'PENDING'
            job.available_at = utcnow()
            job.error_code = 'RECOVERED'
            job.error_message = 'Recovered after interrupted worker/process.'
        db.commit()
        return len(jobs)
    finally:
        db.close()


def _claim_job(db):
    now = utcnow()
    query = (
        db.query(ArchiveJob)
        .options(joinedload(ArchiveJob.url))
        .filter(
            ArchiveJob.status.in_(['PENDING', 'RETRY']),
            ArchiveJob.available_at <= now,
        )
        .order_by(ArchiveJob.created_at.asc())
    )
    # PostgreSQL can safely let multiple workers claim different rows.
    if engine.dialect.name == 'postgresql':
        query = query.with_for_update(skip_locked=True)
    job = query.first()
    if not job:
        return None
    job.status = 'PROCESSING'
    job.started_at = now
    job.last_attempt_at = now
    db.commit()
    db.refresh(job)
    return job


def _is_temporary_failure(http_status: int | None, error_code: str | None) -> bool:
    if http_status == 429 or (http_status is not None and http_status >= 500):
        return True
    return error_code in {'TIMEOUT', 'NETWORK_ERROR'}


def process_one_job() -> bool:
    db = SessionLocal()
    job = None
    started = time.perf_counter()
    try:
        job = _claim_job(db)
        if not job:
            return False
        provider = get_provider(job.service)
        result = provider.submit(job.url.normalized_url)
        duration_ms = int((time.perf_counter() - started) * 1000)
        submission = ArchiveSubmission(
            url_id=job.url_id,
            service=job.service,
            submitted_at=utcnow(),
            status='SUCCESS' if result.success else 'FAILED',
            content_hash=job.content_hash,
            archive_url=result.archive_url,
            archive_identifier=result.archive_identifier,
            http_status=result.http_status,
            duration_ms=duration_ms,
            error_code=result.error_code,
            error_message=result.error,
        )
        db.add(submission)
        job.duration_ms = duration_ms
        if result.success:
            job.status = 'SUCCESS'
            job.completed_at = utcnow()
            job.error_code = None
            job.error_message = None
        else:
            job.retry_count += 1
            job.error_code = result.error_code or 'ARCHIVE_ERROR'
            job.error_message = result.error
            if job.retry_count < settings.max_archive_retries and _is_temporary_failure(result.http_status, result.error_code):
                job.status = 'RETRY'
                # Exponential backoff without blocking the worker thread.
                backoff = settings.archive_delay * (2 ** min(job.retry_count, 6))
                job.available_at = utcnow() + timedelta(seconds=backoff)
            else:
                job.status = 'FAILED'
                job.completed_at = utcnow()
        db.commit()
        return True
    except Exception as exc:
        db.rollback()
        if job is not None:
            try:
                job = db.get(ArchiveJob, job.id)
                job.retry_count += 1
                job.error_code = 'WORKER_EXCEPTION'
                job.error_message = str(exc)[:4000]
                if job.retry_count < settings.max_archive_retries:
                    job.status = 'RETRY'
                    job.available_at = utcnow() + timedelta(seconds=settings.archive_delay * (2 ** min(job.retry_count, 6)))
                else:
                    job.status = 'FAILED'
                    job.completed_at = utcnow()
                db.commit()
            except Exception:
                db.rollback()
        return True
    finally:
        db.close()


def run_worker_forever():
    recover_stuck_jobs()
    while True:
        worked = process_one_job()
        if not worked:
            time.sleep(settings.worker_poll_seconds)


if __name__ == '__main__':
    run_worker_forever()
