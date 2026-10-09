# HiAtlas customer operational scope v1 — approved written spec

Status: written spec approved by the user, incorporating all four mandatory amendments. The implementation plan was subsequently approved and Native execution authorized. Product implementation and official final quality gate are complete; all checks PASS with zero skips.
Base: integration/hiatlas-product-v1 at 0538d18b49f7c4d6efdbdec370f363c5061cc29c.
Branch: feat/hiatlas-customer-scope-v1.

## Goal and boundaries

Expose the authenticated customer's real server-calculated operational context. Keep tenant, contract, role, membership unit scope, organization hierarchy, commercial module state and operational authorization distinct. No main base/change, public Demo change, deployment, push, merge, synthetic workspace records or permission bypass.

## Existing behavior verified

- X-HiAtlas-Context resolves a session/actor-bound context and revalidates active tenant, contract, membership and role.
- MembershipUnitScope currently contains explicit node grants. Zero grants does not authorize all units.
- Node operations already check active ancestors and scoped composite foreign keys.
- Module configuration does not grant permissions. Only DATAHUB is operationally implemented; other domain modules remain unavailable.
- Finance/fiscal/sensitive capability classifications and internal operator separation must remain intact.

## API approach

Add GET /api/context/operational-scope, with no tenant, contract, role, membership, node or module selector in its input. The only context selector is the existing opaque X-HiAtlas-Context header. No organization.manage, roles.manage or modules.read requirement is added to self-discovery.

Return a versioned discriminated response:

- schema_version: 1.
- actor_kind: TENANT or INTERNAL.
- context_id: the validated opaque reference.
- tenant: id and name from this context only.
- contract: id, code, name and environment from this context only.
- customer_scope: null for internal operators; required structured object for TENANT.

TENANT customer_scope:

- role: id, code and name of the active membership role.
- unit_scope: mode ALL or RESTRICTED, never inferred from an empty node list.
- organization_nodes: only active, usable nodes authorized in this tenant/contract; id, code, name, kind and safe parent_id.
- modules: contracted module rows only, with code, label, contracted=true, active and operational_available. Inactive contracted modules remain visible as unavailable. Unknown module codes fail closed. A contracted active module does not imply that its operational domain exists.
- capabilities: server-calculated effective capabilities, filtered through existing sensitive rules, module/implementation gates and required unit scope where applicable. These capabilities are a server-calculated description for UX only, never a reusable authorization proof or credential. Every backend operation independently recalculates the live context, unit scope, module gates and required capability, even when the browser presents a previously successful scope response.

For restricted scope, expose only exact authorized nodes; do not expand a granted parent to its descendants. Parent IDs are returned only when the parent is also in the returned authorized node set. Unauthorized ancestors are checked for viability but their IDs/names are not disclosed. This gives the minimum safe visible forest without manufacturing units or broadening authorization.

Internal administrators/support receive customer_scope=null, never a fabricated TenantRole. Support/privileged contexts must not use this endpoint to obtain additional tenant operational privileges.

## Explicit total-unit scope

Add a constrained membership unit_scope_mode field: RESTRICTED or ALL, default RESTRICTED. Existing memberships migrate to RESTRICTED, preserving all existing deny/explicit-grant semantics. No sentinel node and no automatic ALL upgrade.

Extend the existing administrator-only unit-scope command and its audit snapshot with explicit mode, preserving version checks, role/sensitivity restrictions, context revocation and organization.manage. Legacy requests that omit mode retain restricted semantics. ALL is an explicit administrator action in the current tenant/contract; node IDs do not themselves grant ALL.

Share one server resolver across self-discovery, organization-node authorization and Data Hub selection. ALL authorizes only active nodes of this context with active valid ancestors; RESTRICTED requires an active exact MembershipUnitScope row. Browser IDs are only candidates checked by that resolver.

ALL -> RESTRICTED never reactivates historical or dormant grants. Every restricted update replaces the authorized set with the explicitly submitted node_ids; no submitted set means an empty set. Existing node_ids remains required for legacy requests; a mode-aware request may omit it and receives empty-set semantics. ALL rejects nonempty node_ids and deactivates all prior restricted grants. Returning to RESTRICTED may reactivate a historical row only when that exact node is explicitly submitted and freshly validated. Zero nodes and revoking the last restricted grant authorize zero nodes.

Mode changes and replacement of restricted grants are one atomic command. Lock the scoped membership, validate expected_version and all requested nodes, then update mode, replace grants, increment membership version, revoke affected contexts and write before/after audit snapshots in the same database transaction. No intermediate state is committed. Version conflict, node validation failure or audit failure rolls back every change, including context revocation. Concurrent updates cannot combine a mode from one request with grants from another. Audit snapshots include mode, explicit node_ids and version. No relaxation of database_harness, RLS/grants, schema constraints, PostgreSQL requirement or sensitive classifications.

## Complete bounded scope response

V1 returns the complete authorized visible forest or an explicit error; it never returns a partially truncated scope tree, a successful partial result or pagination. Define MAX_OPERATIONAL_SCOPE_NODES = 1000 for the complete current-contract organization graph examined for viability, including inactive nodes and ancestors. Read at most limit + 1 scoped rows to detect overflow before constructing a response. Above this bound, return HTTP 503 with code OPERATIONAL_SCOPE_TOO_LARGE and no scope payload; do not disclose counts or foreign data. This conservative bound can reject a small restricted scope in a large contract and is an explicit V1 limitation. A future paginated contract needs a separate design.

The frontend clears any previous snapshot, presents an explicit unavailable state and releases no operational controls on this error. A user must not gain operations by manipulating a failed or incomplete response. Individual backend operation authorization remains a fresh scoped check; a discovery snapshot is never an authorization prerequisite or proof.

## Revalidation and isolation

Read fresh rows with scoped tenant/contract predicates and existing lock order. Revalidate before returning, including after lock waits. Inactive membership/role/contract invalidates context; node/scope/module changes change availability on the next request. Do not reuse frontend data as authorization. Cycle, foreign linkage or unknown mode/type/state fails closed.

Context responses must be no-store. Each tab retains only its own existing opaque reference in sessionStorage; no authorization cache in localStorage. Changing or revoking one context does not mutate the other's reference.

## Frontend approach

Add reusable operational scope types, structural validation and provider/hook keyed by the validated context ID. Fetch self scope only for a tenant customer, with cancellation/generation protection on context changes. Clear stale scope before loading/revalidation and on context/session invalidation. Revalidate on focus/restore using the server, retaining the existing independent-tab behavior.

Unknown schema version, actor mismatch, missing tenant role, malformed node types/relationships, invalid modes or contradictory module states produce an explicit unavailable state and no operational controls. Remove reliance on the prototype profile catalogue for this real flow; a server-valid custom role is valid even if absent from the old local seven-profile display map. Backend capabilities/module state determine the real Data Hub entry.

Display real identity/scope metadata and unavailable states in the existing TenantWorkspace. Do not rebuild operational dashboards, selectors for nonexistent domains or synthetic records. Do not infer authorization from node visibility or module visibility.

## Terminology that the UI must preserve

- Available organization node: active real structure in the current contract whose ancestry is viable. Existence is not a user grant.
- Authorized unit scope: explicit ALL policy or active exact membership grants that determine which available nodes this user can use.
- Contracted module: commercial configuration for this contract. It grants no user permission.
- Active module: contracted module currently enabled in configuration. It still may have no implemented operational domain.
- Effective capability: permission computed by the server under current membership/role, sensitive classifications, context and applicable operational gates. Every operation independently checks it again.

## Required verification

PostgreSQL backend tests additionally cover historical-grant non-reactivation on ALL -> RESTRICTED, explicit replacement/empty-set transitions, concurrent version conflicts and full rollback on audit failure, the exact 1000-node boundary and explicit overflow with no partial payload, and replay of a stale capability summary after revocation. Backend tests cover ALL, one/multiple/zero restricted nodes, foreign tenant and foreign contract exclusion, inactive node/ancestor, revoked scope/membership/role/contract, contracted active/inactive/uncontracted modules, forged selectors, independent contexts, internal role separation, unknown/corrupt states, preserved financial restrictions and real Data Hub authorization under ALL/RESTRICTED.

Frontend tests cover strict response validation, fail-closed loading/error, absent synthetic fallback, server-derived custom role, contracted inactive module unavailability, capability-controlled Data Hub, context switch/focus revocation and stale-response isolation across independent providers/tabs.

Run focused tests before the full gate. Final required command:

`.\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'`

Require full backend/frontend/scripts tests, zero skips, lint, TypeScript/Vite build, working/staged git diff --check and official PostgreSQL cleanup PASS. Review the complete diff for security and Demo leakage. Commit locally only after verification; no push.

## Deferred work and risks

Full operational domain UI and datasets, synthetic Workspace replacement, automatic parent-to-descendant grants, unit-specific capabilities, billing/provisioning UI and cross-context aggregate views remain out of scope. Minimal administrative API support for explicit ALL is included; a redesigned administrative scope editor is deferred.

Contracts exceeding the explicit 1000-node graph bound fail discovery closed, including small restricted scopes; future pagination is deferred. Returned scope can become stale after response delivery; only backend operation revalidation is authoritative. Migration preserves existing restrictions and requires PostgreSQL schema verification.

## Consistency self-review

Reviewed after incorporating the four approved amendments: ALL never implies dormant grants; every RESTRICTED set is explicit or empty; mode/grants/version/context revocation/audit share one transaction. Complete bounded discovery and the safe visible forest are compatible: unauthorized ancestors are validated but never disclosed, and no authorized result is silently omitted. Capabilities and visible nodes remain UX descriptions, with fresh backend operation checks as the only authorization authority. Internal roles, sensitive classifications, opaque contexts and independent tabs retain their existing boundaries. Required verification now includes transitions, rollback/concurrency, overflow and stale-summary replay. No unresolved contradiction blocks the implementation plan.
