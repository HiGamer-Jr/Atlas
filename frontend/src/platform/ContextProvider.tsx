import { useCallback, useEffect, useRef, useState, type ReactNode } from 'react';
import { useAuth } from '../auth/state';
import { ApiError, isAbort } from '../api/errors';
import { readContext, storeContext } from './storage';
import { readPrivileged, storePrivileged } from '../privileged/storage';
import { readSupport, storeSupport } from '../support/storage';
import { Context, type AccessContext } from './state';
export function ContextProvider({ children }: {
    children: ReactNode;
}) {
    const { api, busy: authBusy } = useAuth();
    const [selected, setSelected] = useState<AccessContext | null>(null);
    const [loading, setLoading] = useState(() => !!readContext()), [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(null);
    const [recovering, setRecovering] = useState(() => !!readContext());
    const [notice,setNotice]=useState<string|null>(null);
    const privilegedReference = useRef<string|null>(null);
    const registerPrivileged = useCallback((id:string|null)=>{privilegedReference.current=id;},[]);
    const supportReference = useRef<string|null>(null);
    const registerSupport = useCallback((id:string|null)=>{supportReference.current=id;},[]);
    const generation = useRef(0), locked = useRef(false), active = useRef<string | null>(null);
    const forget = useCallback((message?: string) => {
        const supportId = supportReference.current ?? readSupport();
        const privilegedId = privilegedReference.current ?? readPrivileged();
        const wasActive = active.current !== null;
        const terminal = message ?? (supportId ? 'Sessão de suporte encerrada, expirada ou indisponível. Selecione um ambiente para continuar.' : privilegedId ? 'Acesso temporário encerrado, expirado ou revogado. Selecione um ambiente para continuar.' : null);
        setNotice(previous => terminal ?? (wasActive ? null : previous));
        supportReference.current = null;
        privilegedReference.current = null;
        generation.current++;
        api.setContext(null);
        active.current = null;
        storeContext(null);
        storeSupport(null);
        storePrivileged(null);
        setSelected(null);
        setLoading(false);
        setRecovering(false);
        setError(null);
    }, [api]);
    useEffect(() => api.handleContextInvalid(forget), [api, forget]);
    const validate = useCallback(async (id: string, signal?: AbortSignal) => {
        const current = generation.current;
        const result = await api.request<AccessContext>('/context', { contextId: id, signal });
        if (current !== generation.current)
            return;
        if (result.id !== id || !result.tenant_name || !result.contract_code || !result.environment || !Number.isFinite(Date.parse(result.expires_at)))
            throw new ApiError(503);
        active.current = id;
        if (result.support_session_id) supportReference.current=result.support_session_id;
        if (result.privileged_context_id) privilegedReference.current=result.privileged_context_id;
        api.setContext(id);
        storeContext(id);
        setSelected(previous => JSON.stringify(previous) === JSON.stringify(result) ? previous : result);
        setError(null);
        setRecovering(false);
    }, [api]);
    const restore = useCallback(async (signal?: AbortSignal) => {
        const id = active.current ?? readContext();
        if (!id)
            return;
        const current = generation.current;
        try {
            await validate(id, signal);
        }
        catch (e) {
            if (e instanceof ApiError && (e.status === 404 || ['CONTEXT_INVALID', 'CONTEXT_REQUIRED'].includes(e.code)))
                forget();
            else if (!isAbort(e))
                setError(e);
        }
        finally {
            if (current === generation.current)
                setLoading(false);
        }
    }, [validate, forget]);
    useEffect(() => {
        if (authBusy)
            return;
        const controller = new AbortController();
        // Revalidate persisted context against the server before displaying it.
        // eslint-disable-next-line react/set-state-in-effect
        void restore(controller.signal);
        return () => { controller.abort(); api.setContext(null); };
    }, [api, restore, authBusy]);
    useEffect(() => {
        if (!selected)
            return;
        const controller = new AbortController();
        const verify = async () => {
            if (locked.current || controller.signal.aborted)
                return;
            try {
                await validate(selected.id, controller.signal);
            }
            catch (e) {
                if (!isAbort(e) && !(e instanceof ApiError && [401, 403, 404].includes(e.status)))
                    setError(e);
                else if (e instanceof ApiError && [403, 404].includes(e.status))
                    forget();
            }
        };
        const onFocus = () => { void verify(); };
        const remaining = Date.parse(selected.expires_at) - Date.now();
        const expiry = window.setTimeout(() => {
            const supportId = supportReference.current ?? selected.support_session_id ?? readSupport();
            const privilegedId = privilegedReference.current ?? selected.privileged_context_id ?? readPrivileged();
            forget(supportId ? 'Sessão de suporte encerrada, expirada ou indisponível. Selecione um ambiente para continuar.' : privilegedId ? 'Acesso temporário encerrado, expirado ou revogado. Selecione um ambiente para continuar.' : undefined);
            if (privilegedId) void api.request('/grants/context', {contextId:privilegedId}).catch(()=>{});
            if (supportId) void api.request('/support-sessions/' + encodeURIComponent(supportId), { contextId: selected.id }).catch(() => {});
        }, Math.min(Math.max(remaining, 0), 2147483647));
        // Do not poll: polling would renew an otherwise idle server session.
        window.addEventListener('focus', onFocus);
        return () => { controller.abort(); window.clearTimeout(expiry); window.removeEventListener('focus', onFocus); };
    }, [selected, validate, forget, api]);
    async function select(contractId: string) {
        if (locked.current || active.current)
            return;
        locked.current = true;
        setBusy(true);
        setError(null);
        const current = ++generation.current;
        try {
            const result = await api.request<{
                id: string;
            }>('/contexts', { method: 'POST', body: { contract_id: contractId }, contextId: null });
            if (current !== generation.current)
                return;
            // Only the opaque identifier is consumed from creation; details are server-validated.
            active.current = result.id;
            storeContext(result.id);
            setRecovering(true);
            await validate(result.id);
        }
        catch (e) {
            if (e instanceof ApiError && (e.status === 404 || ['CONTEXT_INVALID', 'CONTEXT_REQUIRED'].includes(e.code)))
                forget();
            else if (!isAbort(e))
                setError(e);
        }
        finally {
            locked.current = false;
            setBusy(false);
        }
    }
    async function clear() {
        const id = active.current ?? readContext();
        if (!id || locked.current)
            return;
        locked.current = true;
        setBusy(true);
        setError(null);
        generation.current++;
        api.cancelContext();
        try {
            await api.request(`/contexts/${encodeURIComponent(id)}`, { method: 'DELETE', contextId: id });
            forget();
        }
        catch (e) {
            if (e instanceof ApiError && (e.status === 404 || ['CONTEXT_INVALID', 'CONTEXT_REQUIRED'].includes(e.code)))
                forget();
            else if (!isAbort(e))
                setError(e);
        }
        finally {
            locked.current = false;
            setBusy(false);
        }
    }
    return <Context.Provider value={{ selected, loading, busy, error, recovering, select, clear, notice, registerSupport, registerPrivileged, invalidate: forget, retry: () => void restore() }}>{children}</Context.Provider>;
}
