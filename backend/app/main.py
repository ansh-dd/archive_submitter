from __future__ import annotations

import csv
import io
from datetime import timedelta
from threading import Thread
from urllib.parse import urlsplit, urlunsplit
from uuid import uuid4

from fastapi import BackgroundTasks, Depends, FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from sqlalchemy import func, or_, text
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from .archive import get_provider
from .config import settings
from .crawler import crawl_domain, normalize_url
from .db import Base, SessionLocal, engine, get_db
from .models import ArchiveJob, ArchiveSubmission, CrawlRun, Domain, URLRecord, utcnow
from .schemas import ArchiveRequest, DomainCreate, ScheduleRequest
from .scheduler import run_scheduler_forever
from .security import assert_public_http_url
from .worker import recover_stuck_jobs, run_worker_forever

Base.metadata.create_all(bind=engine)

app = FastAPI(
    title=settings.app_name,
    version='2.0.0',
    description='Fault-tolerant website discovery, incremental change detection, archival queue, and repository API.',
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=['*'],
    allow_headers=['*'],
)


def _crawl_task(domain_id: int):
    db = SessionLocal()
    try:
        crawl_domain(db, domain_id)
    finally:
        db.close()


def dispatch_scan(domain_id: int, background: BackgroundTasks | None = None):
    if settings.task_mode == 'celery':
        from .tasks import crawl_domain_task
        crawl_domain_task.delay(domain_id)
    elif background is not None:
        background.add_task(_crawl_task, domain_id)
    else:
        Thread(target=_crawl_task, args=(domain_id,), daemon=True, name=f'crawl-{domain_id}').start()


@app.on_event('startup')
def startup_event():
    recover_stuck_jobs()
    if settings.task_mode == 'embedded' and settings.embedded_worker:
        Thread(target=run_worker_forever, daemon=True, name='archive-worker').start()
        Thread(target=run_scheduler_forever, args=(lambda domain_id: dispatch_scan(domain_id),), daemon=True, name='scan-scheduler').start()


@app.get('/')
def root():
    return {
        'message': 'Website Archive Submitter API is running',
        'version': '2.0.0',
        'docs': '/docs',
        'task_mode': settings.task_mode,
    }


def serialize_domain(db: Session, d: Domain):
    total = db.query(func.count(URLRecord.id)).filter(URLRecord.domain_id == d.id).scalar() or 0
    changed = db.query(func.count(URLRecord.id)).filter(URLRecord.domain_id == d.id, URLRecord.change_status == 'CHANGED').scalar() or 0
    new = db.query(func.count(URLRecord.id)).filter(URLRecord.domain_id == d.id, URLRecord.change_status == 'NEW').scalar() or 0
    archived = (
        db.query(func.count(func.distinct(ArchiveSubmission.url_id)))
        .join(URLRecord, URLRecord.id == ArchiveSubmission.url_id)
        .filter(URLRecord.domain_id == d.id, ArchiveSubmission.status == 'SUCCESS')
        .scalar() or 0
    )
    pending = (
        db.query(func.count(ArchiveJob.id)).join(URLRecord, URLRecord.id == ArchiveJob.url_id)
        .filter(URLRecord.domain_id == d.id, ArchiveJob.status.in_(['PENDING', 'PROCESSING', 'RETRY'])).scalar() or 0
    )
    failed = (
        db.query(func.count(ArchiveJob.id)).join(URLRecord, URLRecord.id == ArchiveJob.url_id)
        .filter(URLRecord.domain_id == d.id, ArchiveJob.status == 'FAILED').scalar() or 0
    )
    latest_run = db.query(CrawlRun).filter(CrawlRun.domain_id == d.id).order_by(CrawlRun.started_at.desc()).first()
    return {
        'id': d.id, 'base_url': d.base_url, 'hostname': d.hostname, 'status': d.status,
        'created_at': d.created_at, 'last_scan_at': d.last_scan_at,
        'scheduled_scan_enabled': d.scheduled_scan_enabled, 'scan_interval_minutes': d.scan_interval_minutes,
        'next_scan_at': d.next_scan_at,
        'total_urls': total, 'new_urls': new, 'changed_urls': changed,
        'archived_urls': archived, 'pending_jobs': pending, 'failed_jobs': failed,
        'latest_scan': None if not latest_run else {
            'id': latest_run.id, 'status': latest_run.status, 'urls_found': latest_run.urls_found,
            'new_urls_found': latest_run.new_urls_found, 'changed_urls_found': latest_run.changed_urls_found,
            'pages_fetched': latest_run.pages_fetched, 'duration_ms': latest_run.duration_ms,
            'started_at': latest_run.started_at, 'finished_at': latest_run.finished_at,
            'error_message': latest_run.error_message,
        },
    }


@app.get('/health')
def health(db: Session = Depends(get_db)):
    db.execute(text('SELECT 1'))
    return {'status': 'ok', 'service': settings.app_name, 'archive_provider': settings.archive_provider, 'task_mode': settings.task_mode}


@app.get('/api/system/health')
def system_health(db: Session = Depends(get_db)):
    database = 'healthy'
    redis_status = 'not_required'
    try:
        db.execute(text('SELECT 1'))
    except Exception:
        database = 'unhealthy'
    if settings.task_mode == 'celery':
        try:
            import redis
            client = redis.Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
            redis_status = 'healthy' if client.ping() else 'unhealthy'
        except Exception:
            redis_status = 'unhealthy'
    return {
        'api': 'healthy',
        'database': database,
        'redis': redis_status,
        'task_mode': settings.task_mode,
        'archive_provider': settings.archive_provider,
        'crawler_concurrency': settings.max_concurrent_requests,
        'max_response_size_mb': settings.max_response_size_mb,
    }


@app.get('/api/stats')
def stats(db: Session = Depends(get_db)):
    successful = db.query(func.count(ArchiveSubmission.id)).filter(ArchiveSubmission.status == 'SUCCESS').scalar() or 0
    failed_submissions = db.query(func.count(ArchiveSubmission.id)).filter(ArchiveSubmission.status == 'FAILED').scalar() or 0
    total_submissions = successful + failed_submissions
    avg_archive_ms = db.query(func.avg(ArchiveSubmission.duration_ms)).filter(ArchiveSubmission.duration_ms.isnot(None)).scalar()
    avg_crawl_ms = db.query(func.avg(CrawlRun.duration_ms)).filter(CrawlRun.status == 'SUCCESS').scalar()
    return {
        'domains': db.query(func.count(Domain.id)).scalar() or 0,
        'urls': db.query(func.count(URLRecord.id)).scalar() or 0,
        'new_urls': db.query(func.count(URLRecord.id)).filter(URLRecord.change_status == 'NEW').scalar() or 0,
        'changed_urls': db.query(func.count(URLRecord.id)).filter(URLRecord.change_status == 'CHANGED').scalar() or 0,
        'queued': db.query(func.count(ArchiveJob.id)).filter(ArchiveJob.status.in_(['PENDING', 'PROCESSING', 'RETRY'])).scalar() or 0,
        'successful': successful,
        'failed': db.query(func.count(ArchiveJob.id)).filter(ArchiveJob.status == 'FAILED').scalar() or 0,
        'success_rate': round((successful / total_submissions * 100), 2) if total_submissions else 0,
        'avg_archive_ms': round(float(avg_archive_ms or 0), 1),
        'avg_crawl_ms': round(float(avg_crawl_ms or 0), 1),
    }


@app.post('/api/domains', status_code=201)
def create_domain(payload: DomainCreate, db: Session = Depends(get_db)):
    raw = str(payload.url)
    try:
        assert_public_http_url(raw)
    except ValueError as exc:
        raise HTTPException(400, str(exc))
    p = urlsplit(raw)
    base = normalize_url(urlunsplit((p.scheme.lower(), p.netloc.lower(), p.path or '/', '', '')))
    exists = db.query(Domain).filter(Domain.base_url == base).first()
    if exists:
        return serialize_domain(db, exists)
    d = Domain(base_url=base, hostname=(p.hostname or '').lower(), scan_interval_minutes=settings.default_scan_interval_minutes)
    db.add(d)
    db.commit()
    db.refresh(d)
    return serialize_domain(db, d)


@app.get('/api/domains')
def list_domains(db: Session = Depends(get_db)):
    return [serialize_domain(db, d) for d in db.query(Domain).order_by(Domain.created_at.desc()).all()]


@app.get('/api/domains/{domain_id}')
def get_domain(domain_id: int, db: Session = Depends(get_db)):
    d = db.get(Domain, domain_id)
    if not d:
        raise HTTPException(404, 'Domain not found')
    return serialize_domain(db, d)


@app.post('/api/domains/{domain_id}/scan', status_code=202)
def start_scan(domain_id: int, background: BackgroundTasks, db: Session = Depends(get_db)):
    d = db.get(Domain, domain_id)
    if not d:
        raise HTTPException(404, 'Domain not found')
    if d.status == 'SCANNING':
        return {'message': 'Scan is already running.'}
    d.status = 'SCANNING'
    db.commit()
    dispatch_scan(domain_id, background)
    return {'message': 'Discovery started.', 'domain_id': domain_id, 'mode': settings.task_mode}


@app.post('/api/domains/{domain_id}/schedule')
def set_schedule(domain_id: int, payload: ScheduleRequest, db: Session = Depends(get_db)):
    d = db.get(Domain, domain_id)
    if not d:
        raise HTTPException(404, 'Domain not found')
    d.scheduled_scan_enabled = payload.enabled
    d.scan_interval_minutes = payload.interval_minutes
    d.next_scan_at = utcnow() + timedelta(minutes=payload.interval_minutes) if payload.enabled else None
    db.commit()
    return serialize_domain(db, d)


@app.get('/api/domains/{domain_id}/urls')
def list_urls(domain_id: int, q: str = '', limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    if not db.get(Domain, domain_id):
        raise HTTPException(404, 'Domain not found')
    query = db.query(URLRecord).filter(URLRecord.domain_id == domain_id)
    if q:
        query = query.filter(or_(URLRecord.original_url.ilike(f'%{q}%'), URLRecord.normalized_url.ilike(f'%{q}%')))
    rows = query.order_by(URLRecord.id.asc()).limit(limit).all()
    out = []
    for r in rows:
        success = db.query(ArchiveSubmission).filter(ArchiveSubmission.url_id == r.id, ArchiveSubmission.status == 'SUCCESS').order_by(ArchiveSubmission.submitted_at.desc()).first()
        latest_job = db.query(ArchiveJob).filter(ArchiveJob.url_id == r.id).order_by(ArchiveJob.created_at.desc()).first()
        out.append({
            'id': r.id, 'original_url': r.original_url, 'normalized_url': r.normalized_url,
            'discovery_source': r.discovery_source, 'http_status': r.http_status,
            'content_type': r.content_type, 'content_length': r.content_length,
            'content_hash': r.content_hash, 'change_status': r.change_status,
            'robots_allowed': r.robots_allowed, 'etag': r.etag, 'last_modified': r.last_modified,
            'discovered_at': r.discovered_at, 'last_seen_at': r.last_seen_at, 'last_checked_at': r.last_checked_at,
            'archive_status': latest_job.status if latest_job else 'NOT_QUEUED',
            'archive_url': success.archive_url if success else None,
        })
    return out


@app.post('/api/domains/{domain_id}/archive', status_code=202)
def queue_domain(domain_id: int, payload: ArchiveRequest, db: Session = Depends(get_db)):
    d = db.get(Domain, domain_id)
    if not d:
        raise HTTPException(404, 'Domain not found')
    service = (payload.service or settings.archive_provider).lower()
    try:
        get_provider(service)
    except ValueError as exc:
        raise HTTPException(400, str(exc))

    urls = db.query(URLRecord).filter(URLRecord.domain_id == domain_id).all()
    created = skipped = blocked = 0
    for u in urls:
        if not u.robots_allowed or (u.http_status is not None and u.http_status >= 400):
            blocked += 1
            continue
        # Incremental archiving: if the same content fingerprint was already archived, skip it.
        if not payload.force and payload.changed_only:
            same_capture = db.query(ArchiveSubmission).filter(
                ArchiveSubmission.url_id == u.id,
                ArchiveSubmission.service == service,
                ArchiveSubmission.status == 'SUCCESS',
                ArchiveSubmission.content_hash == u.content_hash,
            ).first()
            if same_capture:
                skipped += 1
                continue
        hash_part = u.content_hash or 'nohash'
        idem = f'{u.id}:{service}:{hash_part}'
        if payload.force:
            idem = f'{idem}:force:{uuid4().hex}'
        existing = db.query(ArchiveJob).filter(ArchiveJob.idempotency_key == idem).first()
        if existing:
            skipped += 1
            continue
        try:
            with db.begin_nested():
                db.add(ArchiveJob(
                    url_id=u.id, service=service, status='PENDING', content_hash=u.content_hash,
                    idempotency_key=idem, available_at=utcnow(),
                ))
                db.flush()
            created += 1
        except IntegrityError:
            skipped += 1
    db.commit()
    return {
        'message': 'Archive jobs queued.', 'created': created, 'skipped': skipped,
        'blocked_or_inaccessible': blocked, 'service': service,
    }


@app.get('/api/jobs')
def list_jobs(status: str | None = None, limit: int = Query(200, ge=1, le=1000), db: Session = Depends(get_db)):
    q = db.query(ArchiveJob).join(URLRecord).join(Domain)
    if status:
        q = q.filter(ArchiveJob.status == status.upper())
    rows = q.order_by(ArchiveJob.created_at.desc()).limit(limit).all()
    return [{
        'id': j.id, 'status': j.status, 'service': j.service, 'retry_count': j.retry_count,
        'created_at': j.created_at, 'available_at': j.available_at, 'started_at': j.started_at,
        'completed_at': j.completed_at, 'duration_ms': j.duration_ms,
        'error_code': j.error_code, 'error_message': j.error_message,
        'content_hash': j.content_hash, 'url': j.url.normalized_url, 'domain': j.url.domain.hostname,
    } for j in rows]


@app.post('/api/jobs/{job_id}/retry')
def retry_job(job_id: int, db: Session = Depends(get_db)):
    job = db.get(ArchiveJob, job_id)
    if not job:
        raise HTTPException(404, 'Job not found')
    job.status = 'RETRY'
    job.available_at = utcnow()
    job.completed_at = None
    job.error_code = None
    job.error_message = None
    db.commit()
    return {'message': 'Job queued for retry.'}


@app.get('/api/repository')
def repository(q: str = '', service: str = '', status: str = '', limit: int = Query(300, ge=1, le=1000), db: Session = Depends(get_db)):
    query = db.query(ArchiveSubmission).join(URLRecord).join(Domain)
    if q:
        query = query.filter(or_(URLRecord.normalized_url.ilike(f'%{q}%'), Domain.hostname.ilike(f'%{q}%')))
    if service:
        query = query.filter(ArchiveSubmission.service == service)
    if status:
        query = query.filter(ArchiveSubmission.status == status.upper())
    rows = query.order_by(ArchiveSubmission.submitted_at.desc()).limit(limit).all()
    return [{
        'id': s.id, 'domain': s.url.domain.hostname, 'url': s.url.normalized_url,
        'service': s.service, 'status': s.status, 'submitted_at': s.submitted_at,
        'content_hash': s.content_hash, 'duration_ms': s.duration_ms,
        'archive_url': s.archive_url, 'archive_identifier': s.archive_identifier,
        'http_status': s.http_status, 'error_code': s.error_code, 'error_message': s.error_message,
    } for s in rows]


@app.get('/api/domains/{domain_id}/export')
def export_inventory(domain_id: int, format: str = Query('csv', pattern='^(csv|json)$'), db: Session = Depends(get_db)):
    d = db.get(Domain, domain_id)
    if not d:
        raise HTTPException(404, 'Domain not found')
    rows = db.query(URLRecord).filter(URLRecord.domain_id == domain_id).order_by(URLRecord.id).all()
    data = [{
        'url': r.normalized_url, 'original_url': r.original_url, 'source': r.discovery_source,
        'http_status': r.http_status, 'change_status': r.change_status, 'content_hash': r.content_hash,
        'content_length': r.content_length, 'robots_allowed': r.robots_allowed,
        'discovered_at': r.discovered_at.isoformat() if r.discovered_at else None,
        'last_seen_at': r.last_seen_at.isoformat() if r.last_seen_at else None,
    } for r in rows]
    if format == 'json':
        import json
        body = json.dumps(data, indent=2)
        return StreamingResponse(io.BytesIO(body.encode()), media_type='application/json', headers={'Content-Disposition': f'attachment; filename="{d.hostname}-inventory.json"'})
    output = io.StringIO()
    fields = list(data[0].keys()) if data else ['url']
    writer = csv.DictWriter(output, fieldnames=fields)
    writer.writeheader()
    writer.writerows(data)
    return StreamingResponse(io.BytesIO(output.getvalue().encode('utf-8-sig')), media_type='text/csv', headers={'Content-Disposition': f'attachment; filename="{d.hostname}-inventory.csv"'})
