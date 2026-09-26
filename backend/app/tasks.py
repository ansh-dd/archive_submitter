from .celery_app import celery_app
from .crawler import crawl_domain
from .db import SessionLocal
from .scheduler import dispatch_due_scans
from .worker import process_one_job, recover_stuck_jobs


@celery_app.task(name='app.tasks.crawl_domain_task')
def crawl_domain_task(domain_id: int):
    db = SessionLocal()
    try:
        crawl_domain(db, domain_id)
    finally:
        db.close()


@celery_app.task(name='app.tasks.process_archive_queue')
def process_archive_queue():
    recover_stuck_jobs()
    processed = 0
    # Process a small batch per invocation; multiple Celery workers can scale horizontally.
    for _ in range(25):
        if not process_one_job():
            break
        processed += 1
    return {'processed': processed}


@celery_app.task(name='app.tasks.dispatch_scheduled_scans')
def dispatch_scheduled_scans():
    return {'dispatched': dispatch_due_scans(lambda domain_id: crawl_domain_task.delay(domain_id))}
