import { createContext, useContext } from 'react';
export type AccessContext = {
    id: string;
    tenant_name: string;
    contract_id: string;
    contract_code: string;
    environment: string;
    expires_at: string;
    capabilities: string[];
    support_session_id?: string | null;
    privileged_context_id?: string | null;
};
export type ContextState = {
    selected: AccessContext | null;
    loading: boolean;
    busy: boolean;
    error: unknown;
    recovering: boolean;
    select: (id: string) => Promise<void>;
    clear: () => Promise<void>;
    retry: () => void;
    invalidate?: (notice?: string) => void;
    notice?: string | null;
    registerSupport?: (id: string | null) => void;
    registerPrivileged?: (id: string | null) => void;
};
export const Context = createContext<ContextState | null>(null);
export function useAccessContext() { const context = useContext(Context); if (!context)
    throw new Error('ContextProvider required'); return context; }
