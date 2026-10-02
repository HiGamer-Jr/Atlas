import { useCallback, useEffect, useState } from 'react';
import { useAuth } from '../../auth/state';
import { useAccessContext } from '../state';
import { ApiError, isAbort } from '../../api/errors';
export function useScopedQuery<T>(path: string | null) {
    const { api } = useAuth();
    const { selected } = useAccessContext();
    const contextId = selected?.id;
    const [revision, setRevision] = useState(0);
    const request = `${contextId}:${path}`;
    const key = `${request}:${revision}`;
    const [state, setState] = useState<{
        data: T | null;
        error: unknown;
        key: string;
        request: string;
    }>({ data: null, error: null, key: '', request: '' });
    const retry = useCallback(() => setRevision(value => value + 1), []);
    const discardAndRetry = useCallback(() => { setState({ data: null, error: null, key: '', request: '' }); setRevision(value => value + 1); }, []);
    useEffect(() => {
        if (!path || !contextId)
            return;
        const controller = new AbortController();
        api.request<T>(path, { contextId, signal: controller.signal }).then(data => {
            if (!controller.signal.aborted)
                setState({ data, error: null, key, request });
        }).catch(error => {
            if (!isAbort(error) && !controller.signal.aborted)
                setState(previous => ({ data: previous.request === request && !(error instanceof ApiError && [401, 403, 404].includes(error.status)) ? previous.data : null, error, key, request }));
        });
        return () => controller.abort();
    }, [api, path, contextId, key, request]);
    return { data: state.request === request ? state.data : null, error: state.key === key ? state.error : null, loading: !!path && state.key !== key, retry, discardAndRetry };
}
