# Phase 8 independent frontend static review

Reviewed 2026-10-02 against base `62d5508` in `feat/hiatlas-platform-phase-8` while the frontend owner was still adding regression coverage. Scope: tracked frontend diff plus new `frontend/src/support` sources/tests; existing AuthProvider, ContextProvider, ApiClient, access dialog/query, management shell integration; approved Phase 8 plan/spec and `.phase08/contracts.md`.

This is source review only. Reviewer did not run tests, browser, database, quality gate, or visual checks. The implementation was changing during review; findings need the owner's RED/GREEN fixes followed by scoped re-review. No Phase 9 review or changes.

## Findings sent to root and frontend owner

1. **P2: Newly discovered support does not suspend the normal shell while verification is pending.** `frontend/src/support/SupportSessionProvider.tsx:55-60` runs `verify` when an existing parent's `support_session_id` changes, but `restoring` is only initialized from discovery/storage at initial mount (`:14`). A previously normal parent shell can learn about an active support session on parent focus validation (for example, another copied same-parent tab committed support), then keep Users/management/switch controls visible until the delayed support GET succeeds. Those mounted management queries also remain live. Fail closed as soon as new discovery requires validation. Regression: normal mounted shell, parent focus returns an active support id, defer support GET, assert management/switch absent before resolving it. This is a frontend presentation/lifecycle gap; server authorization remains mandatory.

2. **P2: Shared parent/support expiry can bypass the support terminal notice and observation.** `frontend/src/platform/ContextProvider.tsx:90` schedules `forget` without a message. Support has its own timer in `frontend/src/support/SupportSessionProvider.tsx:74-79`, responsible for the neutral notice and one terminal GET. Since support expiry is capped by parent expiry, their deadlines may be equal. The earlier parent timer can discard the selected context, unmount the support provider, and cancel its timer before it sends the observation or notice. The new timer test used an earlier support deadline with a far-future parent, so it did not cover this case at review time. Regression: both expire at the same deadline, assert child data/storage cleared, neutral accessible notice retained, and exactly one permitted terminal observation attempted without polling.

3. **P2: Successful focus verification retains stale workspace metadata.** `frontend/src/support/Workspace.tsx:11,26` keys the request on support id, child context id, busy, and local revision. Successful support verification (`SupportSessionProvider.tsx:31`) replaces the session object but preserves these inputs. Therefore a focus check that keeps the session ACTIVE after live module/permission changes does not refetch or clear `effective_access`/module metadata. The visible contracted/active state stays from the old response. Add a successful-focus generation/revision or equivalent fresh workspace validation. Regression: change workspace metadata after the initial read while session GET stays ACTIVE with the same ids; focus must fetch/render the new metadata. No operational action currently exists, so this is stale state rather than an asserted authorization bypass.

## Confirmed static properties

- Authenticated operator identity is retained; there is no target login, password flow, or target credential storage.
- Workspace requests supply the child context explicitly. Parent ContextProvider remains the normal owner and ApiClient default is unchanged.
- Start/end/terminal paths cancel scoped requests; workspace cleanup uses AbortSignal plus ApiClient generation enforcement against late fetch completion.
- Opaque support ids alone are stored under a separate sessionStorage key; no support storage events/global support cookie were introduced.
- Active shell replaces management and context-switch controls; operator/viewed identity, contract/environment, read-only label, warning and end control are explicit.
- Financial/fiscal/audit module codes are defensively excluded from Workspace rendering; this defense cannot establish server authorization.
- Native existing AccessDialog provides contextual dialog labels, initial focus, Escape handling and Tab trap; committed end requests focus on normal portal heading.
- CSS declares sticky banner, theme variables and mobile wrapping, but actual sticky position, contrast, viewport behavior and keyboard execution require root browser evidence.

## Remaining evidence

Owner/root must supply fresh RED/GREEN evidence for findings and full frontend gate. Tests inspected include restored-session chain/discovery, stale discovery after end, failed start/end, late workspace after end/revocation, HTTP rejection, keyboard Escape, themes and independent ApiClient flows. A same-document mocked pair of flows with storage disabled does not by itself prove real browser tab/sessionStorage independence. Root owns actual browser/E2E and visual verification.

## Scoped re-review checkpoint — 2026-10-02

The original three P2 findings are resolved statically in the current source:

- Discovery: SupportSessionProvider now derives restoring from an unended discovered id that differs from the validated session, so Shell suppresses management in the same render before verification completes. Regression defers the discovered support GET.
- Shared deadline: ContextProvider expiry now captures discovered/stored support id, retains neutral notice and attempts one terminal read before child unmount. Regression invokes the first scheduled expiry callback alone and flushes React to model separate browser tasks rather than batching both timers.
- Workspace freshness: successful verification increments a provider revision included in the Workspace request key; prior data is hidden, prior request aborted, and fresh module metadata read for unchanged ids. Regression changes active to inactive while the support remains ACTIVE.

Start/restored banner focuses its region and announces a stable read-only status; timer does not announce each tick. Committed end retains ended.current before clearing session/storage, suppresses stale parent discovery after reload, refreshes parent, and focuses the operator portal heading. Existing regressions cover late workspace end/revocation and stale discovery after failed logout. ApiClient source remains unchanged and provides abort plus global/scoped generation assertions after fetch and payload reads.

One additional **P2 pending** was sent to root/frontend owner: parent-first revocation. ContextProvider handleContextInvalid(forget) and parent focus 403/404 call forget without a support message. If parent rejects first (especially CONTEXT_INVALID), it clears storage and unmounts/aborts support before child invalidation can supply the neutral accessible notice. Existing revoked test keeps parent GET valid and rejects support GET, so it does not cover this ordering. Also check the same shared-expiry case after own start with sessionStorage unavailable: selected discovery can still be null, and readSupport cannot supply the active session id. Required fix should retain support presence for parent terminal lifecycle without assuming optional storage is available.

Owner reported 26 support tests / 211 complete tests plus oxlint/build passing. Reviewer confirms the regression source exists, not those execution claims. Final disposition awaits the parent-first terminal notice correction; real browser/E2E/visual/accessibility evidence remains root-owned.

## Final frontend disposition — 2026-10-02

Re-read the residual correction in current sources and the three added regression bodies. No actionable frontend finding remains in this reviewed Phase 8 scope.

ContextProvider now keeps an opaque supportReference in memory, set from validated discovery and explicit registerSupport on successful start/verify, and cleared on committed end/forget. forget snapshots support presence and whether a normal parent was active before clearing refs, then infers or preserves the neutral terminal notice. Thus parent-first CONTEXT_INVALID/403/404 cannot erase the explanation while aborting child verification. Parent expiry also reads the memory reference first, covering own start when sessionStorage is unavailable. Regressions include deferred child validation plus parent-first denial, and storage-unavailable start followed by parent timer first. Owner reported actual RED/GREEN 29 support tests and lint zero; reviewer inspected source only.

Failed end now renders its ErrorNotice within the active modal dialog, so it remains accessible while the modal makes background content inert. Start/restored banner focus, stable status announcement, quiet timer, contextual end confirmation and committed end focus are supported by current code. The history menu and fixtures now use the canonical backend capability support.history.read; the earlier cross-interface observation was overtaken by the owner's correction while sources were changing and is resolved.

Late request safety is layered: ApiClient rejects scoped/global epochs after fetch/payload, Workspace checks abort and discards stale keys, support start/verify check their generation, invalidation/end cancel scoped requests, and logout clears global requests/operator state. This is a static assessment, not proof that every browser ordering was executed.

Final frontend review is clear subject to root's fresh final gate and real browser/E2E evidence. Reviewer made no product edits and executed no tests, browser or database. Visual sticky position, light/dark contrast, 390x844 layout, native keyboard/focus behavior and real separate-tab storage remain explicitly unverified here.

## Final history presentation re-review — 2026-10-02

Root identified requirement 19's missing mode/duration presentation after the broader review. Scoped re-read of current SupportSessionHistory.tsx and the two added SupportSession.test.tsx regressions is clear.

Each history record now renders READ_ONLY as Modo: Somente leitura; an unexpected runtime mode has the conservative Indisponível fallback. Completed duration derives only from server started_at/ended_at, floors elapsed seconds and formats hours/minutes/seconds; missing, non-finite or negative elapsed values return Não registrada. ACTIVE shows Em andamento without deriving an invented end time or browser timer. Existing contextual query, bounded pagination and projection consumption are unchanged.

The added regressions assert an ENDED server interval of 7 min 35 s with the read-only label, and ACTIVE Em andamento with that same mode. The completed fixture uses history fields without parent/child ids and asserts those ids are not displayed. Reviewer inspected these bodies and arithmetic statically; root/owner reported actual RED2 then GREEN31 support tests, but reviewer ran none. No new actionable finding; final source disposition remains clear subject to root's fresh final gate/browser evidence.
