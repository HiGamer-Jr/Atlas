import { useEffect, useState } from 'react';
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
import './LoginScreen.css';
import './platform/Platform.css';
function Portal() {
    const { selected, loading, error, recovering, retry, clear } = useAccessContext();
    if (loading || (recovering && !error && !selected))
        return <p role="status">Validando contexto…</p>;
    return <><ErrorNotice error={error}/>{!!error && recovering && <div className="recovery-actions"><button onClick={retry}>Validar contexto novamente</button><button onClick={() => void clear()}>Encerrar contexto</button></div>}{selected ? <ContractShell /> : !recovering ? <ContractPicker /> : null}</>;
}
function AuthenticatedApp() {
    const { user, loading, error, busy, login, logout, retry } = useAuth();
    const [theme, setTheme] = useState<'light' | 'dark'>(() => { try {
        return localStorage.getItem('hiatlas-theme') === 'dark' ? 'dark' : 'light';
    }
    catch {
        return 'light';
    } });
    useEffect(() => { try {
        localStorage.setItem('hiatlas-theme', theme);
    }
    catch { /* Optional preference only. */ } }, [theme]);
    return <main className={`hiatlas-access real-app ${user ? 'portal' : ''}`} data-theme={theme}>
  <header className="access-top">
   {user && <img className="portal-logo" src={theme === 'light' ? lightLogo : darkLogo} alt="HiAtlas — Supply Chain Intelligence"/>}
   <div className="theme-picker" role="group" aria-label="Aparência"><button aria-label="Tema claro" aria-pressed={theme === 'light'} onClick={() => setTheme('light')}>☼ Claro</button><button aria-label="Tema escuro" aria-pressed={theme === 'dark'} onClick={() => setTheme('dark')}>☾ Escuro</button></div>
   {user && <button disabled={busy} onClick={() => void logout()}>{busy ? 'Saindo…' : 'Sair'}</button>}
  </header>
  <ErrorNotice error={error}/>{!!error && <button onClick={retry}>Tentar novamente</button>}
  {loading ? <p role="status">Verificando sessão…</p> : user ? (user.platform_role === 'PLATFORM_ADMIN' || user.platform_role === 'PLATFORM_SUPPORT' ? <ContextProvider key={user.user_id}><Portal /></ContextProvider> : <section className="portal-content"><h1>Acesso indisponível</h1><p>Este portal está disponível para operadores internos autorizados.</p></section>) : <section className="access-content">
   <img className="hiatlas-logo" src={theme === 'light' ? lightLogo : darkLogo} alt="HiAtlas — Supply Chain Intelligence" width="1254" height="1254"/>
   <div className="access-welcome"><h1>Bem-vindo à HiAtlas</h1><p>Um novo horizonte para o seu negócio</p></div>
   <LoginForm onLogin={login}/><a className="forgot-password" href="/password/forgot">Esqueci minha senha</a>
  </section>}
  <footer className="access-footer">© HiGamer</footer>
 </main>;
}
export default function App() {
    const path = window.location.pathname;
    if (['/password/forgot', '/password/reset', '/invite/accept'].includes(path)) return <AccessLifecycle path={path} />;
    return <AuthProvider><AuthenticatedApp /></AuthProvider>;
}
