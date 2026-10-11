import { useEffect, useLayoutEffect, useRef, useState, type FormEvent } from 'react';
import { ApiClient } from '../api/client';
import { ApiError, errorText, isAbort } from '../api/errors';
import { parseTokenInspection } from '../partners/validate';
import type { TokenInspectionDTO } from '../partners/types';
import lightLogo from '../assets/hiatlas-light.png';
import darkLogo from '../assets/hiatlas-dark.png';
import './AccessLifecycle.css';

type Policy = { min_length: number; max_length: number };
const neutral = 'Se houver uma conta elegível para este endereço, enviaremos as instruções de recuperação.';
const invalidLink = 'Link inválido ou já utilizado. Solicite um novo link.';
function failure(error: unknown) {
    if (error instanceof ApiError) {
        if (error.code === 'TOKEN_EXPIRED') return 'Link expirado. Solicite um novo link.';
        if (error.code === 'TOKEN_INVALID') return invalidLink;
        if (error.code === 'INVITE_AUTH_REQUIRED') return 'Entre com a conta destinatária do convite para continuar.';
        if (error.status === 422) return 'A senha não atende aos requisitos informados. Revise e tente novamente.';
        if (error.status === 503) return 'Serviço de e-mail indisponível. Tente novamente mais tarde.';
    }
    return errorText(error);
}

/** Public lifecycle pages have no authenticated portal, analytics or external resources. */
export default function AccessLifecycle({ path }: { path: string }) {
    const forgot = path === '/password/forgot';
    const invite = path === '/invite/accept';
    const [api] = useState(() => new ApiClient());
    // StrictMode may invoke initializers twice; URL clearing belongs in the layout effect.
    const [token, setToken] = useState(() => new URLSearchParams(window.location.hash.slice(1)).get('token') ?? '');
    const [theme, setTheme] = useState<'light' | 'dark'>(() => {
        try { return localStorage.getItem('hiatlas-theme') === 'dark' ? 'dark' : 'light'; }
        catch { return 'light'; }
    });
    const [policy, setPolicy] = useState<Policy | null>(null);
    const [loading, setLoading] = useState(!forgot);
    const [busy, setBusy] = useState(false);
    const [error, setError] = useState('');
    const [terminal, setTerminal] = useState(false);
    const [inspection, setInspection] = useState<TokenInspectionDTO | null>(null);
    const [existing, setExisting] = useState(false);
    const [done, setDone] = useState(false);
    const [logoutPending, setLogoutPending] = useState(false);
    const [validationAttempt, setValidationAttempt] = useState(0);
    const submission = useRef<AbortController | null>(null);
    const formRef = useRef<HTMLFormElement | null>(null);
    const invitationGeneration = useRef(0);
    const logoutRequest = useRef<AbortController | null>(null);
    useLayoutEffect(() => () => {
        invitationGeneration.current++; logoutRequest.current?.abort();
        submission.current?.abort(); api.cancelAll();
        formRef.current?.reset();
    }, [api]);
    const locked = useRef(false);
    const message = useRef<HTMLParagraphElement>(null);
    const initialToken = useRef(token);
    useLayoutEffect(() => {
        // Fragments never reach HTTP access logs. Remove before initiating any requests.
        if (window.location.hash || window.location.search)
            window.history.replaceState(null, '', window.location.pathname);
    }, []);
    useEffect(() => {
        const replaceToken = () => {
            invitationGeneration.current++; logoutRequest.current?.abort();
            submission.current?.abort(); api.cancelAll(); formRef.current?.reset();
            const next = new URLSearchParams(window.location.hash.slice(1)).get('token') ?? '';
            window.history.replaceState(null, '', window.location.pathname);
            initialToken.current = next; setToken(next); setInspection(null); setPolicy(null);
            setExisting(false); setDone(false); setTerminal(false); setError(''); setBusy(false); setLogoutPending(false);
            locked.current = false; setLoading(!forgot); setValidationAttempt(value => value + 1);
        };
        window.addEventListener('hashchange', replaceToken);
        return () => window.removeEventListener('hashchange', replaceToken);
    }, [api, forgot]);
    useEffect(() => {
        try { localStorage.setItem('hiatlas-theme', theme); }
        catch { /* Theme is optional; credentials never use storage. */ }
    }, [theme]);
    useEffect(() => {
        if (forgot) return;
        const controller = new AbortController();
        async function validate() {
            if (!initialToken.current) {
                setError(invalidLink); setTerminal(true); setLoading(false); return;
            }
            try {
                const wire = await api.request<unknown>('/auth/token/validate', {
                    method: 'POST', body: { token: initialToken.current, purpose: invite ? 'INVITE' : 'PASSWORD_RESET' }, contextId: null, signal: controller.signal,
                });
                if (controller.signal.aborted) return;
                const result = parseTokenInspection(wire, invite);
                if (!result) { setError(invalidLink); setTerminal(true); setToken(''); initialToken.current = ''; return; }
                setInspection(result);
                setExisting(invite && result.requires_authentication);
                const requirements = await api.request<Policy>('/auth/password-policy', { contextId: null, signal: controller.signal });
                if (!controller.signal.aborted) setPolicy(requirements);
            } catch (cause) {
                if (!controller.signal.aborted && !isAbort(cause)) {
                    setError(failure(cause));
                    if (cause instanceof ApiError && ['TOKEN_INVALID', 'TOKEN_EXPIRED'].includes(cause.code)) {
                        setTerminal(true); setToken(''); initialToken.current = '';
                    }
                }
            } finally { if (!controller.signal.aborted) setLoading(false); }
        }
        void validate();
        return () => controller.abort();
    }, [api, forgot, invite, validationAttempt]);
    useEffect(() => { if (error || done) message.current?.focus(); }, [error, done]);
    useEffect(() => {
        if (!done || forgot || logoutPending) return;
        const timer = window.setTimeout(() => window.location.replace('/'), 5000);
        return () => window.clearTimeout(timer);
    }, [done, forgot, logoutPending]);
    async function endSession(signal?: AbortSignal) {
        if (signal?.aborted) return;
        const generation = invitationGeneration.current;
        logoutRequest.current?.abort();
        const controller = new AbortController();
        logoutRequest.current = controller;
        const abort = () => controller.abort();
        signal?.addEventListener('abort', abort, { once: true });
        const current = () => !controller.signal.aborted && generation === invitationGeneration.current && logoutRequest.current === controller;
        api.cancelAll(); formRef.current?.reset();
        try {
            await api.request('/auth/logout', { method: 'POST', contextId: null, signal: controller.signal });
            if (current()) setLogoutPending(false);
        } catch (cause) {
            if (current() && !isAbort(cause)) setLogoutPending(!(cause instanceof ApiError && cause.status === 401));
        } finally {
            signal?.removeEventListener('abort', abort);
            if (logoutRequest.current === controller) logoutRequest.current = null;
        }
    }
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (locked.current || (!forgot && (loading || terminal || !policy || !inspection))) return;
        const form = event.currentTarget;
        const data = new FormData(form);
        if (!forgot && !existing && data.get('password') !== data.get('confirmation')) {
            setError('As senhas não coincidem.'); return;
        }
        locked.current = true; setBusy(true); setError('');
        const controller = new AbortController(); submission.current = controller;
        let authenticatedForInvite = false;
        try {
            if (forgot) {
                await api.request('/auth/recovery', { method: 'POST', body: { email: String(data.get('email')) }, contextId: null, signal: controller.signal });
            } else {
                if (existing) {
                    // Fresh authentication proves recipient identity and satisfies reauthentication.
                    await api.request('/auth/login', { method: 'POST', body: { email: String(data.get('email')), password: String(data.get('current-password')) }, contextId: null, signal: controller.signal });
                    authenticatedForInvite = true;
                }
                await api.request(invite ? '/auth/accept-invite' : '/auth/reset-password', {
                    method: 'POST', body: { token, ...(invite ? { target_kind: inspection!.target_kind } : {}), ...(!existing ? { new_password: String(data.get('password')) } : {}) }, contextId: null, signal: controller.signal,
                });
                if (controller.signal.aborted) return;
                setToken(''); initialToken.current = '';
                await endSession(controller.signal);
            }
            if (!controller.signal.aborted) { form.reset(); setDone(true); }
        } catch (cause) {
            if (!controller.signal.aborted && !isAbort(cause)) {
                if (authenticatedForInvite) await endSession(controller.signal);
                if (controller.signal.aborted) return;
                setError(failure(cause));
                if (cause instanceof ApiError && ['TOKEN_INVALID', 'TOKEN_EXPIRED'].includes(cause.code)) {
                    setTerminal(true); setToken(''); initialToken.current = '';
                }
            }
        } finally {
            for (const name of ['password', 'confirmation', 'current-password']) {
                const field = form.elements.namedItem(name);
                if (submission.current === controller && field instanceof HTMLInputElement) field.value = '';
                data.delete(name);
            }
            if (submission.current === controller) {
                locked.current = false;
                if (!controller.signal.aborted) setBusy(false);
            }
        }
    }
    const title = forgot ? 'Recuperar acesso' : invite ? 'Aceitar convite' : 'Redefinir senha';
    return <main className="hiatlas-access lifecycle-page" data-theme={theme}>
        <header className="access-top"><div className="theme-picker" role="group" aria-label="Aparência">
            <button aria-label="Tema claro" aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>☼ Claro</button>
            <button aria-label="Tema escuro" aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>☾ Escuro</button>
        </div></header>
        <section className="access-content" aria-labelledby="lifecycle-title">
            <img className="hiatlas-logo" src={theme === 'light' ? lightLogo : darkLogo} alt="HiAtlas — Supply Chain Intelligence" width="1254" height="1254" />
            <div className="access-welcome"><h1 id="lifecycle-title">{title}</h1></div>
            {invite && inspection && !terminal && <p>{inspection.target_kind === 'PARTNER' ? 'Convite para parceiro' : inspection.target_kind === 'INTERNAL' ? 'Convite para acesso interno' : 'Convite para organização'}</p>}
            {loading && <p role="status">Validando link…</p>}
            {error && <p ref={message} tabIndex={-1} id="access-error" role="alert">{error}</p>}
            {!loading && !terminal && !forgot && !policy && <button onClick={() => { setLoading(true); setError(''); setValidationAttempt(value => value + 1); }}>Tentar novamente</button>}
            {logoutPending && <><p role="alert">Não foi possível encerrar a sessão. Tente novamente antes de voltar ao login.</p><button onClick={() => void endSession()}>Encerrar sessão</button></>}
            {done ? <><p ref={message} tabIndex={-1} role="status">{forgot ? neutral : invite ? 'Convite aceito.' : 'Senha redefinida.'}</p>
                {!forgot && <p>Entre novamente para acessar sua conta.</p>}
            </> : !loading && !terminal && (forgot || policy) && !logoutPending && <form ref={formRef} className="access-form" onSubmit={submit} aria-busy={busy}>
                {(forgot || existing) && <>
                    {existing && <p>Confirme sua identidade com a conta que recebeu o convite. Sua senha atual será preservada.</p>}
                    <label htmlFor="recovery-email">E-mail</label><input id="recovery-email" name="email" type="email" autoComplete="username" maxLength={320} required disabled={busy} aria-describedby={error ? 'access-error' : undefined} />
                </>}
                {existing && <><label htmlFor="current-password">Senha atual</label><input id="current-password" name="current-password" type="password" autoComplete="current-password" required disabled={busy} aria-describedby={error ? 'access-error' : undefined} /></>}
                {!forgot && !existing && policy && <>
                    <p id="password-policy">Use de {policy.min_length} a {policy.max_length} caracteres. Prefira uma frase longa e exclusiva.</p>
                    <label htmlFor="new-password">Nova senha</label><input id="new-password" name="password" type="password" autoComplete="new-password" required disabled={busy} aria-invalid={!!error} aria-describedby={`password-policy${error ? ' access-error' : ''}`} />
                    <label htmlFor="confirm-password">Confirmar nova senha</label><input id="confirm-password" name="confirmation" type="password" autoComplete="new-password" required disabled={busy} aria-invalid={!!error} aria-describedby={`password-policy${error ? ' access-error' : ''}`} />
                </>}
                <button type="submit" className="access-submit" disabled={busy || (!forgot && !policy)}>{busy ? 'Processando…' : forgot ? 'Solicitar recuperação' : existing ? 'Autenticar e aceitar convite' : title}</button>
            </form>}
            {!logoutPending && <a className="forgot-password" href="/">Voltar ao login</a>}
            {terminal && !invite && <a className="forgot-password" href="/password/forgot">Solicitar novo link</a>}
        </section>
        <footer className="access-footer">© HiGamer</footer>
    </main>;
}
