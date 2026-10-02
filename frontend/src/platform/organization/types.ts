export type NodeType = { kind: string; label: string; allowed_parent_kinds: string[] };
export type OrganizationNode = {
 id: string; tenant_id: string; contract_id: string; parent_id: string | null;
 parent_name: string | null; parent_code: string | null; kind: string; name: string; code: string;
 active: boolean; version: number; created_at: string; updated_at: string; depth: number;
 child_count: number; active_child_count: number; scope_membership_count: number; allowed_actions: string[];
};
export type Page<T> = { items: T[]; total: number; limit: number; offset: number };
export type Module = { id: string | null; code: string; label: string; contracted: boolean; active: boolean; enabled: boolean; operational_available: boolean; version: number; allowed_actions: string[] };
export type Parent = { id: string; name: string; code: string };
export function parentLabel(parent: Parent | null) { return parent ? `${parent.name} (${parent.code})` : 'Sem pai (raiz)'; }
