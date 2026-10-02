> Registro de revisão independente estática da Fase 7 em 2026-10-02. As seções iniciais preservam o histórico; os addendums finais fecham os achados. Referências a .phase07/logs apontam arquivos transitórios removidos após consolidação. Execuções finais e encerramento estão em phase-07.md.
# Phase 7 independent backend review

Review date: 2026-10-02. Workspace: D:\Atlas\.worktrees\hiatlas-platform-phase-1. Baseline supplied by controller: ef9d080; branch feat/hiatlas-platform-phase-7. Review of the current working tree, including untracked Phase 7 source/tests.

## Result

No actionable remaining backend defect identified in the inspected source. This is a static-review result, not a passing quality gate or independent confirmation of the implementer's test results.

The previously reported audit action/snapshot pairing issue is addressed in the inspected AuditInput.validate_scope: the four new actions require their matching entity type, scoped tenant/contract and matching after snapshot; updates require a matching before snapshot. The added parameterized test covers rejecting IdentitySnapshot for each new action. No new RED reproduction is proposed because this review identified no additional defect.

## Inspected requirements and evidence

- Read .phase07/contracts.md, .phase07/progress.md, approved Phase 7 original plan and execution addendum, and relevant approved specification sections on organization, context/policy, roles, audit and deferred extensions.
- Inspected organization models, catalogue, schemas, services, modules and routes, plus router/model registration. Eight physical kinds include UNIT and WORKSITE and exclude PROJECT. Parent and membership-unit FKs include tenant/contract; code is normalized on create, unique per contract and immutable through PATCH. Soft lifecycle and stable versions are used without DELETE routes.
- Inspected the central containment matrix, ancestor/cycle validation, active-child/scope dependency checks and parent options. Scoped recursive paths order the tree before bounded pagination; the inspected recursive expression explicitly casts codes to Text on both sides.
- Traced contract serialization through require_capability -> effective_capabilities -> revalidate -> contract_rows and the existing Context dependency. Commands revalidate after dependent locks and use refreshed locked target rows before version checks. Session/CSRF/origin and current context authority remain the existing shared flow.
- Inspected minimal administrative membership unit-scope GET/PUT, composite relationships, active node/ancestor checks, version increment, context revocation and reversible active rows. Explicit unit policy fails closed without the exact active membership scope and validates current node/ancestor availability.
- Inspected closed module catalogue, missing-row read projection, contracted/active invariant, first-write and update version handling, foreign module identifiers, admin management/support metadata read, and the central optional module policy. Operational availability remains false for undelivered domains. FINANCE configuration does not grant finance/fiscal capability.
- Inspected typed server-owned snapshots, audit append path/transaction dependency and closed projections. Admin can read scoped new metadata; existing support audit predicates exclude structure and unit-scope events. No audit privilege weakening was introduced.
- Inspected migration 0006 guard before DDL, matching model constraints, membership unique key, runtime SELECT/INSERT/UPDATE grants without DELETE/TRUNCATE and dependency-safe downgrade order. Cleanup table registration includes the three new tables first.
- Inspected test_organization_api.py, test_contract_modules.py, test_phase7_policy.py, test_phase7_schema.py, test_phase7_audit.py and test_phase7_races.py. They include physical/tenant constraints, A/A2/B isolation, soft lifecycle, audit rollback/projection, unavailable modules, explicit scope, four concurrent update scenarios, four context-expiry lock scenarios and three contract-inactivation scenarios.
- Inspected operations documentation and source diff boundaries. No Phase 8, support impersonation, MFA, client administrator, business Project, financial grants, generic flags/parameters/integration CRUD or operational placeholder endpoints were introduced in the reviewed backend.

## Verification limits

Only read-only filesystem/source inspection and git diff/status were performed. No DB connection, DB query, migration execution, pytest, Ruff, implementation test, browser/E2E, application startup or product edit was performed by this reviewer. Environment/secret files and database URLs were not read. The implementer's RED/GREEN totals are controller-provided context and were not independently reproduced here. Full backend gate, actual migrations/grant checks and real E2E remain the responsible implementer/controller's checks. The report is the only reviewer-authored file.

## Narrow follow-up review: explicit empty module code

The controller identified a defect missed by the initial static pass: using `module_code or default` discarded an explicitly supplied empty string and could skip module gating for a capability without an implicit module. The controller reports an actual RED failure (DID NOT RAISE). That failure was not reproduced by this reviewer.

The current policy uses `if module_code is None` for defaults. Therefore an explicit empty string reaches the catalogue membership check and receives MODULE_UNAVAILABLE/403, as do unknown strings; capability validation still occurs first. Omitted/None module values retain the implicit finance.read and fiscal.read -> FINANCE mapping. Recognized modules retain scoped tenant/contract SQL predicates, row locking, current capability revalidation and contracted/active/operational checks. No remaining defect found in this correction.

Inspected the new test_explicit_empty_module_code_is_denied regression, which exercises the central policy with a valid modules.read capability and explicitly asserts MODULE_UNAVAILABLE. Also inspected the new 64 parent/child creation combinations against the approved physical matrix and unit-scope cases for inactive nodes (409), duplicate/101-entry inputs (422), foreign A2/B nodes (404) and unchanged membership version after denied requests. Existing unknown-module/capability-first tests remain present.

Rechecked relevant catalogue/grant/migration source: OPERATIONAL_MODULES remains empty, finance/fiscal remain tenant-disabled and absent from internal grants, and migration 0006 still grants only SELECT/INSERT/UPDATE to runtime. No SQL scoping or privilege weakening identified in this follow-up.

Read the current backend-report.md; at review time it still lists full pytest/Ruff as in progress. The controller separately reports the initial full suite at 394 passed, zero skips, 255.59 seconds with Ruff clean, and a final full run including the three additional tests in progress. These are attributed execution reports, not this reviewer's verification. No DB, tests, migrations, Ruff or E2E were executed here; no product files edited. Final fresh gate/E2E remain pending controller verification. This addendum supersedes the initial result for the corrected empty-module defect and retains the original static-only limits.

## Narrow follow-up review: search accepts the full valid node name

Inspected the final search-bound correction in organization/routes.py and test_full_accepted_node_name_can_be_searched. The search query now permits 200 characters, matching NodeCreate/NodePatch name max_length=200. The regression constructs an exact 200-character accepted name (8-character prefix plus 192 characters), creates the node and searches the full name through the real API; it asserts HTTP 200, total=1 and the matching node ID. The prior max_length=128 would reject this valid full-name search before reaching the service.

The service still scopes the query to tenant/contract before applying its escaped name/code icontains filter. Pagination bounds, capability/context authorization and SQL/grants are not changed by this query-validation correction. No actionable remaining defect identified in this narrow delta.

The controller reports an actual RED and implementer GREEN in progress. This reviewer inspected source only and did not independently execute the regression, DB, tests or migrations. No product edits were made; only this review addendum was appended. Final execution/gate/E2E evidence remains the controller's responsibility.
