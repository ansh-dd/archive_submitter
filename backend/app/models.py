from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, Integer, String, Text, DateTime, ForeignKey, UniqueConstraint, Index
from sqlalchemy.orm import relationship
from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Domain(Base):
    __tablename__ = 'domains'
    id = Column(Integer, primary_key=True)
    base_url = Column(String(2048), unique=True, nullable=False, index=True)
    hostname = Column(String(255), nullable=False, index=True)
    status = Column(String(40), default='READY', nullable=False)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_scan_at = Column(DateTime(timezone=True))
    scheduled_scan_enabled = Column(Boolean, default=False, nullable=False)
    scan_interval_minutes = Column(Integer, default=1440, nullable=False)
    next_scan_at = Column(DateTime(timezone=True))

    urls = relationship('URLRecord', back_populates='domain', cascade='all, delete-orphan')
    crawl_runs = relationship('CrawlRun', back_populates='domain', cascade='all, delete-orphan')


class CrawlRun(Base):
    __tablename__ = 'crawl_runs'
    id = Column(Integer, primary_key=True)
    domain_id = Column(Integer, ForeignKey('domains.id', ondelete='CASCADE'), nullable=False, index=True)
    status = Column(String(40), default='RUNNING', nullable=False)
    started_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True))
    urls_found = Column(Integer, default=0, nullable=False)
    new_urls_found = Column(Integer, default=0, nullable=False)
    changed_urls_found = Column(Integer, default=0, nullable=False)
    pages_fetched = Column(Integer, default=0, nullable=False)
    duration_ms = Column(Integer, default=0, nullable=False)
    error_message = Column(Text)

    domain = relationship('Domain', back_populates='crawl_runs')


class URLRecord(Base):
    __tablename__ = 'urls'
    __table_args__ = (
        UniqueConstraint('domain_id', 'normalized_url', name='uq_domain_normalized_url'),
        Index('ix_urls_domain_last_seen', 'domain_id', 'last_seen_at'),
    )
    id = Column(Integer, primary_key=True)
    domain_id = Column(Integer, ForeignKey('domains.id', ondelete='CASCADE'), nullable=False, index=True)
    original_url = Column(String(4096), nullable=False)
    normalized_url = Column(String(4096), nullable=False)
    discovery_source = Column(String(80), nullable=False)
    http_status = Column(Integer)
    redirect_url = Column(String(4096))
    content_type = Column(String(255))
    content_length = Column(Integer)
    content_hash = Column(String(64), index=True)
    previous_content_hash = Column(String(64))
    etag = Column(String(512))
    last_modified = Column(String(512))
    change_status = Column(String(40), default='NEW', nullable=False, index=True)
    robots_allowed = Column(Boolean, default=True, nullable=False)
    discovered_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_seen_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    last_checked_at = Column(DateTime(timezone=True))

    domain = relationship('Domain', back_populates='urls')
    jobs = relationship('ArchiveJob', back_populates='url', cascade='all, delete-orphan')
    submissions = relationship('ArchiveSubmission', back_populates='url', cascade='all, delete-orphan')


class ArchiveJob(Base):
    __tablename__ = 'archive_jobs'
    __table_args__ = (Index('ix_jobs_status_created', 'status', 'created_at'),)
    id = Column(Integer, primary_key=True)
    url_id = Column(Integer, ForeignKey('urls.id', ondelete='CASCADE'), nullable=False, index=True)
    service = Column(String(80), nullable=False, index=True)
    status = Column(String(40), default='PENDING', nullable=False, index=True)
    retry_count = Column(Integer, default=0, nullable=False)
    content_hash = Column(String(64))
    idempotency_key = Column(String(255), unique=True, nullable=False, index=True)
    created_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    available_at = Column(DateTime(timezone=True), default=utcnow, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True))
    completed_at = Column(DateTime(timezone=True))
    last_attempt_at = Column(DateTime(timezone=True))
    duration_ms = Column(Integer)
    error_code = Column(String(80))
    error_message = Column(Text)

    url = relationship('URLRecord', back_populates='jobs')


class ArchiveSubmission(Base):
    __tablename__ = 'archive_submissions'
    id = Column(Integer, primary_key=True)
    url_id = Column(Integer, ForeignKey('urls.id', ondelete='CASCADE'), nullable=False, index=True)
    service = Column(String(80), nullable=False, index=True)
    submitted_at = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    status = Column(String(40), nullable=False, index=True)
    content_hash = Column(String(64), index=True)
    archive_url = Column(String(4096))
    archive_identifier = Column(String(512))
    http_status = Column(Integer)
    duration_ms = Column(Integer)
    error_code = Column(String(80))
    error_message = Column(Text)

    url = relationship('URLRecord', back_populates='submissions')
