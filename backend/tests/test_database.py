from app.db.session import create_database_engine


def test_create_database_engine_uses_postgresql_psycopg():
    database_url = "postgresql+psycopg://atlas:test@localhost:5433/atlas"

    engine = create_database_engine(database_url)

    assert engine.url.drivername == "postgresql+psycopg"
    assert engine.url.host == "localhost"
    assert engine.url.port == 5433
    assert engine.url.database == "atlas"
