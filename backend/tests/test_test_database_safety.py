import pytest

from tests.database_harness import validate_test_urls


@pytest.mark.parametrize(
    "owner,runtime",
    [
        (
            "postgresql+psycopg://owner@localhost/production",
            "postgresql+psycopg://runtime@localhost/production",
        ),
        (
            "postgresql+psycopg://owner@localhost/a_test",
            "postgresql+psycopg://runtime@localhost/b_test",
        ),
        (
            "postgresql+psycopg://owner@localhost/a_test",
            "postgresql+psycopg://owner@localhost/a_test",
        ),
        ("sqlite:///a_test", "sqlite:///a_test"),
    ],
)
def test_unsafe_test_targets_are_rejected_without_connecting(owner, runtime):
    with pytest.raises(ValueError):
        validate_test_urls(owner, runtime)


def test_invalid_test_url_does_not_leak_input():
    with pytest.raises(ValueError) as failure:
        validate_test_urls("sentinel-secret", "invalid")
    assert "sentinel-secret" not in str(failure.value)


@pytest.mark.parametrize(
    "suffix",
    [
        "?dbname=production",
        "?host=remote",
        "?user=postgres",
        "?service=production",
    ],
)
def test_query_overrides_are_rejected(suffix):
    with pytest.raises(ValueError):
        validate_test_urls(
            "postgresql+psycopg://owner@localhost/a_test" + suffix,
            "postgresql+psycopg://runtime@localhost/a_test" + suffix,
        )


@pytest.mark.parametrize("target", ["localhost/dbname%3Dproduction_test", "/a_test"])
def test_implicit_or_conninfo_targets_are_rejected(target):
    with pytest.raises(ValueError):
        validate_test_urls(
            "postgresql+psycopg://owner@" + target,
            "postgresql+psycopg://runtime@" + target,
        )


@pytest.mark.parametrize(
    "field,value", [("database", "other_test"), ("username", "other_role")]
)
def test_actual_connection_identity_is_verified(db_owner, field, value):
    from tests.database_harness import attest_test_connection

    with db_owner.connect() as conn, pytest.raises(ValueError, match="identity"):
        attest_test_connection(conn, db_owner.url.set(**{field: value}))


def test_disposable_marker_is_verified_on_runtime(db_owner, db_runtime):
    from sqlalchemy import text

    from tests.database_harness import attest_test_connection

    with db_owner.begin() as conn:
        name = conn.dialect.identifier_preparer.quote(db_owner.url.database)
        conn.execute(text(f"COMMENT ON DATABASE {name} IS NULL"))
    try:
        with db_runtime.connect() as conn, pytest.raises(ValueError, match="marker"):
            attest_test_connection(conn, db_runtime.url)
    finally:
        with db_owner.begin() as conn:
            conn.execute(
                text(f"COMMENT ON DATABASE {name} IS 'hiatlas-disposable-test-db'")
            )
