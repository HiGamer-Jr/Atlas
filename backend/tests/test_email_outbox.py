from concurrent.futures import ThreadPoolExecutor
from dataclasses import asdict
from threading import Barrier

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.identity.delivery import DeliveryWorker
from app.identity.models import EmailOutbox, SecurityToken
from tests.identity_helpers import csrf
from tests.test_access_tokens import token_from


def enqueue(client, email="member@example.test"):
    csrf(client)
    assert client.post("/api/auth/recovery", json={"email": email}).status_code == 202


def test_outbox_encrypted_deleted_after_delivery(client, mail, auth_users, db_runtime):
    enqueue(client)
    transport, worker = mail
    with Session(db_runtime) as db:
        row = db.scalar(select(EmailOutbox))
        assert row.ciphertext and "https" not in row.ciphertext
        assert row.status == "QUEUED" and row.attempts == 0
    assert asdict(worker.deliver_batch(10)) == {"sent": 1, "failed": 0, "cancelled": 0}
    assert worker.deliver_batch(10).sent == 0
    assert len(transport.messages) == 1
    raw = token_from(transport)
    with Session(db_runtime) as db:
        row = db.scalar(select(EmailOutbox))
        assert row.ciphertext is None and row.status == "SENT" and row.sent_at
        assert db.scalar(select(SecurityToken)).token_hash != raw


@pytest.mark.parametrize("invalid", ["expired", "reissued", "tampered"])
def test_invalid_message_not_sent(client, mail, auth_users, db_runtime, clock, invalid):
    enqueue(client)
    if invalid == "expired":
        clock.advance(minutes=31)
    elif invalid == "reissued":
        enqueue(client)
    else:
        with Session(db_runtime) as db, db.begin():
            db.scalar(select(EmailOutbox)).ciphertext = "corrupt"
    transport, worker = mail
    summary = worker.deliver_batch(10)
    assert summary.sent == (1 if invalid == "reissued" else 0)
    assert len(transport.messages) == summary.sent
    with Session(db_runtime) as db:
        assert all(row.ciphertext is None for row in db.scalars(select(EmailOutbox)))


def test_retry_is_bounded_and_sanitized(
    client, mail, auth_users, db_runtime, settings, clock
):
    enqueue(client)
    transport, worker = mail
    transport.fail = True
    settings.email_max_attempts = 2
    assert worker.deliver_batch(10).failed == 1
    assert worker.deliver_batch(10).failed == 0
    clock.advance(seconds=settings.email_retry_seconds)
    assert worker.deliver_batch(10).failed == 1
    clock.advance(hours=1)
    assert worker.deliver_batch(10).failed == 0
    with Session(db_runtime) as db:
        row = db.scalar(select(EmailOutbox))
        assert (row.status, row.attempts, row.failure_code, row.ciphertext) == (
            "FAILED",
            2,
            "DELIVERY_FAILED",
            None,
        )


def test_workers_concurrent_do_not_duplicate(
    client, mail, auth_users, settings, db_runtime, clock
):
    enqueue(client)
    transport, worker = mail
    workers = [worker, DeliveryWorker(db_runtime, settings, transport, clock)]
    barrier = Barrier(2)

    def deliver(worker):
        barrier.wait()
        return worker.deliver_batch(10).sent

    with ThreadPoolExecutor(2) as pool:
        assert sum(pool.map(deliver, workers)) == 1
    assert len(transport.messages) == 1


def test_stale_claim_becomes_unknown_not_resent(
    client, mail, auth_users, db_runtime, clock
):
    enqueue(client)
    with Session(db_runtime) as db, db.begin():
        row = db.scalar(select(EmailOutbox))
        row.status, row.lease_expires_at = "DISPATCHING", clock()
    assert mail[1].deliver_batch(10).sent == 0
    with Session(db_runtime) as db:
        row = db.scalar(select(EmailOutbox))
        assert row.status == "UNKNOWN" and row.ciphertext is None


def test_unknown_transport_failure_is_not_retried(
    client, mail, auth_users, db_runtime, clock
):
    from app.identity.email_transport import DeliveryUncertain

    enqueue(client)

    class UncertainTransport:
        def send(self, message):
            raise DeliveryUncertain("sensitive transport response")

    mail[1].transport = UncertainTransport()
    assert mail[1].deliver_batch(10).failed == 1
    clock.advance(hours=1)
    assert mail[1].deliver_batch(10).failed == 0
    with Session(db_runtime) as db:
        row = db.scalar(select(EmailOutbox))
        assert (row.status, row.failure_code, row.ciphertext) == (
            "UNKNOWN",
            "DELIVERY_UNKNOWN",
            None,
        )


def test_worker_and_reissue_are_serialized(client, mail, auth_users, new_client):
    from threading import Event

    enqueue(client)
    browser = new_client()
    csrf(browser)
    entered, release = Event(), Event()
    transport, worker = mail
    original_send = transport.send

    def blocked_send(message):
        entered.set()
        assert release.wait(5)
        original_send(message)

    transport.send = blocked_send
    with ThreadPoolExecutor(2) as pool:
        delivered = pool.submit(worker.deliver_batch, 1)
        assert entered.wait(5)
        reissued = pool.submit(
            browser.post, "/api/auth/recovery", json={"email": "member@example.test"}
        )
        assert not reissued.done()
        release.set()
        assert delivered.result().sent == 1
        assert reissued.result().status_code == 202
    old = token_from(transport)
    response = browser.post(
        "/api/auth/token/validate", json={"token": old, "purpose": "PASSWORD_RESET"}
    )
    assert response.status_code == 400


def test_smtp_explicit_envelope_and_quit_uncertainty(monkeypatch):
    import smtplib
    from uuid import uuid4

    from app.core.config import Settings
    from app.identity.email_transport import (
        DeliveryFailure,
        DeliveryUncertain,
        EmailMessage,
        SMTPEmailTransport,
    )

    sent = []

    class SMTPDouble:
        def __init__(self, *args, **kwargs):
            pass

        def __enter__(self):
            return self

        def __exit__(self, *args):
            raise smtplib.SMTPServerDisconnected("sensitive SMTP text")

        def starttls(self, **kwargs):
            pass

        def send_message(self, message, **kwargs):
            sent.append(kwargs)

    monkeypatch.setattr("app.identity.email_transport.smtplib.SMTP", SMTPDouble)
    adapter = SMTPEmailTransport(
        Settings(smtp_host="test.invalid", smtp_sender="sender@example.test")
    )
    with pytest.raises(DeliveryUncertain, match="^DELIVERY_UNKNOWN$"):
        adapter.send(
            EmailMessage("one@example.test", "Subject", "controlled test body", uuid4())
        )
    assert sent == [
        {"from_addr": "sender@example.test", "to_addrs": ["one@example.test"]}
    ]
    with pytest.raises(DeliveryFailure, match="^DELIVERY_INVALID$"):
        adapter.send(
            EmailMessage(
                "one@example.test,two@example.test",
                "Subject",
                "controlled test body",
                uuid4(),
            )
        )
    assert len(sent) == 1
