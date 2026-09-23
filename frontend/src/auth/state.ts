import { createContext, useContext } from 'react';
import type { ApiClient } from '../api/client';
export type Identity = {
    user_id: string;
    display_name: string;
    platform_role: 'PLATFORM_ADMIN' | 'PLATFORM_SUPPORT' | null;
};
export type Auth = {
    api: ApiClient;
    user: Identity | null;
    loading: boolean;
    busy: boolean;
    error: unknown;
    login: (email: string, password: string) => Promise<void>;
    logout: () => Promise<void>;
    retry: () => void;
};
export const AuthContext = createContext<Auth | null>(null);
export function useAuth() { const value = useContext(AuthContext); if (!value)
    throw new Error('AuthProvider required'); return value; }
