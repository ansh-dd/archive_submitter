from __future__ import annotations
import time
from datetime import timedelta

from .config import settings
from .db import SessionLocal
from .models import Domain, utcnow


def dispatch_due_scans(dispatch_func) -> int:
    db = SessionLocal()
    try:
        now = utcnow()
        domains = db.query(Domain).filter(
            Domain.scheduled_scan_enabled.is_(True),
            Domain.next_scan_at.isnot(None),
            Domain.next_scan_at <= now,
            Domain.status != 'SCANNING',
        ).all()
        count = 0
        for domain in domains:
            # Move next_scan_at first to avoid duplicate dispatch if the scheduler loops quickly.
            domain.next_scan_at = now + timedelta(minutes=max(15, domain.scan_interval_minutes))
            db.commit()
            dispatch_func(domain.id)
            count += 1
        return count
    finally:
        db.close()


def run_scheduler_forever(dispatch_func):
    while True:
        dispatch_due_scans(dispatch_func)
        time.sleep(settings.scheduler_poll_seconds)
