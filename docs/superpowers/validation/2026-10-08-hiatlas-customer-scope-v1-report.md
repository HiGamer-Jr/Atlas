# HiAtlas customer scope V1 — completed local validation

Date: 2026-10-08. Repository: HiGamer-Jr/Atlas. Branch: feat/hiatlas-customer-scope-v1.
Base exclusively integration/hiatlas-product-v1, 0538d18b49f7c4d6efdbdec370f363c5061cc29c.
Worktree: D:/Atlas/.worktrees/hiatlas-customer-scope-v1.
No push, merge, rebase, tag, deploy, public Demo modification or existing branch deletion.

## Official quality gate

Command: `.\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'`.
Exit code: 0. Complete transcript: 2026-10-08-hiatlas-customer-scope-v1-quality-gate.txt.

| Check | Result |
|---|---|
| Backend full PostgreSQL suite | 1010 PASS; zero skips |
| Backend lint | PASS |
| Official Windows scripts safety tests | 37 PASS; zero skips |
| Scripts test lint | PASS |
| Frontend full suite | 335 PASS across 21 files; zero skips |
| Frontend lint | PASS; no lint warnings |
| TypeScript + Vite build | PASS |
| Working and staged git diff --check | PASS |
| Owned PostgreSQL cluster stop/removal | PASS |
| Official phase and local gate | PASS |

Only documentation completion/evidence was added after the full gate; final working/staged diff checks were repeated before the local commit. Product code was unchanged after the green gate. Existing Starlette test-client deprecation warning remains non-failing.

## API and architecture

GET /api/context/operational-scope is an authenticated self endpoint without administrative read permissions. Existing opaque X-HiAtlas-Context is session/actor bound and freshly revalidated. It returns schema_version=1, actor_kind, context_id, own tenant/contract metadata, and either a real tenant customer_scope or null for internal operators. The customer payload has actual role, explicit ALL/RESTRICTED policy, exact authorized organization nodes with safe hierarchy, contracted modules with active/operational availability, and descriptive server-calculated capabilities.

Existing administrative unit-scope PUT gains explicit mode and atomic replacement semantics with expected_version, version increment, context revocation and typed audit in one transaction. ALL -> RESTRICTED never implicitly revives historical grants. Browser IDs are candidates, never authority. Individual explicit-node operations revalidate independently of bounded full-tree discovery. Every backend operation retains live module/capability/sensitivity checks.

A complete current-contract graph over 1000 rows fails with 503 OPERATIONAL_SCOPE_TOO_LARGE and no partial payload. Frontend strict validation, lifecycle binding, and in-memory scope state fail closed; no authorization localStorage or synthetic fallback exists. React Activity preserves a draft only during successful refresh of the same scope with controls hidden; failure/change clears the workflow. See docs/architecture/customer-operational-scope-v1.md for the five distinct scope/module/capability definitions.

# Execution decisions and risks

- PowerShell runners and an ignored plan-specific ledger replace Unix skill scripts: Windows compatibility; portability of bookkeeping is the only cost.
- Existing AccessScope is the context reference type instead of ORM AccessContext: preserves the established dependency contract; no additional browser authority.
- Shared resolver/API tests cover externally observable authorization in one PostgreSQL test suite instead of a redundant resolver-only file: avoids duplicate fixtures; failures are localized through API/policy tests.
- One local commit after complete gate, as the user requested: intermediate tasks remain reviewable in the staged diff.
- Existing backend datahub_enabled also gates UX operational availability and capabilities: intentionally disabled domains remain closed; commercial active state remains unchanged.

Independent review completed after a temporary usage interruption. Three Important findings were reproduced RED and fixed: malformed mode/containment, full discovery blocking explicit-node operations, and lost spreadsheet state during successful same-context refresh. No Critical/Minor findings; no declined-to-judge items.

Risks/deferred: complete graph over 1000 nodes fails closed even for small restricted scope; pagination and redesigned administrative ALL editor remain deferred. Full operational domains/datasets/UI, descendant grants and per-unit capabilities remain future work. No persistent synthetic records or Demo behavior was introduced.

npm audit on unchanged dependencies reports source-map-js1.2.1 (dev=true) high severity GHSA-68fv-2mgg-jv7q. Dependency upgrade is outside this authorization feature; original lockfiles are unchanged. Existing Starlette test-client deprecation warning is non-failing.

## Protected references verified unchanged

- `main`: `49a1437252f15300a04c027126940b9f7b56c4a0`
- `origin/main`: `c28d8ca2f01ef13df9f7830d6769343642733e7d`
- `fix/demo-customer-workspace`: `00e585edadc3d8cabd841ac7c2b92a36368892c4`
- `integration/hiatlas-product-v1`: `0538d18b49f7c4d6efdbdec370f363c5061cc29c`

## Changed files

31 files, including contract/design/plan and gate evidence.

- `backend/alembic/versions/0013_customer_unit_scope.py`
- `backend/app/audit/schemas.py`
- `backend/app/datahub/policy.py`
- `backend/app/organization/schemas.py`
- `backend/app/organization/services.py`
- `backend/app/organization/unit_authorization.py`
- `backend/app/platform/policy.py`
- `backend/app/tenancy/models.py`
- `backend/app/tenancy/operational_scope.py`
- `backend/app/tenancy/operational_scope_schemas.py`
- `backend/app/tenancy/routes.py`
- `backend/tests/test_customer_scope_command.py`
- `backend/tests/test_datahub_policy.py`
- `backend/tests/test_migration_lifecycle.py`
- `backend/tests/test_operational_scope_api.py`
- `docs/architecture/customer-operational-scope-v1.md`
- `docs/superpowers/plans/2026-10-08-hiatlas-customer-scope-v1.md`
- `docs/superpowers/specs/2026-10-08-hiatlas-customer-scope-v1-design.md`
- `docs/superpowers/validation/2026-10-08-hiatlas-customer-scope-v1-quality-gate.txt`
- `docs/superpowers/validation/2026-10-08-hiatlas-customer-scope-v1-report.md`
- `frontend/src/App.tsx`
- `frontend/src/AuthenticatedApp.test.tsx`
- `frontend/src/datahub/DataHub.test.tsx`
- `frontend/src/datahub/TenantWorkspace.test.tsx`
- `frontend/src/datahub/TenantWorkspace.tsx`
- `frontend/src/operational/OperationalScopeProvider.test.tsx`
- `frontend/src/operational/OperationalScopeProvider.tsx`
- `frontend/src/operational/state.ts`
- `frontend/src/operational/types.ts`
- `frontend/src/operational/validate.test.ts`
- `frontend/src/operational/validate.ts`
