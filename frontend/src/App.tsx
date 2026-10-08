import { useEffect, useState, type ReactNode } from 'react';
import lightLogo from './assets/hiatlas-light.png';
import darkLogo from './assets/hiatlas-dark.png';
import { AuthProvider } from './auth/AuthProvider';
import { useAuth } from './auth/state';
import LoginForm from './auth/LoginForm';
import AccessLifecycle from './auth/AccessLifecycle';
import { ContextProvider } from './platform/ContextProvider';
import { useAccessContext } from './platform/state';
import ContractPicker from './platform/ContractPicker';
import ContractShell from './platform/ContractShell';
import ErrorNotice from './api/ErrorNotice';
import DeploymentBanner from './deployment/DeploymentBanner';
import Workspace from './workspace/Workspace';
import { profileForTenantRole } from './workspace/customerProfile';
import './LoginScreen.css';
import './platform/Platform.css';

type Theme = 'light' | 'dark';

function Portal() {
    const { selected, loading, error, recovering, retry, clear, notice } = useAccessContext();

    if (loading || (recovering && !error && !selected))
        return <p role="status">Validando contexto…</p>;

    return <>
        {notice && <p role="status">{notice}</p>}
        <ErrorNotice error={error}/>
        {!!error && recovering && <div className="recovery-actions">
            <button onClick={retry}>Validar contexto novamente</button>
            <button onClick={() => void clear()}>Encerrar contexto</button>
        </div>}
        {selected ? <ContractShell /> : !recovering ? <ContractPicker /> : null}
    </>;
}

function AccessShell({
    theme,
    setTheme,
    children,
}: {
    theme: Theme;
    setTheme: (theme: Theme) => void;
    children: ReactNode;
}) {
    const { user, busy, logout } = useAuth();

    return <main className={`hiatlas-access real-app ${user ? 'portal' : ''}`} data-theme={theme}>
        <DeploymentBanner />
        <header className="access-top">
            {user && <img
                className="portal-logo"
                src={theme === 'light' ? lightLogo : darkLogo}
                alt="HiAtlas — Supply Chain Intelligence"
            />}
            <div className="theme-picker" role="group" aria-label="Aparência">
                <button
                    aria-label="Tema claro"
                    aria-pressed={theme === 'light'}
                    onClick={() => setTheme('light')}
                >☀ Claro</button>
                <button
                    aria-label="Tema escuro"
                    aria-pressed={theme === 'dark'}
                    onClick={() => setTheme('dark')}
                >☾ Escuro</button>
            </div>
            {user && <button disabled={busy} onClick={() => void logout()}>
                {busy ? 'Saindo…' : 'Sair'}
            </button>}
        </header>

        {children}

        <footer className="access-footer">© HiGamer</footer>
    </main>;
}

function AuthenticatedPortal({
    theme,
    setTheme,
}: {
    theme: Theme;
    setTheme: (theme: Theme) => void;
}) {
    const { user, error, retry, logout } = useAuth();
    const { selected, clear, busy } = useAccessContext();

    if (selected && user?.platform_role === null) {
        const profile = profileForTenantRole(selected.tenant_role_code);

        if (profile) {
            const workspaceProfile = {
                ...profile,
                name: selected.tenant_role_name || profile.name,
            };

            return <Workspace
                profile={workspaceProfile}
                onLogout={() => void logout()}
            />;
        }

        return <AccessShell theme={theme} setTheme={setTheme}>
            <ErrorNotice error={error}/>
            {!!error && <button onClick={retry}>Tentar novamente</button>}
            <section className="portal-content">
                <h1>Perfil indisponível</h1>
                <p>O perfil associado a este contrato ainda não possui um workspace configurado.</p>
                <button disabled={busy} onClick={() => void clear()}>
                    {busy ? 'Encerrando contexto…' : 'Trocar empresa/contrato'}
                </button>
            </section>
        </AccessShell>;
    }

    return <AccessShell theme={theme} setTheme={setTheme}>
        <ErrorNotice error={error}/>
        {!!error && <button onClick={retry}>Tentar novamente</button>}
        <Portal />
    </AccessShell>;
}

function AuthenticatedApp() {
    const { user, loading, error, login, retry } = useAuth();

    const [theme, setTheme] = useState<Theme>(() => {
        try {
            return localStorage.getItem('hiatlas-theme') === 'dark' ? 'dark' : 'light';
        }
        catch {
            return 'light';
        }
    });

    useEffect(() => {
        try {
            localStorage.setItem('hiatlas-theme', theme);
        }
        catch {
            /* Optional preference only. */
        }
    }, [theme]);

    if (loading) {
        return <AccessShell theme={theme} setTheme={setTheme}>
            <p role="status">Verificando sessão…</p>
        </AccessShell>;
    }

    if (user) {
        return <ContextProvider key={user.user_id}>
            <AuthenticatedPortal theme={theme} setTheme={setTheme}/>
        </ContextProvider>;
    }

    return <AccessShell theme={theme} setTheme={setTheme}>
        <ErrorNotice error={error}/>
        {!!error && <button onClick={retry}>Tentar novamente</button>}
        <section className="access-content">
            <img
                className="hiatlas-logo"
                src={theme === 'light' ? lightLogo : darkLogo}
                alt="HiAtlas — Supply Chain Intelligence"
                width="1254"
                height="1254"
            />
            <div className="access-welcome">
                <h1>Bem-vindo à HiAtlas</h1>
                <p>Um novo horizonte para o seu negócio</p>
            </div>
            <LoginForm onLogin={login}/>
            <a className="forgot-password" href="/password/forgot">Esqueci minha senha</a>
        </section>
    </AccessShell>;
}

export default function App() {
    const path = window.location.pathname;

    if (['/password/forgot', '/password/reset', '/invite/accept'].includes(path))
        return <AccessLifecycle path={path} />;

    return <AuthProvider><AuthenticatedApp /></AuthProvider>;
}
