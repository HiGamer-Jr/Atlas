# HiAtlas Customer Scope V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [x]`) syntax for tracking.

**Goal:** Expose the real customer's operational scope without granting authority to browser state.

**Architecture:** A shared server unit resolver supplies self-discovery and existing operation authorization. Atomic membership scope updates preserve version checks and audit; a strict frontend provider consumes complete snapshots solely for UX. Every backend operation revalidates live authorization independently.

**Tech Stack:** Existing FastAPI, SQLAlchemy, Alembic, PostgreSQL 18, Python >=3.13.15, React 19, TypeScript, Vitest and official PowerShell gate; no new dependency required.

**Spec:** ../specs/2026-10-08-hiatlas-customer-scope-v1-design.md (approved written spec; read before execution).

## Global Constraints

- Exclusive worktree D:/Atlas/.worktrees/hiatlas-customer-scope-v1; branch feat/hiatlas-customer-scope-v1; base integration/hiatlas-product-v1 exactly 0538d18b49f7c4d6efdbdec370f363c5061cc29c.
- No main changes, Demo changes, DeploymentBanner, synthetic production data, push, merge, rebase, tag or deploy.
- Preserve opaque session-bound X-HiAtlas-Context, fresh server authorization, financial/fiscal/sensitive classifications and internal operator separation.
- No localStorage authorization cache; no SQLite, harness relaxation or skipped tests.
- RESTRICTED default; explicit exact grants only; ALL is explicit policy, never a persisted node or inferred empty-list state.
- ALL -> RESTRICTED uses newly submitted grants or zero units; never implicitly restores historical grants.
- Mode, grant replacement, membership version, context revocation and audit commit atomically with expected_version.
- MAX_OPERATIONAL_SCOPE_NODES = 1000 current-contract graph rows, including inactive nodes/ancestors; overflow returns HTTP 503 OPERATIONAL_SCOPE_TOO_LARGE, no partial scope.
- Returned capabilities describe UX only; backend operations freshly recalculate context, unit scope, module and capability.
- Product-code execution starts only after plan review. Defer task commits until the complete official gate passes, then make the requested local commit.

## Review Focus

1. Historical grants survive in storage: ALL -> RESTRICTED with omitted/empty nodes must grant zero (Task 1).
2. Competing administrator writes or audit failure: no mixed mode/grants or partially committed context revocation (Task 1).
3. Large graphs or broken ancestry: no truncated success, leakage or permissive missing-parent interpretation (Tasks 2–3).
4. Stale UX capabilities and manipulated module/node choices: operations deny against fresh server state (Task 3).
5. Late requests, tab switching or malformed response: clear old scope and keep controls closed (Task 4).

## File map and execution order

Tasks run sequentially: persistence/command -> resolver -> self API -> frontend -> complete verification. This is one authorization feature with shared invariants; separate independently shipped subsystem plans would duplicate the authority contract.

- Membership schema and migration: backend/app/tenancy/models.py; backend/alembic/versions/0013_customer_unit_scope.py.
- Atomic administrative command and audit: backend/app/organization/{schemas,services}.py; backend/app/audit/schemas.py. Existing routes remain administrator-only.
- Shared exact unit authority: new backend/app/organization/unit_authorization.py; integrations backend/app/platform/policy.py and backend/app/datahub/policy.py.
- Self API: new backend/app/tenancy/operational_scope.py and operational_scope_schemas.py; existing backend/app/tenancy/routes.py. Preserve existing support_control("context") boundary.
- Frontend: new frontend/src/operational/{types,validate,state,OperationalScopeProvider}.tsx/ts as specified below; existing App.tsx, datahub/TenantWorkspace.tsx and platform/organization/types.ts.
- Durable contract documentation: new docs/architecture/customer-operational-scope-v1.md.
- Test files are named in their owning tasks. database_harness and production fixture/catalogue files are not modified.

## Verification command conventions

From the worktree, backend focused commands below run with backend as working directory: `.\.venv\Scripts\python.exe -m pytest <tests> -q`. Provision the existing locked dependencies using the repository's documented official workflow when execution starts; tests require the official PostgreSQL harness/environment. Do not substitute another database or run without harness readiness. Frontend commands run from frontend: `npm test -- <files>`. A red step must fail on the named behavioral assertion or missing new interface, never merely on database/environment setup. A green step means all selected tests PASS with zero skips.

### Task 1: Explicit policy and atomic scope replacement

**Files:** Modify backend/app/tenancy/models.py, backend/app/organization/schemas.py, backend/app/organization/services.py, backend/app/audit/schemas.py and frontend/src/platform/organization/types.ts. Create backend/alembic/versions/0013_customer_unit_scope.py and backend/tests/test_customer_scope_command.py. Extend backend/tests/test_migration_lifecycle.py and test_foundation_schema.py.

**Interfaces:** Membership.unit_scope_mode: Literal["ALL", "RESTRICTED"], constrained non-null default RESTRICTED. Extend UnitScopePatch with mode default RESTRICTED; legacy omitted-mode requests retain required node_ids. Explicit-mode requests may omit node_ids, interpreted as []; ALL rejects nonempty IDs. UnitScopeView and MembershipUnitScopeSnapshot add mode. Preserve `set_unit_scope(db, request, principal, scope, member_id, payload)` and existing route; it returns the extended UnitScopeView-compatible mapping.

- [x] Write migration and command tests; use existing PostgreSQL API fixtures and real transactions. Core assertions:

```python
# test_existing_memberships_migrate_restricted
assert migrated.unit_scope_mode == "RESTRICTED"
# test_all_to_restricted_never_restores_dormant_grants (omitted and [] cases)
assert response.json()["mode"] == "RESTRICTED"
assert response.json()["node_ids"] == []
# test_restricted_replacement_is_exact (one/multiple/zero cases)
assert set(response.json()["node_ids"]) == explicitly_submitted_ids
# test_conflict_and_audit_failure_are_atomic
assert stored_mode_grants_version_contexts == before_state
assert committed_audits == before_audits
# test_concurrent_updates_have_one_winner
assert sorted(statuses) == [200, 409]
assert stored_mode_and_grants == successful_request_policy
```

Also test invalid enum/foreign node, inactive membership, ALL with IDs, explicit historical-node regrant, administrator-only permission and preserved sensitive-role restrictions. Audit success contains before/after mode, IDs and version; upgrade/downgrade lifecycle and schema constraint checks pass.
- [x] Run new tests before implementation; confirm intended red assertions.
- [x] Implement migration after 0012, schemas and atomic existing command. Maintain established lock order, fresh authorization after waits, scoped predicates, version check and single DB transaction. Deactivate old grants for ALL; replace RESTRICTED grants only from submitted IDs. Roll back audit failure together with every mutation. Avoid separate commit in services.
- [x] Run `.\.venv\Scripts\python.exe -m pytest tests/test_customer_scope_command.py tests/test_migration_lifecycle.py tests/test_foundation_schema.py tests/test_organization_api.py -q`; require PASS/zero skips. Keep task diff local pending final gate.

### Task 2: Shared unit authorization without scope broadening

**Files:** Create backend/app/organization/unit_authorization.py and backend/tests/test_customer_unit_authorization.py. Modify backend/app/platform/policy.py and backend/app/datahub/policy.py; extend backend/tests/test_datahub_policy.py.

**Interfaces:** In unit_authorization.py define frozen `ResolvedUnitScope(mode: Literal["ALL", "RESTRICTED"], nodes: tuple[OrganizationNode, ...])`; `resolve_unit_scope(db: Session, scope: AccessContext, membership: Membership) -> ResolvedUnitScope` returns the complete bounded permitted nodes; `require_authorized_node(db: Session, scope: AccessContext, membership: Membership, node_id: UUID) -> OrganizationNode` validates one candidate afresh. MAX_OPERATIONAL_SCOPE_NODES = 1000. These helpers validate unit authority only; caller still revalidates principal/context and capabilities. No circular import from platform policy into the resolver.

- [x] Write parameterized tests for ALL, one/multiple/zero exact grants, no descendant expansion, foreign tenant/contract, inactive node/ancestor/grant, cycles, foreign parent and unknown policy. Assertions:

```python
assert set(n.id for n in resolved.nodes) == expected_authorized_ids
assert foreign_node_id not in {n.id for n in resolved.nodes}
assert inactive_node_id not in {n.id for n in resolved.nodes}
# test_broken_graph_fails_closed
assert error.code == "OPERATIONAL_SCOPE_INVALID"
# test_graph_limit_is_complete_or_error
assert len(at_limit.nodes) == 1000
assert overflow_error.code == "OPERATIONAL_SCOPE_TOO_LARGE"
```

For restricted small scope in a 1001-row graph assert the same explicit overflow. Singular checks never use client snapshots; historical inactive grants deny. Data Hub ALL selection uses real permitted nodes, RESTRICTED uses only exact grants; preserve existing dataset sensitivity filtering and internal/support prohibitions.
- [x] Run new resolver/Data Hub tests; confirm intended red assertions.
- [x] Implement the bounded scoped graph query (limit + 1), active ancestry validation, exact filtering and scoped per-node checks. Translate invalid graph/state to HTTP 409 OPERATIONAL_SCOPE_INVALID; overflow to 503. Replace duplicated grant authority in platform require_capability and Data Hub authorize_selection, retaining module/sensitivity checks, lock-order discipline and post-wait revalidation. Explicit unauthorized Data Hub IDs retain existing not-found semantics.
- [x] Run `.\.venv\Scripts\python.exe -m pytest tests/test_customer_unit_authorization.py tests/test_datahub_policy.py tests/test_organization_api.py -q`; require PASS/zero skips. Keep task diff local.

### Task 3: Versioned self scope and fresh operation checks

**Files:** Create backend/app/tenancy/operational_scope.py, backend/app/tenancy/operational_scope_schemas.py, backend/tests/test_operational_scope_api.py and docs/architecture/customer-operational-scope-v1.md. Modify backend/app/tenancy/routes.py; extend backend/tests/test_context_api.py and test_datahub_policy.py.

**Interfaces:** `OperationalScopeView` uses the exact schema_version=1 discriminator and fields in the approved spec. Define tenant/customer/role/node/module response models there; internal customer_scope is null. `operational_scope_view(db: Session, principal: Principal, scope: AccessContext) -> OperationalScopeView` in operational_scope.py consumes Task 2 resolve_unit_scope and existing revalidate/effective_capabilities/module catalogue. Resolve Principal's existing import/type from identity dependencies; do not introduce a new principal representation. Route GET /api/context/operational-scope has no selector parameters and Cache-Control: no-store.

- [x] Write API tests with ordinary clients lacking organization.manage, roles.manage and modules.read. Assertions:

```python
assert response.status_code == 200
assert body["schema_version"] == 1
assert body["customer_scope"]["role"]["code"] == actual_role.code
assert visible_node_ids == expected_authorized_ids
assert returned_parent_ids <= visible_node_ids
assert all(m["contracted"] for m in modules)
assert inactive_module["operational_available"] is False
assert internal_body["customer_scope"] is None
# test_overflow_has_no_partial_payload
assert response.status_code == 503
assert error_code == "OPERATIONAL_SCOPE_TOO_LARGE"
assert "customer_scope" not in error_body
# test_stale_summary_cannot_authorize_operation
assert formerly_allowed_operation_after_revocation.status_code in (403, 404)
```

Cover revoked/inactive membership, role and contract; node/grant/module state changes on next request; unknown module/state; forged tenant/contract/header binding; foreign metadata absence; independent session/tab contexts; response no-store. Parameterize operation replay over grant revocation, ALL -> RESTRICTED, module deactivation/uncontracting and capability removal. Contracted active modules without an implemented domain remain operationally unavailable. Internal support/admin get no artificial role or new operation rights.
- [x] Run new API tests; confirm intended red assertions.
- [x] Implement schemas, aggregator and route with existing context dependency/support-control classification. Revalidate fresh state before returning, including after locks; do not call administrator-only list endpoints. Build safe parents only within returned authorized IDs. Describe capabilities through existing policy plus applicable module/unit gates; never accept them as operation input. Document wire examples, errors, atomic updates, 1000-row limitation and all five terminology distinctions.
- [x] Run `.\.venv\Scripts\python.exe -m pytest tests/test_operational_scope_api.py tests/test_context_api.py tests/test_datahub_policy.py tests/test_runtime_privileges.py -q`; require PASS/zero skips. Keep task diff local.

### Task 4: Strict reusable frontend operational context

**Files:** Create frontend/src/operational/types.ts, validate.ts, state.ts, OperationalScopeProvider.tsx, validate.test.ts and OperationalScopeProvider.test.tsx. Modify frontend/src/App.tsx and frontend/src/datahub/TenantWorkspace.tsx; extend frontend/src/AuthenticatedApp.test.tsx and frontend/src/datahub/DataHub.test.tsx.

**Interfaces:** Export the schema-version-1 `OperationalScope` discriminated union matching Task 3. `parseOperationalScope(value: unknown, expectedContextId: string): OperationalScope` rejects malformed or contradictory data. Export `OperationalScopeState` as idle/loading/unavailable with scope:null, or ready with validated scope; unavailable includes a safe error code. `OperationalScopeProvider({children}: {children: ReactNode})` consumes existing useAccessContext/useAuth, and `useOperationalScope(): OperationalScopeState` from state.ts exposes the snapshot without changing platform context selection semantics.

- [x] Write strict parser/provider/workspace tests. Assertions:

```typescript
expect(() => parseOperationalScope(invalidResponse, contextId)).toThrow();
expect(state.scope).toBeNull(); // loading, overflow and malformed/error cases
expect(screen.queryByRole('button', {name: /Data Hub/})).not.toBeInTheDocument();
expect(renderedRoleName).toBe(serverCustomRoleName);
expect(afterLateOldResponse.context_id).toBe(newContextId);
expect(providerB.context_id).toBe(contextB); // clearing A leaves B intact
```

Cover every node kind, duplicate/cyclic/dangling returned parents, missing role, unknown version/actor/mode/module, inactive-but-operational module, wrong context ID, schema/header actor mismatch, forged module/capability browser values, overflow, focus revocation and aborted late response. Verify no authorization data writes to localStorage and no synthetic fallback. Actual backend denial remains Task 3's proof; frontend tests only prove UX stays closed.
- [x] Run `npm test -- src/operational/validate.test.ts src/operational/OperationalScopeProvider.test.tsx src/AuthenticatedApp.test.tsx src/datahub/DataHub.test.tsx`; confirm intended red assertions.
- [x] Implement types/parser/state then provider. Clear scope before refresh/context change; use request cancellation and generation guards; restore/focus always fetch fresh server scope. Internal flow stays distinct and does not require customer_scope. Integrate tenant workspace identity/role from validated server snapshot; remove seven-profile whitelist/fallback from real flow. Show Data Hub only when ready, DATAHUB contracted+active+operational_available and descriptive datahub.read present; operations still call existing backend authorization. No new synthetic selectors, dashboards or records.
- [x] Repeat the focused command; run `npm run lint` and `npm run build`; require PASS/zero skips. Keep task diff local.

### Task 5: Whole diff review, official gate and local commit

**Files:** Review all files above and the approved spec; no gate/harness relaxation. Record results in docs/architecture/customer-operational-scope-v1.md only when supported by command output.

**Interfaces:** Consumes Tasks 1–4 and existing scripts/check-local.ps1; produces verified local feature commit and final evidence report, no remote mutation.

- [x] Review complete diff for unauthorized ancestor disclosure, stale capabilities as authority, mode/grant atomicity, scope/header isolation, sensitive-policy changes, synthetic data and Demo/config leakage. Check App real role path and Data Hub selection use the same authority definitions. Resolve findings with focused regression tests before full gate.
- [x] Run from worktree `.\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'`; require backend full PASS, frontend full PASS, scripts PASS, zero skips, lint PASS, build PASS and PostgreSQL cleanup PASS. Capture exact counts/output/exit code. Any failure follows systematic-debugging; rerun affected tests and the full required gate after fixes.
- [x] Run `git diff --check`; stage only intended feature/docs files, then run `git diff --cached --check`; both PASS. Confirm correct branch/base and unchanged main/Demo refs. Do not run push/merge/deploy.
- [x] Make one local commit after all evidence passes: `git commit -m "feat: add real customer operational scope foundation"`. Confirm SHA and `git status --short` empty.
- [x] Report SHA, changed files, API contract, architectural choices, exact gate results, risks and deferred work. Explicitly retain deferrals: complete domain UI/datasets, synthetic Workspace replacement, descendant grant expansion, per-unit capabilities, redesigned admin editor, provisioning/billing and pagination.

## Plan self-review

Spec coverage: persistence/atomic transitions (Task 1), unit isolation/ancestry/ALL (Task 2), self endpoint/modules/capabilities/internal roles/revalidation (Task 3), strict real frontend and independent contexts (Task 4), security review/official gate/local commit (Task 5). The five Review Focus cases each have named assertions in their owning tasks. Interface names, mode values, response discriminator and limit/error codes are consistent across tasks. Runtime snapshot version remains schema_version=1; membership concurrency uses expected_version and is not conflated with it. Commands use the official PostgreSQL harness and existing toolchain. No product implementation is included in this plan; execution was authorized and completed using Native; all official gate checks passed.

## Execution notes

Native execution authorized by the user. Existing AccessScope (the context dependency's reference type) is used rather than ORM AccessContext. Resolver/self-API behavior is tested together in test_operational_scope_api.py and existing Data Hub tests; a duplicate resolver-only test file was unnecessary. PowerShell runners and an ignored plan-specific ledger replace Unix skill helpers. One local commit is deferred until the official full gate passes.

Independent review identified three Important findings, all reproduced in failing tests and corrected: strict malformed policy/containment validation; explicit-node operation independence from bounded discovery; same-context spreadsheet draft preservation behind a closed refresh gate. There were no Critical or Minor findings and no declined-to-judge items. Supplemental coherence checks include inactive-module capability contradictions and the existing backend feature gate.

Final gate: backend1010 / frontend335 / scripts37 PASS, zero skips; lint/build/diff/cleanup PASS. Task 5 concludes with the single local feature commit containing this plan and validation report.
