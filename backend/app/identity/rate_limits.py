"""Shared, transactional failure counters; no process-local authentication state."""

from datetime import timedelta
from math import ceil

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert

from app.core.errors import ApiError
from app.core.security import token_hash
from app.identity.models import AuthRateLimit


def lock_buckets(db, identifier, source, now, settings):
    keys = {
        token_hash("identifier:" + identifier): settings.auth_identifier_limit,
        token_hash("source:" + source): settings.auth_source_limit,
    }
    buckets = []
    for key in sorted(keys):
        db.execute(
            insert(AuthRateLimit)
            .values(bucket_key=key, window_started_at=now, failures=0)
            .on_conflict_do_nothing()
        )
        bucket = db.scalar(
            select(AuthRateLimit)
            .where(AuthRateLimit.bucket_key == key)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if now >= bucket.window_started_at + timedelta(
            seconds=settings.auth_window_seconds
        ):
            bucket.window_started_at, bucket.failures = now, 0
        buckets.append((bucket, keys[key]))
    for bucket, limit in buckets:
        if bucket.failures >= limit:
            seconds = max(
                1,
                ceil(
                    (
                        bucket.window_started_at
                        + timedelta(seconds=settings.auth_window_seconds)
                        - now
                    ).total_seconds()
                ),
            )
            return [entry[0] for entry in buckets], ApiError(
                429, "AUTH_RATE_LIMITED", "Aguarde antes de tentar novamente.", seconds
            )
    return [entry[0] for entry in buckets], None


def record_failure(buckets):
    for bucket in buckets:
        bucket.failures += 1
