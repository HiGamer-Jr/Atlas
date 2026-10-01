export type Page<T> = {
    items: T[];
    total: number;
    limit: number;
    offset: number;
};
export type Member = {
    id: string;
    user_id: string;
    display_name: string;
    email: string;
    role_id: string;
    role_name: string;
    active: boolean;
    blocked: boolean;
    invitation_pending: boolean;
    version: number;
    allowed_actions: string[];
    last_access_at: string | null;
    invitation_status: string | null;
};
export type Role = {
    id: string;
    code: string;
    name: string;
    description: string;
    classification: string;
    active: boolean;
    support_assignable: boolean;
    sensitivity_locked: boolean;
    support_eligible: boolean;
    permissions: string[];
    version: number;
    member_count: number;
};
export type Capability = {
    code: string;
    domain: string;
    sensitive: boolean;
};
export type AuditRow = {
    id: string;
    occurred_at: string;
    actor_name: string | null;
    actor_id: string | null;
    action: string;
    outcome: string;
    entity_type: string;
    entity_id: string;
    reference: string | null;
    request_id: string;
};
export type AuditPage = {
    items: AuditRow[];
    next_cursor: string | null;
};
export function formatDate(value: string | null) { return value ? new Intl.DateTimeFormat('pt-BR', { dateStyle: 'short', timeStyle: 'medium', timeZoneName: undefined }).format(new Date(value)) : 'Não registrado'; }
export const timezone = Intl.DateTimeFormat().resolvedOptions().timeZone;
