import { ApiError } from './errors';
type Options = {
    method?: 'GET' | 'POST' | 'DELETE' | 'PATCH' | 'PUT';
    body?: unknown;
    contextId?: string | null;
    signal?: AbortSignal;
};
/** One instance per mounted app/tab. No authentication credentials are persisted. */
export class ApiClient {
    private context: string | null = null;
    private generation = 0;
    private contextGeneration = 0;
    private pending = new Map<AbortController, boolean>();
    private onUnauthorized: () => void = () => { };
    handleUnauthorized(callback: () => void) { this.onUnauthorized = callback; return () => { if (this.onUnauthorized === callback)
        this.onUnauthorized = () => { }; }; }
    private onContextInvalid: () => void = () => { };
    handleContextInvalid(callback: () => void) { this.onContextInvalid = callback; return () => { if (this.onContextInvalid === callback)
        this.onContextInvalid = () => { }; }; }
    setContext(id: string | null) {
        if (this.context === id)
            return;
        this.cancelContext();
        this.context = id;
    }
    cancelContext() {
        this.contextGeneration++;
        for (const [controller, scoped] of this.pending)
            if (scoped)
                controller.abort();
    }
    cancelAll() {
        this.generation++;
        for (const controller of this.pending.keys())
            controller.abort();
    }
    async request<T>(path: string, options: Options = {}): Promise<T> {
        if (!path.startsWith('/') || path.startsWith('//'))
            throw new Error('Invalid API path');
        const context = options.contextId === undefined ? this.context : options.contextId;
        const epoch = this.generation, scopeEpoch = this.contextGeneration;
        const controller = new AbortController();
        const abort = () => controller.abort();
        options.signal?.addEventListener('abort', abort, { once: true });
        if (options.signal?.aborted)
            abort();
        this.pending.set(controller, !!context);
        const assertCurrent = () => {
            if (controller.signal.aborted || epoch !== this.generation || (context && scopeEpoch !== this.contextGeneration))
                throw new DOMException('Request cancelled', 'AbortError');
        };
        try {
            assertCurrent();
            const method = options.method ?? 'GET';
            const headers = new Headers({ Accept: 'application/json' });
            if (context)
                headers.set('X-HiAtlas-Context', context);
            if (options.body !== undefined)
                headers.set('Content-Type', 'application/json');
            if (method !== 'GET') {
                // Refresh on every mutation: login rotates CSRF and other tabs share the cookie.
                const csrf = await this.request<{
                    token: string;
                }>('/auth/csrf', { contextId: null, signal: controller.signal });
                assertCurrent();
                headers.set('X-CSRF-Token', csrf.token);
            }
            const response = await fetch(`/api${path}`, { method, credentials: 'include', cache: 'no-store', headers, signal: controller.signal, body: options.body === undefined ? undefined : JSON.stringify(options.body) });
            assertCurrent();
            const payload = response.status === 204 ? undefined : await response.json().catch(() => ({}));
            assertCurrent();
            if (!response.ok) {
                const error = new ApiError(response.status, payload && typeof payload === 'object' ? payload : {});
                // A rejected password confirmation does not revoke a valid authenticated session.
                const rejectedReauthentication = path === '/auth/reauthenticate' && error.code === 'AUTH_INVALID';
                if (response.status === 401 && path !== '/auth/login' && !rejectedReauthentication)
                    this.onUnauthorized();
                if (context && error.code === 'CONTEXT_INVALID')
                    this.onContextInvalid();
                if (path === '/auth/login' && response.status === 401)
                    throw new ApiError(401, { ...payload, code: 'AUTH_INVALID' });
                throw error;
            }
            return payload as T;
        }
        finally {
            options.signal?.removeEventListener('abort', abort);
            this.pending.delete(controller);
        }
    }
}
