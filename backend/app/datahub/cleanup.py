"""Local runtime-only cleanup entry point; no HTTP or owner credentials."""

import argparse
import json

from sqlalchemy.orm import Session

from app.core.config import Settings
from app.datahub.raw_store import RawStore
from app.datahub.retention import cleanup_raw
from app.db.session import create_database_engine, validate_runtime_connection


def main():
    parser = argparse.ArgumentParser(
        description="Remove expired encrypted Data Hub files"
    )
    parser.add_argument("--limit", type=int, default=100)
    args = parser.parse_args()
    settings = Settings()
    store = RawStore(settings)
    engine = create_database_engine(settings.database_url)
    try:
        with Session(engine) as db, db.begin():
            validate_runtime_connection(db.connection())
            db.info["settings"] = settings
            result = cleanup_raw(db, store, args.limit)
        print(json.dumps(result.model_dump()))
    finally:
        engine.dispose()


if __name__ == "__main__":
    main()
