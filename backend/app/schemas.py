from pydantic import BaseModel, HttpUrl, Field


class DomainCreate(BaseModel):
    url: HttpUrl


class ArchiveRequest(BaseModel):
    force: bool = False
    changed_only: bool = True
    service: str | None = None


class ScheduleRequest(BaseModel):
    enabled: bool = True
    interval_minutes: int = Field(default=1440, ge=15, le=525600)
