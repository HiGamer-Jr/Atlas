# Customer operational scope V1

GET /api/context/operational-scope consumes only the authenticated session and existing opaque, actor/session-bound X-HiAtlas-Context. No administrative permission is needed for a customer's own scope. Browser tenant/contract/node/module/role selectors never define its authority. Responses and errors use Cache-Control: no-store.

## Wire contract

schema_version=1; actor_kind=TENANT|INTERNAL; context_id; tenant={id,name}; contract={id,code,name,environment}; customer_scope.

TENANT customer_scope contains role={id,code,name}, unit_scope={mode:ALL|RESTRICTED}, organization_nodes=[{id,code,name,kind,parent_id}], modules=[{code,label,contracted:true,active,operational_available}], capabilities=[code]. INTERNAL returns customer_scope=null, including PLATFORM_ADMIN/PLATFORM_SUPPORT with their own membership. No tenant role is fabricated and no internal operation privilege is added.

Only authorized exact nodes are exposed. A parent_id is exposed only if that parent is also authorized and returned; unauthorized ancestors are validated without disclosing their identity. Grants do not expand to descendants. Inactive node/ancestor/grant removes availability; inactive membership/role/tenant/contract invalidates the context.

## Five distinct concepts

| Concept | Meaning | Does visibility authorize an operation? |
|---|---|---|
| Available organization node | Real active structure with viable ancestry in this contract | No |
| Authorized unit scope | Explicit ALL policy, or active exact membership grants intersected with available nodes | Only the backend's current check is authoritative |
| Contracted module | Commercial contract configuration | No |
| Active module | Contracted module enabled now | No; implementation and permission are also required |
| Effective capability | Live server calculation under context, role, sensitivity, module and applicable unit gates | Returned codes are UX descriptions, never reusable proof |

Every backend operation recalculates live context, scope, module and capability. Returning datahub.read does not grant arbitrary units or datasets. Dataset-specific module/sensitivity/unit checks stay authoritative. The existing server-side datahub_enabled feature gate also controls operational_available and descriptive capabilities, without changing the contracted module active flag. Only DATAHUB has an implemented operational domain; inactive contracted modules remain listed as unavailable, uncontracted modules are omitted.

## Atomic administrative scope command

Existing PUT /api/memberships/{membership_id}/unit-scope remains administrator-only with organization.manage, expected_version and existing sensitive/internal identity restrictions. Request: {mode:ALL|RESTRICTED,node_ids:[UUID],expected_version:int}. Legacy requests omitting mode require node_ids and mean RESTRICTED. Explicit-mode requests omitting node_ids mean an empty list. ALL rejects nonempty node_ids.

A scoped locked membership, expected_version check, complete node validation, mode update, replacement of grants, version increment, context revocation and typed before/after audit occur in one transaction. Failure rolls back all changes. Concurrent writers cannot interleave policy/grants; stale version returns 409 VERSION_CONFLICT. ALL deactivates old restricted grants. ALL -> RESTRICTED never implicitly restores them; only freshly submitted, validated IDs are activated. Empty means zero units. The migration defaults existing memberships to RESTRICTED. Downgrade removes ALL representation and deliberately narrows it to existing explicit grants (normal ALL commands leave zero active grants).

## Complete bounded discovery and failure states

V1 examines at most 1001 graph rows to enforce MAX_OPERATIONAL_SCOPE_NODES=1000, counting inactive nodes and ancestors within the current contract. At most 1000 yields a complete authorized visible forest; above that returns HTTP 503 OPERATIONAL_SCOPE_TOO_LARGE without customer_scope. A small restricted set in a larger contract also fails. No successful truncated tree or pagination exists. Cycles, invalid containment or unknown mode/state fail closed with 409 OPERATIONAL_SCOPE_INVALID; schema constraints reject unsupported persisted values.

Frontend treats idle/loading/invalid/error/overflow as closed, discards stale snapshots, and exposes no operational controls. It uses in-memory state and the existing tab-local opaque context reference; never authorization in localStorage. Focus/restore/context changes fetch fresh server state with cancellation/generation protection. A legitimate backend custom role does not depend on the prototype's seven-profile catalogue.

## Deliberate deferrals

Full operational domain UI/datasets, synthetic Workspace replacement, descendant grants, per-unit capabilities, administrative scope editor redesign, provisioning/billing UI and discovery pagination remain separate phases. Minimal API support for explicit ALL is included. No Demo configuration, banners, fake entities, exchange rates or operational records are added.

## Validation

Use the official command from this worktree: .\scripts\check-local.ps1 -PostgresRoot 'D:\Atlas\.tools\pgsql18'. Require full backend/frontend/scripts tests, zero skips, lint, build, working/staged diff checks and PostgreSQL cleanup. Results are reported only after observing the completed gate.

During successful same-context revalidation, operational controls are hidden and effects suspended using React Activity; draft state survives an unchanged valid scope. Failed, revoked or changed scopes destroy the workflow. Individual explicit-node operations validate only their live candidates and do not depend on successful full-tree discovery.
