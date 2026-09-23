export const CONTEXT_KEY = 'hiatlas.access-context.v1';
export function readContext() { try {
    return sessionStorage.getItem(CONTEXT_KEY);
}
catch {
    return null;
} }
export function storeContext(id: string | null) { try {
    if (id)
        sessionStorage.setItem(CONTEXT_KEY, id);
    else
        sessionStorage.removeItem(CONTEXT_KEY);
}
catch { /* Memory-only operation when storage is unavailable. */ } }
