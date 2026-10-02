> Registro de revisão independente estática da Fase 7 em 2026-10-02. As seções iniciais preservam o histórico; os addendums finais fecham os achados. Referências a .phase07/logs apontam arquivos transitórios removidos após consolidação. Execuções finais e encerramento estão em phase-07.md.
# Phase 7 independent frontend review

Reviewed 2026-10-02, branch `feat/hiatlas-platform-phase-7`, base `ef9d080`. Static review of the live worktree; implementation continued during review. No product edits, tests, database calls, browser runs, or commits were performed by this reviewer.

## Verdict: remaining findings

Two P2 issues remain in the inspected source. Root should route them to the original implementer for actual RED/correction/GREEN and request a scoped re-review. This is not a full gate or real-browser approval.

### F7-FE-02 — P2: creation conflicts enter an unrecoverable existing-record refresh flow

Locations: `frontend/src/platform/organization/NodeEditor.tsx:14`, `:39`, `:43`.

A new node uses `useScopedQuery(null)`. Every mutation 409 sets `conflict=true`, and the review then removes “Voltar aos campos” and offers “Atualizar dados”. That button sets `refreshPending=true` and calls `detail.retry()`, but a null-path query cannot fetch a record or execute the effect that clears either flag. Consequently a duplicate-code creation (the backend emits `CODE_CONFLICT` 409), or a parent becoming inactive during creation, strands the user in confirmation; correcting the draft requires canceling and re-entering it from scratch. No stale-version safety requirement needs this existing-record refresh workflow for a POST without an existing id.

Suggested RED: create a complete draft, return 409 from POST, attempt the offered refresh and assert that the user can return to the populated form, change the conflicting code/parent, review, and successfully POST. Also assert no node-detail request is fabricated for a nonexistent id. Current code has no usable return-to-fields path and cannot satisfy this flow.

Expected correction: explicit create-conflict recovery that preserves the draft and permits correction/review, with any necessary parent-list refresh; retain strict successful-detail/version refresh gating for edits and lifecycle actions.

### F7-FE-03 — P2: delayed initial detail silently overwrites an enabled parent selection

Locations: `frontend/src/platform/organization/NodeEditor.tsx:25`, `:43`; `frontend/src/platform/organization/ParentOptions.tsx:5`, `:12`.

The editor disables name/active/review while its fresh detail is loading, but supplies no equivalent loading/initialization state to ParentOptions. The parent select becomes usable as soon as its independent parents query returns. If that response wins the race against the editor detail request, the user can select a different parent and then have it silently replaced by `setParent(physicalParent(fresh))` when detail resolves. The same initial synchronization correctly refreshes server state, so the missing input gate is the issue. The interface can lose a user selection and later submit the restored old parent.

Suggested RED: open edit, hold the editor's second node-detail GET unresolved while resolving the parents request. Assert the parent picker cannot be changed before fresh detail is applied (or, for a deliberate dirty-field design, assert an accepted user choice survives the delayed response). Resolve fresh detail, select a new permitted parent, review and verify PATCH keeps that chosen parent. Current code enables the picker before detail completes and overwrites its value on resolution.

Expected correction: gate parent interaction until initial detail is successfully synchronized (and during any detail reset), or explicitly protect dirty parent changes with a design that still validates current server state and version.

## Fixed during inspection; scoped evidence review pending

F7-FE-01: the initial inspected NodeEditor had the entire state synchronization statement on the same `// eslint-disable-next-line` comment, so successful GET/409 recovery never replaced current version, fields, or allowed actions. This was sent immediately to root. The latest inspected source places the statement on executable line 25, and the implementer added a successful conflict-recovery test. Read the implementation evidence: `.phase07/frontend-refresh-red.log` records the new recovery test failing because it received Canteiro Norte instead of Canteiro Revisado (1 failed/19 passed); `.phase07/frontend-green.log` records 20 passed tests after the correction. This reviewer inspected these logs without repeating the runs. This defect is no longer present in the latest static source; final scoped review should consume the implementer's evidence.

## Covered static boundaries

- Read binding `.phase07/contracts.md`, progress ledger, Phase 7 original plan/execution addendum and relevant approved-spec organization/module passages.
- Inspected OrganizationPage, NodeEditor, ParentOptions, ModulesPage, types/styles, new tests and HTTP fixture; ContractShell/AccessDialog/useScopedQuery delta; supporting real API client/auth/context providers.
- Query keys include context; old request effects abort. ContractShell keys Tools by selected context id. The API client additionally guards session/context generations. Successful context replacement unmounts editors, which abort their mutations. Real 401/CONTEXT_INVALID paths clear session/context through existing providers.
- Forbidden/missing editor reads close the editor and discard parent detail/catalog caches before retry. Explicit mutation 403 followed by a transient read failure cannot restore the discarded detail/catalog through the added discardAndRetry path. This is static inspection, not independent dynamic validation.
- Existing-record conflict gates remain blocked after failed refresh and require explicit successful refresh plus renewed review. Module initial inputs are disabled during its fresh catalog read. The two remaining findings above cover node-specific gaps.
- Physical node labels/options originate in the server type catalog, with explicit parent/code/depth, bounded list/parent pagination, and descendant exclusion request. No PROJECT physical kind or permanent-delete action was added. Server preorder is an agreed backend responsibility; no global frontend sort requested.
- Modules distinguish contracted/active, force inactive when uncontracted, consume id/version and server allowed_actions, display operational unavailability, and keep support read-only. No finance/fiscal content grant is added by frontend configuration.
- No new production browser business-data persistence found. Existing opaque context storage is reused.
- Native labeled selects, semantic cards, context shown in shell/dialog, dialog Escape/Tab handling and restoration fallback are present. Mobile CSS uses wrapping cards and bounded dialog widths; no real-browser accessibility/layout approval is claimed.

## Verification limits

No implementation tests were repeated, no full frontend gate was run, no DB was touched, and no transient repro files were created. The reviewed tests use real providers over mock HTTP with immediate responses; they do not establish the delayed-detail parent-selection race. Real root E2E, mobile 390x844, light/dark screenshots, keyboard focus across changing dialog content, contract A/A2/B switching with outstanding responses, and final gate remain controller responsibilities/pending. Current source was changing during review; re-review should use the corrected stable checkpoint.


## Scoped re-review — 2026-10-02 — supersedes initial remaining-findings verdict

Verdict: all three review findings ADDRESSED. No critical new breakage found in the correction scope. The controller-reported hyphenated-code regression is also ADDRESSED. This verdict is a static code/test/evidence review, not full frontend-gate or real-browser approval.

| Finding | Verdict | Inspected correction and evidence |
| --- | --- | --- |
| F7-FE-01: commented detail synchronization | ADDRESSED | `NodeEditor.tsx:21-32` executes fresh current/field synchronization, including the expected version and server actions, and clears conflict/review only after a successful fresh query. `OrganizationPage.test.tsx:80` verifies the changed name and PATCH version 4 after 409. Read `frontend-refresh-red.log`: 1 failed/19 passed, stale name assertion; earlier 20-test GREEN and latest 29-test GREEN cover it. |
| F7-FE-02: create 409 trapped in null-query refresh | ADDRESSED | `NodeEditor.tsx:43` branches on an existing current record. The create path returns to fields without setting conflict/refreshPending or retrying a null detail query; draft values remain intact. `OrganizationPage.test.tsx:115` verifies retained name/code, no impossible refresh button, corrected code and successful second POST. Read `frontend-review-red.log`: this test failed because Code was inaccessible. |
| F7-FE-03: delayed detail overwrites enabled parent input | ADDRESSED | `NodeEditor.tsx:17,24,47` tracks initialization in React state and passes a disabled gate for busy/loading/not-yet-initialized detail. `ParentOptions.tsx:5,12` applies it to search, select, retry and paging controls. `OrganizationPage.test.tsx:123` holds detail unresolved while the parent request finishes, verifies disabled controls, resolves fresh detail, and verifies the subsequent chosen parent remains selected. Read `frontend-review-red.log`: this test failed because the select was enabled; combined wave 2 failed/24 passed. |
| Controller-reported HTML Code pattern rejecting approved hyphens | ADDRESSED | `NodeEditor.tsx:47` removes the restrictive native pattern while retaining required/maxLength and normalization; the authoritative backend schema still validates its approved `[A-Z][A-Z0-9_-]{0,63}` format. `OrganizationPage.test.tsx:134` uses native checkValidity for CD-CWB, LOJA-BAURU and WS-OBRA-001. Read `frontend-code-red.log`: 3 failed/26 passed. |

Latest inspected `.phase07/frontend-green.log`: `vitest run src/platform/organization`, 2 files passed, 29 tests passed, started 00:07:35. The controller's preceding 26-test GREEN was superseded by this later run including the three code cases. The reviewer read saved evidence and test implementation without rerunning tests or treating mock results as browser/backend proof.

Rechecked existing-record 409/failed-refresh gating alongside these changes: create-specific recovery does not clear the existing-record conflict guard; refreshed version still replaces current before a new review. Parent initialization is kept disabled through the initial synchronization render, and server scopes/actions remain authoritative. No further critical correction regression found in this scoped pass.

No product files changed by the reviewer. No DB, full suite, browser or new transient repro run. Root still owns final frontend/full gate, backend/API verification, and real E2E with desktop/mobile, light/dark, focus behavior and contract switching. Original review's broader verification limits remain in force except that the delayed-parent race now has an inspected deferred-response regression test and all tracked findings above are closed for this scoped review.
