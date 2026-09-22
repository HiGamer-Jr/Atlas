-- Run with psql as the administrator of a dedicated TEST PostgreSQL cluster.
-- Creates new roles/database only; refuses collisions; never resets existing data.
-- Passwords are prompted securely by psql, never passed as SQL/CLI literals.
\set ON_ERROR_STOP on
CREATE ROLE hiatlas_test_owner LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
\password hiatlas_test_owner
CREATE ROLE hiatlas_test_runtime LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT NOBYPASSRLS;
\password hiatlas_test_runtime
CREATE DATABASE hiatlas_foundation_test OWNER hiatlas_test_owner;
COMMENT ON DATABASE hiatlas_foundation_test IS 'hiatlas-disposable-test-db';
-- Exports for the test runner are described in database/README.md.
