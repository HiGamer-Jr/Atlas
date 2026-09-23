import { afterEach, expect, it, vi } from 'vitest';
import { ApiClient } from './client';
afterEach(() => vi.unstubAllGlobals());
it('uses cookies, obtains CSRF and sends only an opaque context header', async () => {
    const fetcher = vi.fn().mockResolvedValueOnce(new Response(JSON.stringify({ token: 'csrf' }))).mockResolvedValueOnce(new Response('{}'));
    vi.stubGlobal('fetch', fetcher);
    const api = new ApiClient();
    api.setContext('opaque');
    await api.request('/example', { method: 'POST', body: { name: 'safe' } });
    expect(fetcher.mock.calls[0][0]).toBe('/api/auth/csrf');
    const options = fetcher.mock.calls[1][1];
    expect(options.credentials).toBe('include');
    expect(options.headers.get('X-CSRF-Token')).toBe('csrf');
    expect(options.headers.get('X-HiAtlas-Context')).toBe('opaque');
    expect(options.headers.has('Authorization')).toBe(false);
});
it('aborts and rejects late results even if the transport ignores abort', async () => {
    let resolve!: (value: Response) => void;
    const fetcher = vi.fn((_url: string, _init: RequestInit) => new Promise<Response>(done => { resolve = done; }));
    vi.stubGlobal('fetch', fetcher);
    const api = new ApiClient();
    api.setContext('A');
    const pending = api.request('/context');
    const assertion = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    api.setContext('B');
    expect(fetcher.mock.calls[0][1].signal?.aborted).toBe(true);
    resolve(new Response(JSON.stringify({ client: 'A' })));
    await assertion;
});
it('isolates two tab clients and their cancellation', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response('{}')));
    const a = new ApiClient(), b = new ApiClient();
    a.setContext('A');
    b.setContext('B');
    a.setContext(null);
    await b.request('/context');
    expect(vi.mocked(fetch).mock.calls[0][1]?.headers).toBeInstanceOf(Headers);
    expect(new Headers(vi.mocked(fetch).mock.calls[0][1]?.headers).get('X-HiAtlas-Context')).toBe('B');
});
it.each([403, 404, 409, 422, 429, 503])('sanitizes HTTP %s and exposes only a safe support code', async (status) => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(new Response(JSON.stringify({ message: 'SECRET stack trace', request_id: 'request-123' }), { status })));
    const api = new ApiClient();
    try {
        await api.request('/example');
        throw new Error('expected failure');
    }
    catch (error) {
        expect(error).toMatchObject({ status, requestId: 'request-123' });
        expect((error as Error).message).not.toContain('SECRET');
    }
});
it('honors caller AbortSignal and does not send an already cancelled request', async () => {
    const fetcher = vi.fn();
    vi.stubGlobal('fetch', fetcher);
    const controller = new AbortController();
    controller.abort();
    await expect(new ApiClient().request('/example', { signal: controller.signal })).rejects.toMatchObject({ name: 'AbortError' });
    expect(fetcher).not.toHaveBeenCalled();
});
it('cancels all pending requests on session invalidation', async () => {
    let resolve!: (value: Response) => void;
    vi.stubGlobal('fetch', vi.fn(() => new Promise<Response>(done => { resolve = done; })));
    const api = new ApiClient(), pending = api.request('/auth/me', { contextId: null });
    const assertion = expect(pending).rejects.toMatchObject({ name: 'AbortError' });
    api.cancelAll();
    resolve(new Response('{}'));
    await assertion;
});
