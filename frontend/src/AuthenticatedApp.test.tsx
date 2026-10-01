import { cleanup, fireEvent, render, screen, waitFor, within } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from './App';
const key = 'hiatlas.access-context.v1';
let logged = false, role = 'PLATFORM_ADMIN', invalid = false;
const calls: {
    path: string;
    init: RequestInit;
}[] = [];
const contract = { id: 'contract-a', tenant_id: 'tenant-a', tenant_name: 'GDSUL', name: 'Principal', code: 'CTR-2026-001', environment: 'PRODUCTION' };
function response(data: unknown, status = 200) { return new Response(JSON.stringify(data), { status }); }
beforeEach(() => {
    logged = false;
    role = 'PLATFORM_ADMIN';
    invalid = false;
    calls.length = 0;
    sessionStorage.clear();
    localStorage.clear();
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
        const path = url.replace('/api', '');
        calls.push({ path, init });
        if (path === '/auth/csrf')
            return response({ token: 'csrf' });
        if (path === '/auth/login') {
            logged = true;
            return response({});
        }
        if (path === '/auth/logout') {
            logged = false;
            return new Response(null, { status: 204 });
        }
        if (!logged)
            return response({ code: 'SESSION_INVALID' }, 401);
        if (path === '/auth/me')
            return response({ user_id: 'user', display_name: 'Junior', platform_role: role, capabilities: [] });
        if (path.startsWith('/contracts'))
            return response({ items: [contract] });
        if (path === '/contexts')
            return response({ id: 'opaque-a' }, 201);
        if (path.startsWith('/contexts/'))
            return new Response(null, { status: 204 });
        if (path === '/context')
            return invalid ? response({ code: 'CONTEXT_INVALID' }, 403) : response({ id: 'opaque-a', tenant_name: 'GDSUL', contract_id: 'contract-a', contract_code: 'CTR-2026-001', environment: 'PRODUCTION', expires_at: '2099-01-01T00:00:00Z' });
        return response({}, 404);
    }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
async function login() {
    await screen.findByLabelText('E-mail');
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'internal@example.test' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'entered-password' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar no HiAtlas' }));
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
}
async function select() { fireEvent.click(await screen.findByRole('button', { name: 'Acessar contrato CTR-2026-001' })); await screen.findByTestId('contract-context'); }
it('real login has no role selector and loads identity through me', async () => {
    render(<App />);
    await login();
    expect(screen.queryByLabelText(/perfil/i)).not.toBeInTheDocument();
    const paths = calls.map(c => c.path);
    expect(paths.slice(paths.indexOf('/auth/login'), paths.indexOf('/auth/login') + 2)).toEqual(['/auth/login', '/auth/me']);
    expect(screen.getByText('Bem-vindo, Junior')).toBeInTheDocument();
});
it('invalid credentials have a neutral error without raw server details', async () => {
    const original = fetch;
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/auth/login') ? Promise.resolve(response({ message: 'email exists password hash SECRET', request_id: 'support-123' }, 401)) : original(url, init)));
    render(<App />);
    await screen.findByLabelText('E-mail');
    fireEvent.change(screen.getByLabelText('E-mail'), { target: { value: 'a@b.test' } });
    fireEvent.change(screen.getByLabelText('Senha'), { target: { value: 'invalid' } });
    fireEvent.click(screen.getByRole('button', { name: 'Entrar no HiAtlas' }));
    expect(await screen.findByRole('alert')).toHaveTextContent('E-mail ou senha inválidos.');
    expect(screen.getByRole('alert')).not.toHaveTextContent('SECRET');
});
it.each(['PLATFORM_ADMIN', 'PLATFORM_SUPPORT'])('restores %s session into picker then corresponding portal', async (value) => {
    logged = true;
    role = value;
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    await select();
    expect(screen.getByRole('heading', { name: value === 'PLATFORM_ADMIN' ? 'Administração HiAtlas' : 'Suporte HiAtlas' })).toBeInTheDocument();
    const header = screen.getByTestId('contract-context');
    for (const text of ['GDSUL', 'CTR-2026-001', 'Produção'])
        expect(within(header).getByText(text)).toBeInTheDocument();
    expect(calls.find(c => c.path === '/contexts')?.init.body).toBe(JSON.stringify({ contract_id: 'contract-a' }));
    expect(new Headers(calls.find(c => c.path === '/context')?.init.headers).get('X-HiAtlas-Context')).toBe('opaque-a');
    expect(sessionStorage.getItem(key)).toBe('opaque-a');
    expect(localStorage.getItem(key)).toBeNull();
});
it('revalidates persisted context before rendering on reload', async () => {
    logged = true;
    sessionStorage.setItem(key, 'opaque-a');
    render(<App />);
    expect(screen.queryByTestId('contract-context')).not.toBeInTheDocument();
    await screen.findByTestId('contract-context');
    expect(calls.some(c => c.path === '/context')).toBe(true);
});
it('invalid persisted context returns to selection', async () => {
    logged = true;
    invalid = true;
    sessionStorage.setItem(key, 'opaque-a');
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    expect(sessionStorage.getItem(key)).toBeNull();
});
it('401 clears persisted context and shows login', async () => {
    sessionStorage.setItem(key, 'old');
    render(<App />);
    await screen.findByLabelText('E-mail');
    expect(sessionStorage.getItem(key)).toBeNull();
});
it('logout calls the server with CSRF then clears session and context', async () => {
    logged = true;
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    await select();
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    await screen.findByLabelText('E-mail');
    expect(calls.some(c => c.path === '/auth/logout' && c.init.method === 'POST')).toBe(true);
    expect(sessionStorage.getItem(key)).toBeNull();
});
it('switching closes the current context on server and returns to selection', async () => {
    logged = true;
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    await select();
    fireEvent.click(screen.getByRole('button', { name: 'Trocar empresa/contrato' }));
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    expect(calls.some(c => c.path === '/contexts/opaque-a' && c.init.method === 'DELETE')).toBe(true);
    expect(sessionStorage.getItem(key)).toBeNull();
});
it('local role and demo URL cannot bypass the real session', async () => {
    localStorage.setItem('platform_role', 'PLATFORM_ADMIN');
    history.replaceState(null, '', '/?demo=1');
    render(<App />);
    await screen.findByLabelText('E-mail');
    expect(screen.queryByLabelText(/perfil de acesso/i)).not.toBeInTheDocument();
    await waitFor(() => expect(screen.queryByText('GDSUL')).not.toBeInTheDocument());
    history.replaceState(null, '', '/');
});
it('keeps the session when server logout fails instead of claiming success', async () => {
    logged = true;
    const original = fetch;
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.endsWith('/auth/logout') ? Promise.resolve(response({}, 503)) : original(url, init)));
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    await select();
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    await screen.findByText(/Serviço temporariamente indisponível/);
    expect(screen.getByTestId('contract-context')).toBeInTheDocument();
    expect(sessionStorage.getItem(key)).toBe('opaque-a');
});
it('does not silently switch after failed CSRF validation on close', async () => {
    logged = true;
    const original = fetch;
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.includes('/contexts/') ? Promise.resolve(response({ code: 'CSRF_INVALID' }, 403)) : original(url, init)));
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    await select();
    fireEvent.click(screen.getByRole('button', { name: 'Trocar empresa/contrato' }));
    await screen.findByRole('alert');
    expect(screen.getByTestId('contract-context')).toBeInTheDocument();
    expect(sessionStorage.getItem(key)).toBe('opaque-a');
});
it('401 while working clears the authenticated UI and tab context', async () => {
    logged = true;
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    await select();
    logged = false;
    fireEvent(window, new Event('focus'));
    await screen.findByLabelText('E-mail');
    expect(screen.queryByTestId('contract-context')).not.toBeInTheDocument();
    expect(sessionStorage.getItem(key)).toBeNull();
});
it('a delayed A validation cannot populate B after switching', async () => {
    logged = true;
    const original = fetch;
    let delay = false, resolveA: ((response: Response) => void) | undefined, delayedSignal: AbortSignal | undefined;
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
        if (url.includes('/contracts?'))
            return Promise.resolve(response({ items: [contract, { ...contract, id: 'contract-b', code: 'CTR-B', tenant_name: 'Empresa B' }] }));
        if (url === '/api/contexts' && String(init?.body).includes('contract-b'))
            return Promise.resolve(response({ id: 'opaque-b' }, 201));
        if (url === '/api/context' && new Headers(init?.headers).get('X-HiAtlas-Context') === 'opaque-b')
            return Promise.resolve(response({ id: 'opaque-b', tenant_name: 'Empresa B', contract_id: 'contract-b', contract_code: 'CTR-B', environment: 'TEST', expires_at: '2099-01-01T00:00:00Z' }));
        if (url === '/api/context' && delay) {
            delay = false;
            delayedSignal = init?.signal ?? undefined;
            return new Promise<Response>(resolve => { resolveA = resolve; });
        }
        return original(url, init);
    }));
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    await select();
    delay = true;
    fireEvent(window, new Event('focus'));
    await waitFor(() => expect(resolveA).toBeDefined());
    fireEvent.click(screen.getByRole('button', { name: 'Trocar empresa/contrato' }));
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    expect(delayedSignal?.aborted).toBe(true);
    fireEvent.click(await screen.findByRole('button', { name: 'Acessar contrato CTR-B' }));
    await screen.findByTestId('contract-context');
    resolveA!(response({ id: 'opaque-a', tenant_name: 'Detalhe exclusivo A', contract_code: 'CTR-A', environment: 'TEST' }));
    await waitFor(() => expect(screen.getByTestId('contract-context')).toHaveTextContent('Empresa B'));
    expect(screen.queryByText('Detalhe exclusivo A')).not.toBeInTheDocument();
});
it('malformed persisted context returns to selection after server rejection', async () => {
    logged = true;
    sessionStorage.setItem(key, 'malformed');
    const original = fetch;
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url === '/api/context' ? Promise.resolve(response({ code: 'CONTEXT_REQUIRED' }, 403)) : original(url, init)));
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    expect(sessionStorage.getItem(key)).toBeNull();
});
it('failed logout during context validation resumes that validation', async () => {
    logged = true;
    const original = fetch;
    let hold = true, started = false;
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => {
        if (url === '/api/context' && hold) {
            started = true;
            return new Promise<Response>((_resolve, reject) => init?.signal?.addEventListener('abort', () => reject(new DOMException('aborted', 'AbortError'))));
        }
        if (url === '/api/auth/logout') {
            hold = false;
            return Promise.resolve(response({}, 503));
        }
        return original(url, init);
    }));
    render(<App />);
    await screen.findByRole('heading', { name: 'Selecionar ambiente' });
    fireEvent.click(await screen.findByRole('button', { name: 'Acessar contrato CTR-2026-001' }));
    await waitFor(() => expect(started).toBe(true));
    expect(screen.getByRole('status')).toHaveTextContent('Validando contexto');
    fireEvent.click(screen.getByRole('button', { name: 'Sair' }));
    await screen.findByText(/Serviço temporariamente indisponível/);
    expect(await screen.findByTestId('contract-context')).toHaveTextContent('CTR-2026-001');
});
it('successful contract retry clears its old error and displays the empty state', async () => {
    logged = true;
    const original = fetch;
    let fail = true;
    vi.stubGlobal('fetch', vi.fn((url: string, init?: RequestInit) => url.includes('/contracts?') ? Promise.resolve(fail ? response({}, 503) : response({ items: [] })) : original(url, init)));
    render(<App />);
    await screen.findByRole('alert');
    fail = false;
    fireEvent.click(screen.getByRole('button', { name: 'Tentar novamente' }));
    await screen.findByText('Nenhum contrato disponível para esta pesquisa.');
    expect(screen.queryByRole('alert')).not.toBeInTheDocument();
});
it('StrictMode does not show login while the live session restoration is pending', async () => {
    const {StrictMode}=await import('react');
    sessionStorage.setItem(key,'opaque-a');
    let resolveLive: ((value:Response)=>void)|undefined;
    let requests=0;
    vi.stubGlobal('fetch',vi.fn((_url:string,init?:RequestInit)=>new Promise<Response>((resolve,reject)=>{
        requests++;resolveLive=resolve;
        init?.signal?.addEventListener('abort',()=>reject(new DOMException('aborted','AbortError')));
    })));
    render(<StrictMode><App/></StrictMode>);
    await waitFor(()=>expect(requests).toBe(2));
    expect(screen.queryByLabelText('E-mail')).not.toBeInTheDocument();
    expect(screen.getByRole('status')).toHaveTextContent('Verificando sessão');
    resolveLive!(response({code:'SESSION_INVALID'},401));
    await screen.findByLabelText('E-mail');
    expect(sessionStorage.getItem(key)).toBeNull();
});
const phase6Member={id:'member-a',user_id:'customer',display_name:'Cliente real',email:'customer@example.test',role_id:'buyer',role_name:'Comprador Nacional',active:true,blocked:false,invitation_pending:false,invitation_status:null,version:1,allowed_actions:['block'],last_access_at:null};
function installPhase6Endpoints(failureStatus:number,failureCode:string){const original=fetch;vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>{
 if(url==='/api/context')return Promise.resolve(response({id:'opaque-a',tenant_name:'GDSUL',contract_id:'contract-a',contract_code:'CTR-2026-001',environment:'PRODUCTION',expires_at:'2099-01-01T00:00:00Z',capabilities:['memberships.read','users.status']}));
 if(url.startsWith('/api/memberships?'))return Promise.resolve(response({items:[phase6Member],total:1,limit:20,offset:0}));
 if(url==='/api/memberships/member-a')return Promise.resolve(response(phase6Member));
 if(url==='/api/memberships/member-a/status')return Promise.resolve(response({code:failureCode},failureStatus));
 return original(url,init);
}));}
it('Phase6 mutation 401 removes dialog and contextual records through the session handler',async()=>{logged=true;installPhase6Endpoints(401,'SESSION_INVALID');render(<App/>);await screen.findByRole('heading',{name:'Selecionar ambiente'});await select();fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Cliente real'}));fireEvent.click(await screen.findByRole('button',{name:'Bloquear acesso'}));fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'}));await screen.findByLabelText('E-mail');expect(screen.queryByRole('dialog')).not.toBeInTheDocument();expect(screen.queryByText('Cliente real')).not.toBeInTheDocument();expect(sessionStorage.getItem(key)).toBeNull();});
it('Phase6 mutation context revocation returns to picker and clears contextual dialogs',async()=>{logged=true;installPhase6Endpoints(403,'CONTEXT_INVALID');render(<App/>);await screen.findByRole('heading',{name:'Selecionar ambiente'});await select();fireEvent.click(await screen.findByRole('button',{name:'Detalhes de Cliente real'}));fireEvent.click(await screen.findByRole('button',{name:'Bloquear acesso'}));fireEvent.click(within(screen.getByRole('dialog')).getByRole('button',{name:'Confirmar'}));await screen.findByRole('heading',{name:'Selecionar ambiente'});expect(screen.queryByRole('dialog')).not.toBeInTheDocument();expect(screen.queryByText('Cliente real')).not.toBeInTheDocument();expect(sessionStorage.getItem(key)).toBeNull();});
