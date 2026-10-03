import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { ApiClient } from '../api/client';
import { ApiError, isAbort } from '../api/errors';
import { storeContext } from '../platform/storage';
import { storeSupport } from '../support/storage';
import { storePrivileged } from '../privileged/storage';
import { AuthContext, type Identity } from './state';
export function AuthProvider({ children }: {
    children: ReactNode;
}) {
    const [api] = useState(() => new ApiClient());
    const [user, setUser] = useState<Identity | null>(null);
    const [loading, setLoading] = useState(true);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState<unknown>(null);
    const generation = useRef(0);
    const locked = useRef(false);
    const clear = useCallback(() => {
        generation.current++;
        api.cancelAll();
        api.setContext(null);
        storeContext(null);
        storeSupport(null);
        storePrivileged(null);
        setUser(null);
        setLoading(false);
        setBusy(false);
    }, [api]);
    const restore = useCallback(async () => {
        const current = generation.current;
        try {
            const identity = await api.request<Identity>('/auth/me', { contextId: null });
            if (current === generation.current) {
                setUser(identity);
                setError(null);
            }
        }
        catch (e) {
            if (!isAbort(e) && !(e instanceof ApiError && e.status === 401))
                setError(e);
        }
        finally {
            if (current === generation.current)
                setLoading(false);
        }
    }, [api]);
    const cancelRestore = useCallback(() => {
        generation.current++;
        api.cancelAll();
    }, [api]);
    useEffect(() => api.handleUnauthorized(clear), [api, clear]);
    useEffect(() => {
        // Synchronize session state with the server on mount.
        // eslint-disable-next-line react/set-state-in-effect
        void restore();
        const refresh = () => { if (!locked.current && document.visibilityState !== 'hidden')
            void restore(); };
        window.addEventListener('focus', refresh);
        // Recheck on activity; polling would prevent server idle expiry.
        return () => { cancelRestore(); window.removeEventListener('focus', refresh); };
    }, [cancelRestore, restore]);
    async function login(email: string, password: string) {
        if (locked.current)
            return;
        locked.current = true;
        setBusy(true);
        setError(null);
        api.cancelAll();
        try {
            await api.request('/auth/login', { method: 'POST', body: { email, password }, contextId: null });
            const identity = await api.request<Identity>('/auth/me', { contextId: null });
            storeContext(null);
        storeSupport(null);
        storePrivileged(null);
            api.setContext(null);
            setUser(identity);
        }
        finally {
            locked.current = false;
            setBusy(false);
        }
    }
    async function logout() {
        if (locked.current)
            return;
        locked.current = true;
        setBusy(true);
        setError(null);
        api.cancelAll();
        try {
            await api.request('/auth/logout', { method: 'POST', contextId: null });
            clear();
        }
        catch (e) {
            if (!isAbort(e) && !(e instanceof ApiError && e.status === 401))
                setError(e);
        }
        finally {
            locked.current = false;
            setBusy(false);
        }
    }
    return <AuthContext.Provider value={{ api, user, loading, busy, error, login, logout, retry: () => void restore() }}>{children}</AuthContext.Provider>;
}
