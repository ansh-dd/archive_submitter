from __future__ import annotations

import time
from dataclasses import dataclass
from urllib.parse import quote

import httpx

from .config import settings


@dataclass
class ArchiveResult:
    success: bool
    archive_url: str | None = None
    archive_identifier: str | None = None
    http_status: int | None = None
    error_code: str | None = None
    error: str | None = None


class ArchiveProvider:
    name = "base"

    def submit(self, url: str) -> ArchiveResult:
        raise NotImplementedError


class WaybackProvider(ArchiveProvider):
    name = "wayback"

    def _headers(self) -> dict[str, str]:
        if not settings.wayback_access_key:
            raise RuntimeError(
                "WAYBACK_ACCESS_KEY is missing."
            )

        if not settings.wayback_secret_key:
            raise RuntimeError(
                "WAYBACK_SECRET_KEY is missing."
            )

        return {
            "Accept": "application/json",
            "Authorization": (
                f"LOW "
                f"{settings.wayback_access_key}:"
                f"{settings.wayback_secret_key}"
            ),
            "User-Agent": settings.user_agent,
        }

    def _success_result(
        self,
        data: dict,
        job_id: str,
        fallback_url: str,
    ) -> ArchiveResult:

        timestamp = data.get("timestamp")

        original_url = (
            data.get("original_url")
            or fallback_url
        )

        archive_url = None

        if timestamp and original_url:
            archive_url = (
                "https://web.archive.org/web/"
                f"{timestamp}/{original_url}"
            )

        return ArchiveResult(
            success=True,
            archive_url=archive_url,
            archive_identifier=job_id,
            http_status=data.get("http_status"),
        )

    def submit(self, url: str) -> ArchiveResult:

        try:
            headers = self._headers()

        except RuntimeError as exc:
            return ArchiveResult(
                success=False,
                error_code="AUTH_MISSING",
                error=str(exc),
            )

        save_endpoint = (
            settings.wayback_save_base.rstrip("/")
        )

        try:

            with httpx.Client(
                timeout=60,
                follow_redirects=True,
                headers=headers,
            ) as client:

                # STEP 1:
                # Submit capture request to Save Page Now.
                response = client.post(
                    save_endpoint,
                    data={
                        "url": url,
                        "capture_all": "1",
                    },
                )

                if response.status_code == 429:
                    return ArchiveResult(
                        success=False,
                        http_status=429,
                        error_code="HTTP_429",
                        error=(
                            "Internet Archive rate limit "
                            "was reached."
                        ),
                    )

                if response.status_code in {
                    401,
                    403,
                }:
                    return ArchiveResult(
                        success=False,
                        http_status=response.status_code,
                        error_code="AUTH_FAILED",
                        error=(
                            "Internet Archive rejected "
                            "the supplied credentials."
                        ),
                    )

                if response.status_code >= 500:
                    return ArchiveResult(
                        success=False,
                        http_status=response.status_code,
                        error_code=(
                            f"HTTP_{response.status_code}"
                        ),
                        error=(
                            "Internet Archive returned "
                            "a temporary server error."
                        ),
                    )

                if response.status_code >= 400:
                    return ArchiveResult(
                        success=False,
                        http_status=response.status_code,
                        error_code=(
                            f"HTTP_{response.status_code}"
                        ),
                        error=(
                            "Wayback submission failed: "
                            f"{response.text[:500]}"
                        ),
                    )

                try:
                    submit_data = response.json()

                except ValueError:
                    return ArchiveResult(
                        success=False,
                        http_status=response.status_code,
                        error_code="INVALID_RESPONSE",
                        error=(
                            "Internet Archive returned "
                            "a non-JSON response."
                        ),
                    )

                # Occasionally a result may already
                # contain completed capture information.
                if (
                    submit_data.get("status")
                    == "success"
                ):
                    job_id = (
                        submit_data.get("job_id")
                        or "WAYBACK"
                    )

                    return self._success_result(
                        submit_data,
                        job_id,
                        url,
                    )

                job_id = submit_data.get("job_id")

                if not job_id:
                    return ArchiveResult(
                        success=False,
                        http_status=response.status_code,
                        error_code="NO_JOB_ID",
                        error=(
                            submit_data.get("message")
                            or (
                                "Internet Archive did not "
                                "return a capture job ID."
                            )
                        ),
                    )

                # STEP 2:
                # Poll Save Page Now job status.
                status_endpoint = (
                    f"{save_endpoint}/status/"
                    f"{job_id}"
                )

                # 60 checks × 2 seconds = about 2 minutes.
                for _ in range(60):

                    time.sleep(2)

                    status_response = client.get(
                        status_endpoint
                    )

                    if (
                        status_response.status_code
                        == 429
                    ):
                        return ArchiveResult(
                            success=False,
                            archive_identifier=job_id,
                            http_status=429,
                            error_code="HTTP_429",
                            error=(
                                "Rate limit reached while "
                                "checking Wayback status."
                            ),
                        )

                    if (
                        status_response.status_code
                        >= 500
                    ):
                        continue

                    if (
                        status_response.status_code
                        >= 400
                    ):
                        return ArchiveResult(
                            success=False,
                            archive_identifier=job_id,
                            http_status=(
                                status_response.status_code
                            ),
                            error_code=(
                                "STATUS_HTTP_"
                                f"{status_response.status_code}"
                            ),
                            error=(
                                "Unable to retrieve Wayback "
                                "capture status."
                            ),
                        )

                    try:
                        status_data = (
                            status_response.json()
                        )

                    except ValueError:
                        continue

                    status = status_data.get("status")

                    if status == "success":

                        return self._success_result(
                            status_data,
                            job_id,
                            url,
                        )

                    if status == "error":

                        return ArchiveResult(
                            success=False,
                            archive_identifier=job_id,
                            http_status=(
                                status_data.get(
                                    "http_status"
                                )
                            ),
                            error_code=(
                                status_data.get(
                                    "status_ext"
                                )
                                or "WAYBACK_ERROR"
                            ),
                            error=(
                                status_data.get(
                                    "message"
                                )
                                or status_data.get(
                                    "exception"
                                )
                                or (
                                    "Internet Archive "
                                    "capture failed."
                                )
                            ),
                        )

                    # Any "pending" result simply
                    # continues to the next poll.

                return ArchiveResult(
                    success=False,
                    archive_identifier=job_id,
                    error_code="TIMEOUT",
                    error=(
                        "Wayback capture did not finish "
                        "within approximately 120 seconds."
                    ),
                )

        except httpx.TimeoutException as exc:

            return ArchiveResult(
                success=False,
                error_code="TIMEOUT",
                error=str(exc),
            )

        except httpx.HTTPError as exc:

            return ArchiveResult(
                success=False,
                error_code="NETWORK_ERROR",
                error=str(exc),
            )

        except Exception as exc:

            return ArchiveResult(
                success=False,
                error_code="WAYBACK_EXCEPTION",
                error=str(exc),
            )

class ArchiveTodayProvider(ArchiveProvider):
    name = "archive_today"

    def submit(self, url: str) -> ArchiveResult:
        """
        Archive.today / Archive.is currently has no verified
        documented public automation API for this project.

        We intentionally do not automate its submission form
        or bypass CAPTCHA / access controls.
        """

        return ArchiveResult(
            success=False,
            archive_identifier="MANUAL_ONLY",
            error_code="MANUAL_SUBMISSION_REQUIRED",
            error=(
                "Archive.today / Archive.is requires manual "
                "submission. No verified public automation API "
                "is configured, and this application does not "
                "bypass CAPTCHA, authentication, rate limits, "
                "or other access controls."
            ),
        )


class MockProvider(ArchiveProvider):
    name = "mock"

    def submit(self, url: str) -> ArchiveResult:

        # Development/demo provider only.
        # It does NOT create a real public archive.
        return ArchiveResult(
            success=True,
            archive_url=(
                "https://example.invalid/"
                "mock-archive?url="
                f"{quote(url, safe='')}"
            ),
            archive_identifier="LOCAL-DEMO",
            http_status=200,
        )


def get_provider(
    name: str | None = None,
) -> ArchiveProvider:

    selected = (
        name
        or settings.archive_provider
    ).lower()

    if selected == "mock":
        return MockProvider()

    if selected == "wayback":
        return WaybackProvider()

    if selected in {
        "archive_today",
        "archive.today",
        "archive.is",
    }:
        return ArchiveTodayProvider()

    raise ValueError(
        f"Unsupported archive provider: "
        f"{selected}"
    )
