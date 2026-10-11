# Purchase requests V1

This document describes the implemented internal purchase need workflow. Approved source: [2026-10-08 design](../superpowers/specs/2026-10-08-hiatlas-purchase-request-v1-design.md). Validation and limitations: [durable report](../superpowers/validation/2026-10-08-hiatlas-purchase-request-v1-report.md). It supplements that approved specification without changing it. The exact official full gate passed on2026-10-11 at product commit3c79c91a77c995c8db67d00f92e8d2f871a87881, including zero-skip backend/script/frontend suites and normal owned PostgreSQL cleanup; the durable report preserves all three earlier failed attempts and remaining limitations. Controller final documentation review/publication is tracked separately.

A purchase request records a real internal need and manual evidence of fulfillment. It creates no purchase order, supplier commitment, stock movement, payment or financial approval. Data Hub imports are informational records and never become requests automatically. UUIDs are the initial displayed identifiers; no fiscal/commercial numbering is invented.

## Five authorization concepts

| Concept | Meaning and boundary |
|---|---|
| Organization available | Real active organization nodes of the contract, with valid active ancestry. An available node is not itself a grant to the actor. COMPANY is a grouping; request units may be UNIT, STORE, DISTRIBUTION_CENTER, WAREHOUSE, OFFICE, WORKSITE or BRANCH. |
| Unit scope | The actor's current ALL scope or exact active RESTRICTED membership grants within this contract. Zero restricted grants authorize no units. Ownership and ancestor names never widen scope. |
| Contracted module | PROCUREMENT must actually be contracted for this contract. Commercial presence in the catalogue alone does not authorize operation. |
| Active module | The contracted module must also be active and have implemented operational routes (operational_available). Inactive modules remain descriptive and expose no operational controls. |
| Effective capability | A persisted active custom TenantRole permission, current actor/context/session/membership/module/unit gates and command relationship/state checks together determine the server's decision. Names and discovery snapshots are never proof for a later command. |

The operational scope is a descriptive snapshot for UX. Unknown, contradictory, unavailable or oversized scope closes controls. Each API operation freshly revalidates authority. INTERNAL actors and support/temporary-grant contexts cannot become request actors through a TenantRole. No capability or role name grants assignment, finance or administration implicitly.

## Capability contract

All capabilities have prefix `procurement.requests.`; the suffixes form a closed catalogue. No automatic INTERNAL_GRANTS or financial/fiscal grants are added.

| Suffix | Business permission (also requires current read/unit authority for an existing record) |
|---|---|
| create | Create, edit and submit the author's own draft; it does not confer read access to others. |
| read_own | Original user AND membership authorship, within current units. Default own-list accepts read_own or the narrow read_unit capability fallback while retaining authorship predicates. |
| read_unit | Submitted requests in current authorized units; another author's draft remains private. |
| triage | Start/conclude triage and reject in IN_TRIAGE; no implied assign, approve or cancel. |
| approve | Human approval/rejection in AWAITING_APPROVAL; approver must differ from requester. |
| assign | Assign/reassign a current eligible buyer, without creating any role, membership or grant. |
| fulfill | Current assigned buyer records/reverses actual delivery; read_unit is independently mandatory. |
| cancel | Capability plus state-specific requester/triage relationship below. |
| close | FULFILLED closure by original requester or current buyer, with close and read authority. |
| comment | Append notes and permitted post-draft attachments; it never supplies read authority. |


## Live policy and existing implementation detail

Purchase requests use live tenant roles and exact current unit scope. The role name grants nothing; INTERNAL actors, support contexts and temporary privileged contexts are denied before capability checks. Every action requires its own procurement.requests capability and an implemented, contracted, active PROCUREMENT module. PROCUREMENT is operational together with its authenticated read and command routes. Descriptive request capabilities are omitted when no authorized, active node has an eligible request kind.

Read authorization requires the original requester user and membership for read_own, plus current unit access. read_unit also requires current unit access, and never reveals another author's draft. Action capabilities grant no read access. Commands must separately call authorize_request_read and require_request_unit for the action, then enforce ownership, relationship and transition rules. In particular, triage is never a substitute for cancel; cancellation needs cancel plus the relationship appropriate to the current status.

Buyer candidates are real active tenant users with an active, unblocked, accepted membership in this exact tenant/contract, an active role granting fulfill and read_unit, and current access to the request unit. Validation does not write memberships, roles or grants. A returned membership is a candidate at this validation point, not durable authorization; assignment and fulfillment revalidate it. Candidate discovery additionally requires actor read_unit (queries), while assignment to an already readable request uses its normal read authorization and assign.

## Existing lock order and command requirement

The existing context path takes the operator population advisory lock during authentication and locks actor User, AuthSession, Tenant (shared), Contract (exclusive), AccessContext, then Membership/TenantRole. Permission checks lock TenantRolePermission; module checks lock ContractModule and revalidate. Unit authorization refreshes Membership, walks and locks the requested OrganizationNode and its ancestors, then locks active exact MembershipUnitScope grants ordered by node ID. Organization and membership administration already serialize on Contract, and member_commands.context prelocks actor/target users in UUID order before authentication/context locks.

Policy and discovery use those helpers without adding candidate User locks after Contract/Membership locks. Buyer User and active platform role are freshly read before membership and unit waits and again afterward. These policy reads are descriptive validation; assignment commands provide the identity prelocks described below and revalidate after waits. Aggregate/item locks follow authorization locks; immutable entries are read under aggregate serialization without UPDATE privileges.


## Workflow and prospective approval policy

Creation and draft editing derive requester identity from the validated principal and membership. Draft content can remain incomplete; submission requires description, justification, needed_on and 1–100 valid decimal items. URGENT submission additionally requires a distinct bounded command reason, independent from the mandatory stored justification. The submit route accepts the canonical ReasonCommand or VersionCommand union; ordinary submission without a reason remains valid. Submitted reasons remain private event evidence and participate in the full canonical payload digest and receipt conflict/replay behavior. Draft node changes authorize both old and new nodes. Draft item IDs are validated inside the current request and retained in place, preserving created_at and attachment links. Removal of an item with an attachment fails atomically with ITEM_HAS_ATTACHMENTS until its attachment is removed through the attachment domain. Migration0015 makes only the ordering uniqueness constraint DEFERRABLE INITIALLY IMMEDIATE: item edits defer it for reordering, including 100 retained IDs, then explicitly restore IMMEDIATE before audit or response. Position bounds, identity and scoped foreign keys remain immediate. All content freezes at submission. Commands require current read authorization independently from the action capability, enforce expected_version under the refreshed aggregate lock, and increment once. Assignment requires assign even for triage; it does not grant buyer permissions. Execution additionally requires current buyer fulfill and read_unit. assigned_at and transition timestamps preserve first occurrence.

GET/PATCH /api/contract/purchase-request-policy require modules.read/modules.manage. No policy row means REQUIRED/version0. Configuration updates require expected_version and reason, share the exclusive Contract lock with decisions, and audit atomically. request-approval reads the fresh server policy: REQUIRED becomes AWAITING_APPROVAL; explicit NOT_REQUIRED becomes APPROVED with POLICY_WAIVER and no approver. Recorded mode/version are immutable decision evidence. A pending REQUIRED request still requires a human distinct from its requester after a policy change; HUMAN approval keeps the original policy snapshot.

## Identity prelocks and atomic retries

The assignment route uses a dedicated context dependency: lifecycle advisory lock, shared operator-population lock, actor and candidate User rows ordered by UUID, then the existing authentication/CSRF/opaque-context resolution path. Candidate lookup before authorization reads only an identity lock ID, and foreign/inactive candidates still fail current scoped validation without names. Standard Context is deliberately absent from that dependency chain, so it cannot acquire actor/contract locks before candidate prelocking. Services prelock identities before domain authorization. Candidate membership/role/permissions, module and node/grants are freshly checked after waits, with no late inverted candidate User lock. Aggregate locks follow authorization; item locks follow aggregate. Existing administrative lifecycle/contract serialization is preserved, including its concurrency cost.

Each successful mutation writes aggregate, private event and typed central audit in one caller transaction, without service commits. Idempotent commands also store the full RequestView receipt in that transaction. Event payloads are a closed union for transitions, assignment, items, notes, quantities and attachments; central audit stores bounded IDs, statuses, versions, policy evidence and hashes, while free text stays in private history. Audit actor_role is null for tenant users; snapshots and events retain the real membership and TenantRole provenance. The existing PostgreSQL immutable evidence grants/triggers remain unchanged.

Idempotency uses validated tenant/contract/actor/context/route/target IDs, UUID key and canonical full payload digest including expected_version. Creation target NULL uses the existing NULLS NOT DISTINCT constraint. Replay reauthorizes current action and aggregate read/unit access, then independently authorizes the stored original response visibility and original unit with current actor/scope permissions before returning its exact typed snapshot. A draft move never permits disclosure of a historic unit lost from current scope; denied replay changes no receipt or domain evidence. It neither reapplies a transition nor recomputes historic response fields. Transition authorization uses the original event's origin for reject/cancel rules. Different payload conflicts; revoked authority denies without returning the receipt. PATCH keeps optimistic version behavior without idempotent replay.

Non-null project_id/cost_center_id produce an allowlisted custom Pydantic reference error mapped to HTTP422 REFERENCE_DOMAIN_UNAVAILABLE only on request routes. All other validation retains the existing concealed VALIDATION_ERROR envelope. Operational payloads cannot carry approval_mode, requester or scope claims. Every response remains no-store.

Real PostgreSQL event/barrier tests cover policy update versus decision, membership administration versus assignment, crossed actor/candidate assignments, and separately revoked actor/candidate identities, memberships, roles, capabilities, units, grants, module, contract and context. Futures and SQL waits have explicit deadlines; no sleep determines outcomes. Private attachments are implemented; full official gate status is recorded in the durable validation report.

## Actual manual fulfillment

POST /api/procurement/requests/{id}/fulfillments accepts the canonical FulfillmentCommand: expected_version, scoped item_id, exact positive decimal quantity, evidence (1–4000 characters) and reason (1–2000). The server fixes sign=1, source_kind=MANUAL_EXTERNAL and the item UOM. This is attestation of a delivery that occurred; it writes no purchase order, inventory, Data Hub or finance record. Current assigned buyer, fulfill, read_unit, independent request read and exact unit access are required on every operation and replay.

Identity and current authorization locks precede the refreshed aggregate lock, followed by all request items in UUID order. Immutable original entries are read under the aggregate lock; no UPDATE permission or entry lock is required. Quantities are summed as Decimal under the aggregate lock and cannot exceed the item quantity. Completion is derived from every item's actual net entries; the last delivery sets FULFILLED and the first fulfilled_at, increments the aggregate once, and writes fulfillment_recorded plus fulfilled with distinct sequences at the same aggregate_version. Entry, state, typed audits, private history and original full response receipt share the caller transaction.

POST /{id}/fulfillments/{entry}/reverse accepts only canonical ReasonCommand and only executes in IN_FULFILLMENT. It appends one negative compensation with the original positive entry's exact quantity, item UOM and evidence; the positive entry remains immutable. Compensation entries cannot themselves be reversed, and a positive entry can be compensated only once. Reversal route identity includes the original entry ID, so receipt keys cannot cross entries. FULFILLED and later terminal states cannot reverse or add delivery. Authorized receipt retries return their original response after later commands without writing again. CANCELLED with partial deliveries retains PARTIAL, net quantities and the remaining quantity.

## State and quantity contract

| Command | Origin → result | Additional rule |
|---|---|---|
| create / draft edit | DRAFT → DRAFT | Own draft; create; requester/scope derived server-side. |
| submit | DRAFT → SUBMITTED | Author/create; description, justification, needed_on, 1–100 valid items; URGENT needs separate command reason. A past needed_on is allowed and signaled. |
| start-triage | SUBMITTED → IN_TRIAGE | triage. |
| request-approval | IN_TRIAGE → AWAITING_APPROVAL or APPROVED | triage; fresh REQUIRED or NOT_REQUIRED policy decides, with approval_requested or approval_waived evidence. |
| approve | AWAITING_APPROVAL → APPROVED | approve; human distinct from requester; HUMAN decision. |
| reject | IN_TRIAGE or AWAITING_APPROVAL → REJECTED | triage in the former, approve in the latter; reason mandatory. |
| assignment / reassignment | APPROVED or IN_FULFILLMENT → same state | assign; current eligible buyer, first assigned_at retained; event records later reassignments. |
| start-fulfillment | APPROVED → IN_FULFILLMENT | Current assigned buyer; fulfill plus read_unit. |
| fulfillments / reverse | IN_FULFILLMENT → same state or FULFILLED | Actual net quantities; reversal cannot occur once FULFILLED. |
| close | FULFILLED → CLOSED | close; original requester or current buyer. |
| cancel | DRAFT/SUBMITTED/IN_TRIAGE/AWAITING_APPROVAL/APPROVED/IN_FULFILLMENT → CANCELLED | cancel + reason; DRAFT author only; before fulfillment requester or triage; during fulfillment triage only. |
| notes | Any non-DRAFT, non-CLOSED state → same state | comment plus read; REJECTED/CANCELLED permit explanation without reopening. |

REJECTED, CANCELLED and CLOSED never reopen. Assignment is an attribute/event, not a status. NONE/PARTIAL/COMPLETE is derived fulfillment_state, not a permission or additional workflow state. Cancellation with partial deliveries preserves PARTIAL, net fulfilled quantities and remaining balances. FULFILLED disallows reversal in V1; correction after completion requires a future explicit process.

Bounded user text uses Unicode code-point limits consistently between Python and the browser; malformed lone surrogates and overlimit text fail. Forms use matching custom validity and pre-transport guards instead of native UTF-16 maxLength. Quantities are exact Numeric(18,6), positive on input and serialized as decimal strings, never binary floats. There are at most 100 items; requested quantities/items/UOM/node/justification freeze at submission. UOM is one of UN, KG, G, L, ML, M, M2, M3, CX, PCT. CX/PCT require the package content in specification; there is no conversion or material authority inferred from text or Data Hub IDs. Item totals are requested, signed net fulfilled and remaining; different UOM/items must not be summed as a common physical quantity. Reversal appends the exact original positive amount as one negative compensation, preserving original evidence. No partial compensations or reversal of a reversal.

## Implemented API

Prefix `/api/procurement/requests`. Authentication, existing CSRF rules and the opaque context apply; private responses are `Cache-Control: no-store`. RequestView has schema_version=1, server IDs/scope/requester/node/buyer, need fields, status/version/UTC timestamps, exact item balances and attachment metadata. List/candidates/history filter scope BEFORE count and pagination. Limit is 1–100; cursor is bounded and tied to current actor/context/query/filter/target/limit, and is never a credential.

| Method and relative path | Contract |
|---|---|
| POST empty path | Create DRAFT; real requesting_node_id/title and allowed draft fields/items; 201. |
| GET empty path | visibility own (default) or unit; status/node filters; requester/buyer filters only in unit mode. |
| GET /buyer-candidates | requesting_node_id, limit/cursor; assign + read_unit; membership_id/display_name only, no email. |
| GET /{id} | Current authorized RequestView; foreign/missing records uniformly 404. |
| PATCH /{id}/draft | expected_version and permitted draft fields/items; scoped retained item IDs and atomic replacement. |
| POST /{id}/submit | expected_version; optional reason for ordinary priority, mandatory separate reason for URGENT. |
| POST /{id}/start-triage, /request-approval, /approve, /start-fulfillment, /close | VersionCommand with expected_version. |
| POST /{id}/reject, /cancel | ReasonCommand with expected_version and nonempty reason. |
| POST /{id}/assignment | expected_version and buyer_membership_id; real target freshly validated. |
| POST /{id}/fulfillments | expected_version, item_id, exact positive quantity string, evidence and reason. |
| POST /{id}/fulfillments/{entry}/reverse | expected_version/reason; scoped original entry, only IN_FULFILLMENT. |
| POST /{id}/notes | expected_version/text; private append-only event. |
| GET /{id}/history | Scoped paginated private business events; no audit.read requirement or administrative audit payload. |
| POST /{id}/attachments | Bounded multipart file/expected_version/optional item_id; state/read/action gate before file bytes. |
| GET /{id}/attachments/{attachment}/download | Fresh record read authorization; private binary attachment download. |
| DELETE /{id}/attachments/{attachment} | expected_version; own DRAFT/create only; event and deletion atomic. |

Approved draft/assignment paths are `/{id}/draft` and `/{id}/assignment`. Task 7 corrected earlier route drift with HTTP RED/GREEN; no legacy aliases are retained.

GET/PATCH `/api/contract/purchase-request-policy` require modules.read/modules.manage, respectively. PATCH requires expected_version, reason and approval_mode; absent row returns REQUIRED/version0. Operational payloads cannot choose a waiver or contain approval_mode, actor/scope claims or generic status edits. Unknown fields fail validation; non-null project_id/cost_center_id receive REFERENCE_DOMAIN_UNAVAILABLE, with no invented references.

All POST commands require a UUID Idempotency-Key. Existing aggregate mutations also require positive expected_version; policy's initial expected_version is 0. Key identity includes tenant/contract/actor/context/route/target; canonical digest covers every command field including expected_version and file digest. Successful replay reauthorizes current action/read/unit access and returns the immutable original complete RequestView, even after later aggregate changes. Changed payload returns 409 IDEMPOTENCY_CONFLICT; revocation returns denial without receipt disclosure. PATCH and DELETE do not replay: a lost response requires a fresh authorized GET/version decision.

| HTTP | Codes / meaning |
|---|---|
| 401 | Existing invalid/expired session authentication envelope. |
| 403 | CAPABILITY_DENIED, UNIT_SCOPE_DENIED and existing module/context denial codes; no hidden record disclosure. |
| 404 | NOT_FOUND uniform for missing/foreign request, item, attachment or entry. |
| 409 | VERSION_CONFLICT, INVALID_TRANSITION, INVALID_POLICY, IDEMPOTENCY_CONFLICT, OPERATIONAL_SCOPE_INVALID; ITEM_HAS_ATTACHMENTS; FULFILLMENT_EXCEEDS_REMAINING, FULFILLMENT_ALREADY_REVERSED, INVALID_FULFILLMENT_ENTRY. |
| 413 | ATTACHMENT_TOO_LARGE (5 MiB file bound). |
| 422 | VALIDATION_ERROR, REFERENCE_DOMAIN_UNAVAILABLE, CURSOR_INVALID, ATTACHMENT_INVALID, ATTACHMENT_LIMIT (ten files). |
| 503 | OPERATIONAL_SCOPE_TOO_LARGE; controls remain unavailable. |

Error payloads retain the existing concealed envelope; validation does not echo untrusted input. The custom reference-domain mapping is narrowly allowlisted on purchase request routes.

## Private file contract

PDF, PNG, JPEG and valid UTF-8 TXT only, with verified content rather than client MIME authority; maximum 5 MiB/file, ten files/request. No HTML, SVG, encrypted file, executable or remote fetch. Filename is sanitized; digest SHA-256/size/media type/uploader and optional scoped item association are recorded. Bytes are private PostgreSQL bytea, absent from detail/list/history/audit. Download uses attachment Content-Disposition, nosniff and no-store, never a public URL.


Own DRAFT upload/removal requires create and current read. Upload in SUBMITTED, IN_TRIAGE, AWAITING_APPROVAL, APPROVED, IN_FULFILLMENT or FULFILLED requires comment plus read; terminal states reject new uploads. Submitted attachments are preserved; notes may explain supersession without silently deleting evidence. Removing an attached draft item fails ITEM_HAS_ATTACHMENTS until its file is explicitly removed. File mutation, aggregate version, event/audit and receipt commit atomically. Bounded stream reads do not trust Content-Length; auth/state checks precede bytes. Sync SQLAlchemy operations are offloaded through existing Starlette threadpool with strictly sequential Session use to keep actual DB lock waits off the event loop.

PDF acceptance is conservative: PDF 1.0–1.7, classic xref, at most 4096 occupied objects, one flat trailer with Root/Size and optional Info/hex ID, <=8 KiB trailer and <=256 tokens, complete lexical boundaries and valid root references. Xref streams, complex/nested/incremental formats can be rejected even if otherwise valid. PNG requires final IEND with no trailing content; image dimensions/work are bounded. These checks are not malware scanning. Scanner/external storage are future operational work; retention follows the request, with no Data Hub TTL.

## Functional UI and authority boundary

The tenant workspace offers own requests and a unit queue only from validated live scope, module availability and descriptive read capabilities. Forms collect real multi-item need/UOM/quantities; no project/cost-center/material demo selectors. Detail shows HUMAN versus POLICY_WAIVER, server decision mode, UUID, private history/files and "Atendimento registrado manualmente". Triaging concludes through request-approval with no browser waiver selector. Needed date warning uses local calendar date for UX, not a contractual reporting timezone.

Buyer controls are tentative candidates: existing wire data cannot prove the current actor is the assigned buyer. Role/name/eligible buyer is not identity proof; backend owns that decision. A 403 closes/refreshes scope. A future descriptive self-membership/action flag could tighten UX without becoming reusable authority.

Context/scope changes and request A→B changes invalidate generations, abort transports and reset local fields/edit state. Late action/candidate/history/download callbacks cannot restore prior private data or controls. Tabs have independent contexts/drafts; 409 versions never silently merge. Retry keys bind to the same intent/payload/version/bytes; changed intent uses a new key. Downloads use private Blob URLs and revokeObjectURL; no scope/capability authority is cached in localStorage.

## Persistence, limitations and future domains

Migration0014 registers the scoped aggregate/items/events/entries/attachments/receipts/policy in app/db/models.py with composite FKs, immutable evidence/runtime protections and closed SQL capability catalogue. Migration0015 only defers item-position uniqueness during reorder, restoring immediate validation before response/evidence; other bounds/identities/FKs remain immediate. Standalone frozen owner/runtime pre-DDL guards are intentionally retained per controller rulings, rather than rewriting migration history. Runtime remains a non-owner with minimum permissions; scoped queries remain mandatory, with no assumption of universal RLS.

Idempotency receipts/events are immutable without TTL; storage grows and requires future retention design that cannot permit duplicate delivery. Private bytea files also grow. Existing lifecycle/Contract serialization reduces throughput but preserves administration/assignment/decision consistency; changing it requires proven lock/revalidation semantics. Full project verification and independent branch review status are stated only in the durable report.

Projects, cost centers and material master remain separate future official domains with scoped FKs/active association checks. WORKSITE can be a real unit now, not a project authority. Downstream processes/orders/transfers will link many-to-many by item and actual quantity; no single header purchase_order_id or free UUID polymorphic authority is added now. Real timestamps/balances support future indicators; no dashboard, synthetic denominator or cross-UOM total is produced.

PARTNER remains a future separate actor class and partner organization, distinct from TenantRole and INTERNAL. Only explicitly shared downstream processes could allow milestones, documents/NF/NFS, payment requests and tracking of its own processes/payments. It must never approve or execute payment or gain broad finance/administration; downstream sharing never grants source-request/unit access. No actor union, Partner branch/code, membership or payment capability is introduced here.

Excluded: monetary approval chains, notifications/email, request-creating imports, synthetic catalogues, suppliers/quotations/orders, automatic stock/transfer, finance/fiscal/payment workflows, dashboards, Demo/DeploymentBanner or deploy changes, new dependencies and test harness relaxation.
