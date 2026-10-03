export type Grant = {
    id: string;
    context_id: string;
    parent_context_id: string;
    tenant_id: string;
    contract_id: string;
    tenant_name: string;
    contract_code: string;
    environment: string;
    operator: {
        user_id: string;
        display_name: string;
        platform_role: 'PLATFORM_ADMIN';
    };
    grant_type: 'FINANCIAL_FISCAL' | 'MAINTENANCE';
    status: string;
    version: number;
    reason: string;
    reference: string | null;
    started_at: string;
    expires_at: string;
    ended_at: string | null;
    revoked_at: string | null;
    scopes: {
        action_code: string;
        entity_type: string;
        entity_id: string | null;
    }[];
};
