# Purchase requests V1 — durable validation report

Date: 2026-10-10. Branch: `feat/hiatlas-purchase-request-v1`. Worktree: `D:/Atlas/.worktrees/hiatlas-purchase-request-v1`.
Approved spec: [design](../specs/2026-10-08-hiatlas-purchase-request-v1-design.md); approved execution: [plan](../plans/2026-10-08-hiatlas-purchase-request-v1.md); implemented contract: [architecture](../../architecture/purchase-requests-v1.md).

**Status: Task 8 Phase A documentation complete; independent whole-branch review and Phase B official full quality gate PENDING. No full-gate PASS or publication is claimed.** Tasks 1–7 and their fix reviews are complete per the authoritative controller ledger. This is a pre-gate evidence checkpoint; the controller must review the entire branch before resuming the implementer for Phase B.

Product-exclusive base: `fa354b73cdb43d600949e54b81595f416ef5cd65` (customer-scope). Task 8 input HEAD: `858d7d139e359a319cde25188deb55b695c31720`. The Phase A docs-only commit SHA is recorded in the execution report `.superpowers/sdd/2026-10-08-hiatlas-purchase-request-v1/task-8-report.md`; a commit cannot contain its own SHA.

## Evidence provenance and documentation RED → GREEN

Authoritative execution ledger and detailed reports are local ignored SDD artifacts under `.superpowers/sdd/2026-10-08-hiatlas-purchase-request-v1/`: `progress.md`, `task-1-report.md` … `task-7-report.md`, their RED/GREEN transcripts, review packages and fixes. This durable report carries their task outcomes and controller dispositions into versioned documentation; prior counts are scoped historical evidence, never the final gate's totals.

Task 8 is documentation work. Its RED was actual completeness inspection before edits at input HEAD, not a fabricated failing software test:

- Existing plural architecture file was 40 lines, covering policy/locks/workflow/manual fulfillment but omitting the full five-concept authorization explanation, API/error/state/quantity tables, private-file and UI contract, PDF compatibility limits, no-TTL growth and future PARTNER boundary.
- Durable report did not exist. `Test-Path` returned False.
- Initial inspection reported False for all 11 section/contract markers, including "Five authorization concepts", "State and quantity contract", "Implemented API", "Private file contract", "PARTNER", "4096", "8 KiB", "256 tokens", "without TTL" and "Organization available". Raw measured output: `task-8-doc-red.txt`.
- Singular architecture path did not exist; the existing plural file was extended, avoiding a duplicate document.
- Original doc still described attachments as a later task. That stale handoff is removed from the implemented contract.

GREEN is a fresh section-by-section contract audit against spec sections 1–13, actual route decorators/command schemas/errors, test names and final task reports. Architecture now documents all identified gaps; this report supplies coverage, all eight task outcomes, decisions and honest pending gate status. Local `task-8-doc-green.txt` records the fresh completeness/route/test/ruling/ref/diff checks. These documentation checks do not claim software execution or replace the official full gate.

## Spec → implementation → test evidence matrix

Tests referenced below are real files/cases inspected at input HEAD. Parameterized cases explain why function counts differ from executed case counts. The matrix maps behavior; final project totals are intentionally pending.

| Spec section | Implemented evidence / acceptance boundary | Test evidence |
|---|---|---|
| 1 Purpose, base, exclusions | Separate need aggregate; no order/stock/payment writes, real manual attestations; exclusive branch/base | fulfillment `test_multi_item_partial_complete_close`, `test_partial_cancel_keeps_quantities`; whole-diff boundary inspection below |
| 2 Existing infrastructure | app/db/models.py registry, tenancy/context/current roles/units, official PostgreSQL minimum privileges; no Demo project reuse | schema `test_registered_purchase_models_match_migration`, `test_runtime_grants_and_migration_lifecycle`; migration lifecycle tests |
| 3 Chosen architecture | Domain in backend/app/procurement/requests and frontend/src/procurement/requests; caller transaction with immutable evidence rather than generic workflow/replay authority | commands `test_audit_failure_rolls_back_commands`; fulfillment `test_complementary_audit_failure_rolls_back_completed_delivery` |
| 4 Components / flow | Fresh policy; scope predicates before counts/pages; commands/locks/events; private bytes; validated tenant UI | queries `test_count_cursor_filters_never_leak`, `test_routes_are_private_and_revalidate`; state/workspace tests |
| 5 Models / invariants | Scoped FKs, server authorship/IDs, frozen submitted content; exact decimal/UOM/items; policy/receipt/attachments/entries | schema `test_payload_limits_and_exact_decimals`, `test_scoped_references_reject_cross_contract_and_cross_request`, `test_submitted_items_cannot_accept_new_insert`, `test_receipt_null_target_is_unique_and_context_scoped`; commands retained-item/reorder cases |
| 5 Approval policy | Default absent REQUIRED/version0; explicit NOT_REQUIRED; server decision/HUMAN vs POLICY_WAIVER; prospective config | commands `test_required_default_not_required_and_invalid_policy`, `test_policy_admin_patch_prospective`, `test_policy_change_preserves_pending_human_decision`, `test_both_policy_flows_retries_versions_revalidation`; concurrency `test_policy_change_and_concurrent_decision` |
| 6 State machine | Closed transitions, independent urgent reason, no reopen, partial cancellation and explicit close; assigned attribute | commands `test_workflow_and_every_invalid_state_pair`, `test_self_approval_denied_and_content_frozen`, `test_urgent_submit_requires_distinct_reason`, `test_http_submit_reason_contract_and_exact_replay`; fulfillment compensation/partial/close cases |
| 7 Authorization | Ten permissions, action never implies read, exact current units, private draft, real candidate/assigned buyer, no internal/support authority | policy custom-role/ALL-restricted/zero-grants/own-read/private-draft/every-gate/internal/derived-context cases; queries eligibility/count/private-history; commands `test_buyer_read_unit_revocation_blocks_execution`; schema `test_purchase_request_capability_catalog_has_no_automatic_grants` |
| 8 Read API | Scoped own/unit list, bounded cursor/detail/history/minimal buyers and metadata without bytes/email; no-store | queries cursor/scope/kind/filter/count/foreign404/history-revocation/balance-projection cases; api.test.ts |
| 8 Command API / reference errors | Actual approved /{id}/draft and /{id}/assignment, CSRF/UUID key/version/closed bodies, no client waiver or fake reference | commands `test_http_approved_draft_route_contract`, `test_assignment_http_opaque_context_and_invalid_candidate`, `test_http_command_csrf_version_key_and_content_freeze`, `test_http_create_and_reference_domain_error`; frontend approved-path/retry tests |
| 8 Private files | Bounded streaming/type/filename/scoped item/state auth before bytes/no-store download/current revocation; conservative bounded PDF parser | attachments real-image/PDF, type-size-encryption, cross-item, private download, multipart limits, auth-before-body, final-IEND, terminal/delete/replay, work-bound/flat-trailer/lexical-token cases |
| 9 Evidence / audit | Event/audit/mutation/receipt atomic; tenant actor_role null, membership/role typed provenance; immutable runtime evidence | schema `test_runtime_cannot_rewrite_evidence`, `test_approver_requires_explicit_human_decision`, `test_maximum_unicode_note_payload_is_storable`; commands audit-sequence/rollback; fulfillment supplemental-audit failure; attachment rollback |
| 10 Concurrency / idempotency | Identity prelocks then current scope/Contract/aggregate/items; revalidate waits; full immutable original response; no duplicates | concurrency actor/candidate revocation, policy decision/admin lock order, crossed assignments; fulfillment concurrent/idempotent delivery/compensation/revoked waits/exact old receipt; attachment tenth-file concurrency and event-loop lock wait |
| 10 UI isolation | Context/scope and request/refresh generation, abort and guarded callbacks; independent tabs/drafts; private blobs/retry intents | RequestWorkspace.test.tsx, state.test.tsx, api.test.ts, RequestDetail.lifecycle.test.tsx (9 regressions including stale A→B actions/candidates/history/private-file fields) |

| 11 Evolution / indicators / PARTNER | Explicit future scoped projects/cost center/material and downstream many-to-many item sources; separate Partner actor/payment-request-only; no future code/dashboard | commands/schema reject unavailable non-null reference; frontend form/parser tests; whole-diff absence inspection for future product code |
| 12 Acceptance / exclusions | Native PostgreSQL owner/runtime migration replay; scoped suites and per-task review; mandatory zero skips and final gate | schema/migration lifecycle; all named task suites below; official full backend/frontend/scripts/lint/TS/Vite/cleanup PENDING |
| 13 Risks | Bytea/immutable receipts grow; no scanner; conservative PDF; manual evidence; contract serialization; UX tentative buyer; frozen warning/audit baseline | Attachment parser/work/lexical regressions; concurrency barriers; UI lifecycle regression; risk disclosures below (not asserted as solved) |

Test paths: backend rows use `backend/tests/test_purchase_request_{schema,policy,queries,commands,concurrency,fulfillment,attachments}.py` and `backend/tests/test_migration_lifecycle.py`. Frontend rows use `frontend/src/procurement/requests/*.test.ts(x)`, `frontend/src/operational/procurement.test.ts`, OperationalScopeProvider.test.tsx and TenantWorkspace.test.tsx. Fixtures are test-only persisted inputs; there are no fake production requests/catalogues.

## Eight-task RED/GREEN and independent review ledger

| Task / final local commit | Observed RED and retained intermediate failures | Final scoped GREEN evidence / controller review |
|---|---|---|
| 1 Foundations — b9c68798e57a54fb4b78a8b5c1d67a12293b9a73 | Missing procurement package/tables; later hardening RED 4 failed (11 deselected): NULL/coalescing/INSERT freeze/payload bounds | Broad 1026 PASS predates hardening; final 41 focused PASS/zero skips + normal CLEAN + Ruff. Complete/spec compliant; plan-mandated frozen guard disposition below. Original native Stop FAIL retained. |
| 2 Policy — e67c63d90225d52409835e4321f67edb2563f3de | 42 failed, missing policy interfaces; intermediate 1 fixture constraint failure retained | 87 relevant PASS then final 44 policy PASS, zero skips, owned CLEAN/Ruff. Independent spec/quality Approved; no Critical/Important open. |
| 3 Queries — b89268e7ab762d00d2f7a41116706f38f8c798da | 5 missing query/route failures; own-list fallback RED 1 actual CAPABILITY_DENIED | Broader 109 PASS before fallback; final 65 queries/policy PASS, zero skips, six independently owned CLEAN. Approved; no Critical/Important open. Brief lifecycle overlap disclosed below. |
| 4 Workflow — 6e6e1b83fc456278d6863c9f77d9a934cbb3d131 | Missing POST; retained-item/note/attachment/reorder RED; expanded 239 PASS/1 obsolete catalogue assertion FAIL with original Stop FAIL; first urgency review RED had 2 test-attribute mistakes, valid RED 4 failed/7 passed | Initial focused 30 PASS; fresh affected catalogue 29 PASS after assertion-only fix; urgency fix final 57 PASS/zero skips/CLEAN/Ruff. Original review + fix Approved; URGENT gap resolved, guard disposition below. |
| 5 Fulfillment — 28f896cfca19624f3fde33ac611de32a8e1b5fa3 | Missing route404; first combined 8 failed/75 passed (immutable-entry FOR UPDATE needed forbidden UPDATE permission) | Fixed by aggregate serialization/ordered item locks, without grant change. Fresh 40 fulfillment PASS + prior 53 unchanged command/concurrency PASS; zero skips; all 3 CLEAN. Approved; no Critical/Important open. |
| 6 Attachments — 3350d54b791e18a01c6638c28d078cd11d06c6a1 | 10 missing module/route failures; auth-before-bytes/PNG trailer 2 failures; invalid first lock-wait experiment (ResourceClosedError) explicitly NOT valid RED, corrected lock-wait actual RED; PDF bound RED; review-fix trailer RED 7 failed/3 passed and lexical RED 6 failed/4 passed | Initial 71 regression PASS precedes last offload changes; final original 15 attachment PASS; fix1 25 PASS; final fix2 full attachment35 PASS/zero skips/CLEAN/Ruff. Review + 2 scoped fixes Approved; quadratic trailer and token-boundary Important findings resolved. Conservative PDF/no-scanner limitations remain. |
| 7 Operational UI — 858d7d139e359a319cde25188deb55b695c31720 | 4 missing-interface suites + 1 PROCUREMENT acceptance test; invalid wire/navigation/network/node behavior RED; expected API paths RED3; review stale-request callback RED5 actual private visible outcomes | Backend realigned routes54 PASS/CLEAN; final frontend390 PASS/29 files; required57/scoped94 PASS; lint/TypeScript/Vite PASS; zero skips. Original review + fix Approved; Important callback and Minor formatting findings resolved. |
| 8 Documentation + final verification — Phase A commit in task-8-report.md | Measured absent/incomplete documentation described above; no fabricated software RED | Documentation completeness/diff/ref GREEN only. Independent whole-branch review, fresh full gate, final evidence commit/clean tree and controller push are PENDING. |

Task reviews are controller-run independent reviews, not implementer self-approval. Frozen standalone migration guard duplication was an explicit plan-conflict disposition, not a hidden unresolved product defect. Baseline Starlette/npm-audit minors and specified limitations remain visible for final review. No counts in this table are final whole-project gate counts.

## Whole-branch boundary inspection (Phase A)

Commands inspected:
```powershell
git diff --name-status fa354b73cdb43d600949e54b81595f416ef5cd65..HEAD
git diff --unified=3 fa354b73cdb43d600949e54b81595f416ef5cd65..HEAD
rg -n -i 'Demo|synthetic|DeploymentBanner|localStorage|auth.*grant|finance|SQLite|skip' <saved-whole-branch-diff>
git merge-base --is-ancestor fa354b73cdb43d600949e54b81595f416ef5cd65 HEAD
git merge-base --is-ancestor 858d7d139e359a319cde25188deb55b695c31720 HEAD
git remote get-url origin
git for-each-ref --format='%(refname) %(objectname)' refs/heads refs/remotes/origin
```

Saved diff: local `task-8-whole-branch.diff` at input HEAD. This implementer audit checks domain/boundary/documentation evidence; it does not replace the controller's pending independent code review.

Actual scan occurrences were inspected:
- Demo/synthetic/DeploymentBanner/localStorage/SQLite references occur in approved docs as prohibitions/explanations. Added product domain code contains no production Demo import, synthetic data source, banner, SQLite or localStorage authority. frontend fixtures.ts is consumed by tests only.
- Finance/fiscal/financial_forecasts strings in migration0014 OLD_CHECK/NEW_CHECK, tenancy model and frontend operational closed catalogue retain inherited sensitive entries while adding only the ten procurement permissions. No FINANCIAL_FISCAL or INTERNAL_GRANTS changes, finance routes or payment writes.
- `skipped_count` in audit schemas is unchanged Data Hub import-context text in the diff, not a pytest/Vitest skip. No added test skip marker or harness weakening; official gate zero skips still must be proved in Phase B.
- GRANT statements in new migration0014 are scoped runtime database privileges, including INSERT/SELECT evidence and bounded draft/config mutation, not actor authorization grants. Existing exact unit grant predicates and TemporaryPrivilegedGrant reads validate or reject access; no permission grant creation. Policy reads explicitly reject support/grant contexts.
- Existing Data Hub workspace is extended only to expose validated real procurement navigation; inherited Data Hub behavior/finance catalogue strings are not new operational finance authority.
- Changed paths are domain/migration/catalogue/audit/API registration/operational scope/test/frontend workspace/docs. No scripts/database_harness/dependency-lock/deploy/Demo product files changed.

Base ancestry exit0; Task8 input ancestry exit0. Official origin URL is `https://github.com/HiGamer-Jr/Atlas.git`. Read-only local and remote-tracking ref values match the authoritative ledger (no fetch, push or other ref mutation in Phase A):

| Protected ref | SHA |
|---|---|
| refs/heads/main | 49a1437252f15300a04c027126940b9f7b56c4a0 |
| refs/remotes/origin/main | c28d8ca2f01ef13df9f7830d6769343642733e7d |
| refs/heads/fix/demo-customer-workspace | 00e585edadc3d8cabd841ac7c2b92a36368892c4 |
| refs/heads/integration/hiatlas-product-v1 | 0538d18b49f7c4d6efdbdec370f363c5061cc29c |
| refs/heads/feat/hiatlas-customer-scope-v1 | fa354b73cdb43d600949e54b81595f416ef5cd65 |

| refs/heads/release/hiatlas-demo-v1 | 1277afae61e349d01d04f551d505e5e491de9e29 |

## Decisions and ledger rulings, including cost if wrong

The following is the verbatim full set of `Ruling:` lines read from progress.md in Phase A. They record approved choices, rationale and cost of being wrong, including administrative boundary, prospective policy, immutable migration guard snapshots, signature/DTO/error mapping, deterministic prelocks, descriptive candidate SQL, own-read fallback, text-note compatibility, retained attachment/item IDs, deferrable reorder, sequential threadpool DB work and tentative buyer UX. They are preserved instead of silently converting tradeoffs into unconditional guarantees.



Ruling: Configuração de aprovação é por contrato, default sem row REQUIRED; modules.manage existente configura, sem conceder administração a buyer/requester — é a menor fronteira admin segura existente — se errado, exige nova capability/migração e rework da configuração.

Ruling: Mudança de política é prospectiva à decisão de triagem; pending REQUIRED não vira waiver automaticamente e decisões registradas permanecem históricas, autorização operacional sempre revalidada — preserva evidência e evita rescrever aprovações — se errado, exige mecanismo futuro explícito de reavaliação/correção de decisões.

Ruling: Scripts SDD copiados somente para tooling isolado com CRLF→LF, mesma lógica — Git Bash no Windows requer LF — se errado, refazer artefatos, sem impacto produto.

Ruling: transition_target precisa parâmetro approval_mode explícito server-side, assinatura no plan omitia-o apesar da descrição — corrigir assinatura antes Task4 — se errado, rework de transições/testes, sem relaxar autorização.

Ruling: ApprovalPolicyView uses approval_mode/version, matching persisted ContractRequestPolicy and write schema; brief shorthand mode/version resolves to approval_mode — single field across services/API — if wrong, wire field naming rework.

Ruling: Schema keeps PydanticCustomError REFERENCE_DOMAIN_UNAVAILABLE; Task4 owns allowlisted HTTP mapping in existing RequestValidationError handler, other validation unchanged — FastAPI validation precedes route command, so route-only mapping cannot emit exact spec code — if wrong, narrow handler/schema integration rework.

Ruling: Retain the plan-mandated verbatim role guard in migration0014 as an immutable self-contained security snapshot matching0013; reviewer Important1 is explicitly disposed under plan-conflict rule — extracting mutable app/shared logic or rewriting old migrations risks reproducibility and guard drift — if wrong, duplicated guards cost maintenance and require a separately versioned migration helper with replay security tests.

Ruling: Task2 candidate policy does not acquire candidate User locks late after contract/context locks; retain fresh User/platform-role validation plus existing membership/role/node/grant helpers, and Task4 prelocks assignment actor/candidate users deterministically before contract/context — avoids introducing inverted lock order while policy remains fresh descriptive validation — if wrong, assignment concurrency requires lock/revalidation rework before domain release.

Ruling: Task3 descriptive buyer list may use scoped SQL eligibility predicates instead of per-candidate lock-taking policy loop; must cover same identity/member/role/permissions/node/grant gates, fresh actor revalidation and requery count/page after waits — query must filter before pagination without new candidate lock inversion; assignment remains Task4 full locked revalidation — if wrong, eligibility drift requires shared predicate/query rework and negative-gate tests before release.

Ruling: visibility=own accepts read_own OR read_unit via narrow CAPABILITY_DENIED fallback as Task2 detail, still user+membership authorship/currentunit/private draft predicates; requester/buyer filters only visibility=unit — read_unit includes own requests and defaultown must not deny legitimate buyer, aligns detail/list semantics — if wrong, API capability/default behavior and UI expectations need rework without widening unit scope.

Ruling: Closed NOTE event variant must read existing valid text-only note history without requiring an invented digest; newly emitted services may still include digest — spec requires closed/auditable note payload, not mandatory digest for text; Task3 persisted history remains valid — if wrong, explicit event schema version/backfill migration needed, never silently discard history.

Ruling: Draft replacement preserves retained item IDs and attachments; removing an item with an existing attachment fails explicitly/atomically until authorized attachment removal (Task6), never implicit evidence deletion/reassignment — scoped FK and evidence must survive valid item edits — if wrong, explicit auditable attachment/item removal workflow/API needs redesign, no silent data loss.

Ruling: Add focused migration0015/model making only uq_purchase_request_item_position DEFERRABLE INITIALLY IMMEDIATE; draft edit defers only it then restores IMMEDIATE before response/audit/receipt — immediate uniqueness plus CHECK1..100 cannot reorder100retainedIDs safely without destroying IDs/evidence — if wrong, migration/reorder algorithm rollback rework; unchanged final uniqueness, bounds/FKs/runtime checks and RED/GREEN100items/lifecycle required.

Ruling: Retain0015 standalone frozen owner/runtime pre-DDL guard identical previousmigration, as authorized0014snapshot precedent; planmandatedImportantdisposed under conflict-rule — migration replay must not depend mutable apphelper/historyrewrite — if wrong duplicatedguards require versioned stablehelper and equivalent security replay tests in separate work.

Ruling: Asyncmultipart route moves synchronous SQLAlchemy auth/commands into existing Starlette threadpool helper with strictly sequential Session usage, not newasyncDB/dependency — real DB lock wait must not stall eventloop; prove controlledREDGREEN responsiveness — if wrong, thread/session/teardown integration needs rework before release without concurrent Session access.

Ruling: Do not add backend actor-membership representation solely to hide candidate UX actions in V1; current eligiblebuyer+fulfill/read/state can expose tentative control, backend alone proves assignedbuyer; UI must not claim assigned-to-me from role/name and must handle403closing/refreshscope — avoids invented identity authority/payload expansion, minimalUI stays candidate notproof — if wrong, nextphase adds descriptive selfmembership/effectiveaction flags and tighterUX with tests.

## Risks, lifecycle history and future phase

- **Original native stop failures remain failures.** Task 1 broad backend1026 run and Task 4 expanded239 PASS/1 catalogue assertion FAIL run each had official native Stop NONZERO_EXIT. Cause is unknown; original logs do not establish a root cause. No rerun or report relabels them PASS.
- Both original servers later ended naturally. Separate ownership-checked recovery used only the exact owned temp root, unchanged official seal/no-reparse guards, fresh PID absence, pg_ctl status3 and pg_isready2 before literal owned-root removal; each recovery PASS means recovered cleanup, not original Stop PASS. Task 1 evidence: task-1-cleanup-diagnostic.json/task-1-cleanup-recovery.txt/task-1-final-lifecycle-output.txt. Task 4: task-4-green-final-transcript.txt/task-4-cleanup-diagnostic.json/task-4-cleanup-recovery.txt. Subsequent fresh focused official lifecycles emitted CLEAN. Phase B must independently demonstrate official stop AND removal PASS.
- Tasks 3 and 6 each disclosed a brief sequencing overlap: one next test process started before the prior distinct owning process's Stop completed. Each owning process ultimately emitted its own CLEAN, with no cross-root cleanup or ownership override. This is a recorded execution deviation, not a failed Stop or evidence of an orphan; later rounds waited for CLEAN.
- PDF parser conservatively accepts classic flat-xref PDF<=4096 occupied objects, <=8 KiB trailer and <=256 tokens; nested/complex/xref-stream or otherwise valid unsupported PDFs may be rejected. No malware scanner; signature/type/work limits are not malware safety proof. Bytea storage/retention and external scanner/storage require future operational design.
- Buyer identity is tentative in UX because current representation does not carry self-membership authority. Backend remains authoritative; controls must handle denial/reset rather than infer assigned-to-me from role/name/candidate.
- Immutable event/idempotency storage has no TTL and grows. Future retention must preserve exact replay/no-double-fulfillment semantics. Contract/lifecycle serialization has a throughput cost; changing locks requires fresh administrative/concurrent security evidence.
- Frozen npm baseline audit contains a High vulnerability and existing Starlette TestClient httpx/httpx2 deprecation warning. They are reported baseline issues, unsuppressed, with no new dependencies/lockfile update in this branch. This gate is functional/security-regression verification, not a claim that dependencies or attachment content are vulnerability-free.
- Manual fulfillment is a user attestation of real delivery, not automatic order/stock evidence. Post-FULFILLED corrections, structured material/project/cost center, monetary approval chains, reporting timezone/dashboard, notifications and downstream process/order/inventory integration remain future work.
- Future PARTNER must be a separate actor/partner organization with explicitly shared downstream access; it may request payment, never approve/execute it. No Partner branch/code or payment/actor union change is part of this delivery.

## Official final gate — Phase B pending

Do not reuse task-scoped totals. After controller's independent whole-branch review and resolution/review of any proved finding, the implementer must run exactly from the worktree root:
```powershell
.\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'
```

Full native stdout/stderr and lifecycle must be captured without secrets in `docs/superpowers/validation/2026-10-08-hiatlas-purchase-request-v1-quality-gate.txt`. Start-Transcript alone can omit native stdout on this Windows host; durable gate evidence must include the actual native output and return code. Do not publish runtime/owner URLs or environment credentials.

| Required final proof | Phase A status |
|---|---|
| Complete backend tests / actual totals / zero skips | PENDING |
| Complete frontend tests / actual totals / zero skips | PENDING |
| Complete script tests / actual totals / zero skips | PENDING |
| Backend/frontend/scripts lint | PENDING |
| TypeScript and Vite build | PENDING |
| Official PostgreSQL stop and owned-root removal | PENDING |
| Independent whole-branch review / all proved findings resolved | PENDING |
| Final git diff --check / staged check / ancestry/protected refs | PENDING final; Phase A fresh checks recorded locally |
| Final evidence commit and clean working tree | PENDING |
| Controller-only exclusive branch push/upstream/local=remote SHA | PENDING; no merge/deploy |

Any failure requires diagnosis, reviewed fixes if code changes, and a new complete official gate. Recovery cannot be substituted for official cleanup PASS. Preserve strict ownership guards; no broad process kills/deletes, SQLite, skip marker, dependency change or harness relaxation. The controller performs the authorized narrow push only after final review/gate/evidence commit/clean status; no other refs, Partner branch, merge or deployment.
