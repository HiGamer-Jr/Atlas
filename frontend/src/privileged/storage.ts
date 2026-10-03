const KEY = 'hiatlas.privileged-context.v1';
export function readPrivileged() { try {
    return sessionStorage.getItem(KEY);
}
catch {
    return null;
} }
export function storePrivileged(id: string | null) { try {
    if (id)
        sessionStorage.setItem(KEY, id);
    else
        sessionStorage.removeItem(KEY);
}
catch { /* Memory remains authoritative only after server validation. */ } }
