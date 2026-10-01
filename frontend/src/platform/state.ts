import { createContext, useContext } from 'react';
export type AccessContext = {
    id: string;
    tenant_name: string;
    contract_id: string;
    contract_code: string;
    environment: string;
    expires_at: string;
    capabilities: string[];
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
};
export const Context = createContext<ContextState | null>(null);
export function useAccessContext() { const context = useContext(Context); if (!context)
    throw new Error('ContextProvider required'); return context; }
