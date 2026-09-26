from celery import Celery
from celery.schedules import crontab
from .config import settings

celery_app = Celery(
    'website_archive_submitter',
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=['app.tasks'],
)
celery_app.conf.update(
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    worker_prefetch_multiplier=1,
    broker_connection_retry_on_startup=True,
    timezone='UTC',
    beat_schedule={
        'dispatch-due-domain-scans': {
            'task': 'app.tasks.dispatch_scheduled_scans',
            'schedule': crontab(minute='*'),
        },
        'process-archive-queue': {
            'task': 'app.tasks.process_archive_queue',
            'schedule': 2.0,
        },
    },
)
