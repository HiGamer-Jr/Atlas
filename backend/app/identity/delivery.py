"""Controlled transactional outbox worker, with durable uncertain-delivery handling."""

import argparse
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from cryptography.fernet import Fernet, InvalidToken
from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.config import Settings
from app.core.errors import ApiError
from app.core.security import token_hash
from app.db.session import create_database_engine, validate_runtime_connection
from app.identity.email_transport import (
    DeliveryFailure,
    EmailMessage,
    SMTPEmailTransport,
)
from app.identity.models import EmailOutbox, SecurityToken, User
from app.identity.tokens import eligible_token, lifecycle_lock


@dataclass
class DeliverySummary:
    sent: int = 0
    failed: int = 0
    cancelled: int = 0


class DeliveryWorker:
    def __init__(self, engine, settings, transport, clock=None):
        self.engine, self.settings, self.transport = engine, settings, transport
        self.clock = clock or (lambda: datetime.now(UTC))

    def deliver_batch(self, limit: int) -> DeliverySummary:
        if not 1 <= limit <= 1000:
            raise ValueError("Limit must be between 1 and 1000")
        result = DeliverySummary()
        for _ in range(limit):
            with Session(self.engine) as db, db.begin():
                validate_runtime_connection(db.connection())
                lifecycle_lock(db)
                now = self.clock()
                # A crash after durable claim may have delivered. Never blindly resend.
                db.execute(
                    update(EmailOutbox)
                    .where(
                        EmailOutbox.status == "DISPATCHING",
                        EmailOutbox.lease_expires_at <= now,
                    )
                    .values(
                        status="UNKNOWN",
                        ciphertext=None,
                        failure_code="DELIVERY_UNKNOWN",
                        lease_expires_at=None,
                    )
                )
                row = db.scalar(
                    select(EmailOutbox)
                    .where(
                        EmailOutbox.status == "QUEUED",
                        EmailOutbox.next_attempt_at <= now,
                    )
                    .order_by(EmailOutbox.created_at, EmailOutbox.id)
                    .with_for_update(skip_locked=True)
                    .limit(1)
                )
                if row is None:
                    break
                row.status = "DISPATCHING"
                row.attempts += 1
                row.lease_expires_at = now + timedelta(
                    seconds=self.settings.email_lease_seconds
                )
                row_id = row.id
            # Separate from business HTTP transaction; durable claim before external I/O.
            with Session(self.engine) as db, db.begin():
                validate_runtime_connection(db.connection())
                lifecycle_lock(db)
                now = self.clock()
                row = db.get(EmailOutbox, row_id, with_for_update=True)
                if row.status != "DISPATCHING":
                    result.cancelled += 1
                    continue
                token = db.get(SecurityToken, row.token_id, with_for_update=True)
                user = db.get(User, token.recipient_user_id, with_for_update=True)
                try:
                    eligible_token(db, token, user, row.message_type, now)
                except ApiError:
                    row.status, row.ciphertext, row.failure_code = (
                        "CANCELLED",
                        None,
                        "TOKEN_INVALID",
                    )
                    row.lease_expires_at = None
                    result.cancelled += 1
                    continue
                # Only delivery-payload errors are recoverable here. Audit/storage errors above abort.
                try:
                    if (
                        row.recipient != token.recipient_email
                        or row.message_type != token.purpose
                    ):
                        raise ValueError("DELIVERY_INVALID")
                    raw = (
                        Fernet(self.settings.outbox_key.get_secret_value().encode())
                        .decrypt(row.ciphertext.encode())
                        .decode()
                    )
                    if token_hash(raw) != token.token_hash:
                        raise ValueError("DELIVERY_INVALID")
                except (InvalidToken, ValueError, AttributeError):
                    row.status, row.ciphertext, row.failure_code = (
                        "CANCELLED",
                        None,
                        "TOKEN_INVALID",
                    )
                    row.lease_expires_at = None
                    result.cancelled += 1
                    continue
                path = (
                    "/invite/accept" if token.purpose == "INVITE" else "/password/reset"
                )
                message = EmailMessage(
                    to=row.recipient,
                    subject="HiAtlas - acesso seguro",
                    text=f"Use este link uma unica vez para continuar:\n{self.settings.public_origin}{path}#token={raw}\nSe nao solicitou, ignore esta mensagem.",
                    id=row.id,
                )
                # Lifecycle lock ensures no committed invalidation between validation and send.
                try:
                    self.transport.send(message)
                except DeliveryFailure:
                    row.failure_code = "DELIVERY_FAILED"
                    row.status = (
                        "FAILED"
                        if row.attempts >= self.settings.email_max_attempts
                        else "QUEUED"
                    )
                    row.next_attempt_at = now + timedelta(
                        seconds=min(
                            self.settings.email_retry_seconds * 2 ** (row.attempts - 1),
                            self.settings.email_retry_max_seconds,
                        )
                    )
                    if row.status == "FAILED":
                        row.ciphertext = None
                    result.failed += 1
                except Exception:  # noqa: BLE001 -- transport boundary: persist uncertainty without exception payload
                    row.status, row.failure_code, row.ciphertext = (
                        "UNKNOWN",
                        "DELIVERY_UNKNOWN",
                        None,
                    )
                    result.failed += 1
                else:
                    row.status, row.sent_at, row.ciphertext, row.failure_code = (
                        "SENT",
                        now,
                        None,
                        None,
                    )
                    result.sent += 1
                row.lease_expires_at = None
        return result


def deliver_batch(limit: int) -> DeliverySummary:
    settings = Settings()
    engine = create_database_engine(settings.database_url)
    try:
        return DeliveryWorker(
            engine, settings, SMTPEmailTransport(settings)
        ).deliver_batch(limit)
    finally:
        engine.dispose()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--once", action="store_true", required=True)
    parser.add_argument("--limit", type=int, default=20)
    args = parser.parse_args()
    print(deliver_batch(args.limit))
