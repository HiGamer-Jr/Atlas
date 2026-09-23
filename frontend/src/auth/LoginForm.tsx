import { useState, type FormEvent } from 'react';
import ErrorNotice from '../api/ErrorNotice';
import { ApiError, isAbort } from '../api/errors';
export default function LoginForm({ onLogin }: {
    onLogin: (email: string, password: string) => Promise<void>;
}) {
    const [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(null);
    const invalid = error instanceof ApiError && error.status === 422;
    async function submit(event: FormEvent<HTMLFormElement>) {
        event.preventDefault();
        if (busy)
            return;
        const form = event.currentTarget, data = new FormData(form);
        setBusy(true);
        setError(null);
        try {
            await onLogin(String(data.get('email')), String(data.get('password')));
        }
        catch (e) {
            if (!isAbort(e))
                setError(e);
        }
        finally {
            const password = form.elements.namedItem('password') as HTMLInputElement;
            password.value = '';
            setBusy(false);
        }
    }
    return <form className="access-form" onSubmit={submit} aria-busy={busy}>
  <label htmlFor="email">E-mail</label><input id="email" name="email" type="email" autoComplete="username" maxLength={320} aria-invalid={invalid} aria-describedby={invalid ? "login-validation" : undefined} required disabled={busy}/>
  <label htmlFor="password">Senha</label><input id="password" name="password" type="password" autoComplete="current-password" maxLength={1024} aria-invalid={invalid} aria-describedby={invalid ? "login-validation" : undefined} required disabled={busy}/>
  <ErrorNotice error={error}/>{invalid && <p id="login-validation">Confira os campos E-mail e Senha.</p>}<button className="access-submit" disabled={busy} type="submit">{busy ? 'Entrando…' : 'Entrar no HiAtlas'}</button>
 </form>;
}
