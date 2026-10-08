# HiAtlas product v1 integration audit

Official repository: HiGamer-Jr/Atlas. Branch: integration/hiatlas-product-v1.
Base: 02ae9b3a3766aa89253d37944c0b4eadd00a95a0 (validated Foundation/Data Hub).
Gate source: 97f527bc14c00d2b1c727c362cdf9704fd61d5d4.
Audited Demo HEAD: 00e585edadc3d8cabd841ac7c2b92a36368892c4, including ad59355 and 1277afa.

## Decisions

The Demo and Data Hub diverge after Foundation 641e575. A full restore or merge from the Demo would discard validated Data Hub code. Integration therefore selects changes relative to Foundation, keeping the complete Data Hub implementation and its validation artifacts.

The ten files changed by gate commit 97f527b are integrated. Eight remain byte-equivalent in Git; testdb.psm1 and its safety test file receive the reviewed cleanup amendments below. Existing Data Hub PostgreSQL fixtures, migration revisions 0011/0012, routes, dependencies, policies and browser checks remain intact.

Context role metadata (tenant_role_code/name) is returned from the backend revalidated membership role. Internal operators receive null role metadata. Customer identity uses real auth/me and contract selection through ContextProvider. Session storage retains only the opaque context identifier; role/profile is read from backend context.

The customer bridge in App.tsx is adapted to TenantWorkspace, the real Data Hub workspace already present in the base. Seven recognized customer roles retain presentation names, isolated from the fictional workspace/catalog. A missing/unknown role fails closed. The backend tenant-role name takes precedence for display. Backend capabilities exclusively govern available tools; this mapping grants no permissions or demo modules. Role metadata does not imply business features are implemented.

## Deliberately excluded

- DeploymentBanner and its tests; VITE_DEPLOYMENT_VARIANT and Demo-only env configuration.
- Demo Workspace changes, fictional catalog imports, synthetic records, dashboards, indicators, exchange rates, fake companies and units.
- Demo domain, deployment configuration, release changes and any removal of Data Hub functionality.
- Demo-only CSS presentation changes unnecessary for the product flow.

Prototype source files inherited from 02ae9b3 remain unchanged; the authenticated product entry imports no fictional Workspace or catalog. Synthetic test fixtures remain test-only.

## Deferred

BUG-03B (real organization unit scope) is not implemented. No fake-unit selector or unit restriction is inferred from the profile mapping. Real unit authorization requires a separate backend/frontend scope design and validation.

## Validation

Command: .\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'
Final full run on 2026-10-08 returned exit code 0. Backend: 975 passed (1076.22s); scripts: 37 passed (109.11s); frontend: 309 passed across 18 files. Zero skips. Backend/script/frontend lint, TypeScript/Vite build, working/staged diff checks and disposable PostgreSQL cleanup all passed. One dependency TestClient deprecation warning remains. No deployment or remote push is part of this integration.

## Reviewed amendments discovered by full validation

Repeated full runs exposed an intermittent native PostgreSQL stop failure although the exact owned cluster eventually reached shut down. The original exception hid timeout/nonzero-exit details. Start remains unchanged. Stop launches no daemon, so it now captures/drains native output, allows pg_ctl 120 seconds and an outer 150-second timeout, and emits only a sanitized failure category. Ownership, SQL marker, role/PID/path/reparse attestation and fail-closed removal remain unchanged. Regression coverage includes noisy native output, bounded stop arguments and sanitized timeout/nonzero-exit categories. Two stopped residuals were removed only after exact logged path/ID/seal checks, no reparse points, no PID/process and positive pg_controldata shut-down proof; no other database was touched. Real lifecycle passed with the amended helper.

Full frontend validation exposed a reusable race in ModuleEditor: controls became enabled before initial fresh fields were applied, allowing initialization to overwrite an edit. Initialized state is now committed with fresh fields before editing/review is allowed. The scoped refresh regression covers updated values/version. The conflict test now awaits completed refreshes before clicking retry; a support focus assertion now waits for the existing focus effect. These are product architecture/test fixes and implement no Demo behavior or unit scope.

The original gate validation document is retained as historical evidence for 97f527b. This product report describes the amendments and final validation of this integration.

## Integrated file inventory

- backend/app/tenancy/schemas.py
- backend/app/tenancy/services.py
- backend/tests/test_context_api.py
- backend/tests/test_local_gate_collection.py
- database/README.md
- docs/operations/hiatlas-product-v1-integration.md
- docs/superpowers/plans/2026-10-08-hiatlas-product-v1.md
- docs/superpowers/validation/hiatlas-local-test-gate.md
- frontend/src/App.tsx
- frontend/src/AuthenticatedApp.test.tsx
- frontend/src/datahub/DataHub.test.tsx
- frontend/src/datahub/TenantWorkspace.tsx
- frontend/src/platform/organization/ModulesPage.test.tsx
- frontend/src/platform/organization/ModulesPage.tsx
- frontend/src/platform/state.ts
- frontend/src/support/SupportSession.test.tsx
- frontend/src/workspace/customerProfile.ts
- scripts/check-local.ps1
- scripts/check-platform-foundation.ps1
- scripts/testdb-start.ps1
- scripts/testdb-stop.ps1
- scripts/testdb.psm1
- scripts/tests/test_local_testdb_scripts.py
- scripts/tests/testdb-lifecycle.ps1
- docs/superpowers/validation/hiatlas-product-v1.md
