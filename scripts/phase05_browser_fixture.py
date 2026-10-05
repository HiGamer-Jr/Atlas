"""Controlled browser harness; refuses any database without disposable attestation.

Email secrets travel only through the subprocess pipe to browser-test memory.
Never run this module against an application database or with real SMTP.
"""

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "backend"))

from sqlalchemy import text

from app.core.config import Settings
from app.identity.email_transport import FakeEmailTransport
from tests.database_harness import open_test_engines
from tests.helpers import seed_scope
from tests.identity_helpers import seed_user


def settings():
    return Settings(
        environment="test",
        database_url=os.environ["TEST_DATABASE_RUNTIME_URL"],
        public_origin=os.environ["HIATLAS_E2E_ORIGIN"],
        outbox_key=os.environ["OUTBOX_KEY"],
    )


def unavailable_marker():
    return Path(os.environ["HIATLAS_E2E_STATE"]) / "email-unavailable"


class ControlledEmailTransport(FakeEmailTransport):
    @property
    def available(self):
        return not unavailable_marker().exists()

    @available.setter
    def available(self, value):
        pass


def create_browser_app():
    from app.main import create_app

    owner, runtime = open_test_engines()
    owner.dispose()
    runtime.dispose()
    application = create_app(settings())
    application.state.email_transport = ControlledEmailTransport()
    return application


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "action", choices=["seed", "deliver", "expire", "email-off", "email-on"]
    )
    parser.add_argument("--recipient")
    args = parser.parse_args()
    owner, runtime = open_test_engines()
    try:
        if args.action == "seed":
            with runtime.connect() as connection:
                if connection.scalar(text("SELECT count(*) FROM users")):
                    raise ValueError("Seed requires an empty disposable database")
            users = {
                "admin_user": seed_user(
                    runtime, "admin@example.test", "PLATFORM_ADMIN"
                ),
                "support_user": seed_user(
                    runtime, "support@example.test", "PLATFORM_SUPPORT"
                ),
                "member_user": seed_user(runtime, "member@example.test"),
            }
            identifiers = seed_scope(runtime, users)
            from phase11_browser_fixture import set_fixture_password

            set_fixture_password(runtime)
            print(json.dumps({key: str(value) for key, value in identifiers.items()}))
        elif args.action == "deliver":
            from app.identity.delivery import DeliveryWorker

            transport = FakeEmailTransport()
            result = DeliveryWorker(runtime, settings(), transport).deliver_batch(20)
            messages = [
                message
                for message in transport.messages
                if message.to == args.recipient
            ]
            if not messages or result.sent < 1:
                raise ValueError("Expected controlled email delivery")
            # This output is consumed through execFileSync stdio=pipe, never a log.
            print(json.dumps({"text": messages[-1].text}))
        elif args.action == "expire":
            with owner.begin() as connection:
                connection.execute(
                    text(
                        "UPDATE security_tokens SET created_at=now()-interval '2 days', "
                        "expires_at=now()-interval '1 second' WHERE consumed_at IS NULL"
                    )
                )
            print("Expired disposable test tokens")
        elif args.action == "email-off":
            unavailable_marker().touch()
            print("Controlled transport unavailable")
        else:
            unavailable_marker().unlink(missing_ok=True)
            print("Controlled transport available")
    finally:
        owner.dispose()
        runtime.dispose()


if __name__ == "__main__":
    try:
        main()
    except Exception:  # noqa: BLE001 -- never expose delivery secrets in a CLI traceback
        # No tracebacks/SQL parameters/mail content/links in browser reports.
        print(
            "Controlled browser fixture failed; inspect configuration without secrets",
            file=sys.stderr,
        )
        raise SystemExit(1) from None
