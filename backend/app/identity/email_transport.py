import smtplib
import ssl
from dataclasses import dataclass, field
from email.message import EmailMessage as SMTPMessage
from typing import Protocol
from uuid import UUID

from app.identity.mailboxes import single_mailbox


@dataclass(frozen=True, repr=False)
class EmailMessage:
    to: str
    subject: str
    text: str
    id: UUID


class DeliveryFailure(Exception):
    """Definite failure before SMTP accepted the message; safe to retry."""


class DeliveryUncertain(Exception):
    """Acceptance is unknown; do not automatically send a duplicate."""


class EmailTransport(Protocol):
    @property
    def available(self) -> bool: ...

    def send(self, message: EmailMessage) -> None: ...


@dataclass
class FakeEmailTransport:
    available: bool = True
    fail: bool = False
    messages: list[EmailMessage] = field(default_factory=list, repr=False)

    def send(self, message: EmailMessage) -> None:
        if not self.available or self.fail:
            raise DeliveryFailure("DELIVERY_FAILED")
        self.messages.append(message)


class SMTPEmailTransport:
    def __init__(self, settings):
        self.settings = settings

    @property
    def available(self):
        return bool(self.settings.smtp_host and self.settings.smtp_sender)

    def send(self, message):
        if not self.available:
            raise DeliveryFailure("EMAIL_UNAVAILABLE")
        settings = self.settings
        try:
            recipient = single_mailbox(message.to)
            sender = single_mailbox(settings.smtp_sender)
        except ValueError:
            raise DeliveryFailure("DELIVERY_INVALID") from None
        mail = SMTPMessage()
        mail["From"] = settings.smtp_sender
        mail["To"] = message.to
        mail["Subject"] = message.subject
        mail["Message-ID"] = f"<{message.id}@hiatlas.outbox>"
        mail.set_content(message.text)
        sending = False
        try:
            with smtplib.SMTP(
                settings.smtp_host,
                settings.smtp_port,
                timeout=settings.smtp_timeout_seconds,
            ) as smtp:
                smtp.starttls(context=ssl.create_default_context())
                if settings.smtp_username:
                    smtp.login(
                        settings.smtp_username,
                        settings.smtp_password.get_secret_value()
                        if settings.smtp_password
                        else "",
                    )
                sending = True
                smtp.send_message(mail, from_addr=sender, to_addrs=[recipient])
        except (
            smtplib.SMTPRecipientsRefused,
            smtplib.SMTPSenderRefused,
            smtplib.SMTPDataError,
        ):
            raise DeliveryFailure("DELIVERY_FAILED") from None
        except (smtplib.SMTPException, OSError):
            if sending:
                raise DeliveryUncertain("DELIVERY_UNKNOWN") from None
            raise DeliveryFailure("DELIVERY_FAILED") from None
