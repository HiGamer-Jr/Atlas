import { cleanup, fireEvent, render, screen } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
let validation = 200, code = 'TOKEN_EXPIRED', existing = false, unavailable = false, rejectPassword = false;
let calls: { path: string; body: Record<string, string> }[];
beforeEach(() => {
 validation = 200; existing = false; unavailable = false; rejectPassword = false; calls = [];
 localStorage.clear(); sessionStorage.clear();
 vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
  const path = url.replace('/api', ''); const body = JSON.parse(String(init.body || '{}')); calls.push({path, body});
  const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), {status});
  if (path === '/auth/csrf') return reply({token:'csrf'});
  if (path === '/auth/password-policy') return reply({min_length:12,max_length:1024});
  if (path === '/auth/token/validate') return reply(validation === 200 ? {requires_authentication:existing} : {code}, validation);
  if (path === '/auth/recovery') return reply({}, unavailable ? 503 : 202);
  if (path === '/auth/login' || path === '/auth/reauthenticate' || path === '/auth/logout') return new Response(null,{status:204});
  if (path === '/auth/accept-invite' || path === '/auth/reset-password') return rejectPassword ? reply({code:'PASSWORD_INVALID'},422) : new Response(null,{status:204});
  return reply({},401);
 }));
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); history.replaceState(null,'','/'); });
function open(path: string) { history.replaceState(null,'',path); render(<App/>); }
async function password() {
 fireEvent.change(await screen.findByLabelText('Nova senha'),{target:{value:'A-long-private-password!'}});
 fireEvent.change(screen.getByLabelText('Confirmar nova senha'),{target:{value:'A-long-private-password!'}});
}
it('real login links to recovery',async () => {open('/'); expect(await screen.findByRole('link',{name:'Esqueci minha senha'})).toHaveAttribute('href','/password/forgot');});
it.each(['known@example.test','unknown@example.test'])('recovery shows same neutral response for %s', async email => {
 open('/password/forgot'); fireEvent.change(await screen.findByLabelText('E-mail'),{target:{value:email}}); fireEvent.click(screen.getByRole('button',{name:'Solicitar recuperação'}));
 expect(await screen.findByText('Se houver uma conta elegível para este endereço, enviaremos as instruções de recuperação.')).toBeInTheDocument();
});
it('unavailable email never shows sent success',async () => {unavailable=true; open('/password/forgot'); fireEvent.change(await screen.findByLabelText('E-mail'),{target:{value:'a@example.test'}}); fireEvent.click(screen.getByRole('button',{name:'Solicitar recuperação'})); expect(await screen.findByRole('alert')).toHaveTextContent('Serviço de e-mail indisponível');});
it.each([['/invite/accept','Convite aceito.','Aceitar convite'],['/password/reset','Senha redefinida.','Redefinir senha']])('consumes %s without persisting or displaying token',async (path,done,button) => {
 open(path+'#token=private-test-secret'); await password(); expect(location.hash).toBe(''); expect(document.body).not.toHaveTextContent('private-test-secret');
 fireEvent.click(screen.getByRole('button',{name:button})); expect(await screen.findByText(done)).toBeInTheDocument();
 expect(screen.queryByLabelText('Nova senha')).not.toBeInTheDocument(); expect(screen.getByRole('link',{name:'Voltar ao login'})).toHaveAttribute('href','/');
 expect(JSON.stringify(localStorage)).not.toContain('private-test-secret'); expect(JSON.stringify(sessionStorage)).not.toContain('private-test-secret');
});
it.each([['TOKEN_EXPIRED','Link expirado. Solicite um novo link.'],['TOKEN_INVALID','Link inválido ou já utilizado. Solicite um novo link.']])('handles %s', async (value,message) => { validation=400; code=value;open('/password/reset#token=private-test-secret'); expect(await screen.findByRole('alert')).toHaveTextContent(message); expect(screen.queryByLabelText('Nova senha')).not.toBeInTheDocument(); });
it('password confirmation prevents consumption',async () => {open('/password/reset#token=private-test-secret');await password();fireEvent.change(screen.getByLabelText('Confirmar nova senha'),{target:{value:'different'}});fireEvent.click(screen.getByRole('button',{name:'Redefinir senha'}));expect(await screen.findByRole('alert')).toHaveTextContent('As senhas não coincidem.');expect(screen.getByLabelText('Confirmar nova senha')).toHaveAttribute('aria-describedby',expect.stringContaining('access-error'));expect(calls.some(c=>c.path==='/auth/reset-password')).toBe(false);});
it('backend policy rejection is shown safely',async () => {rejectPassword=true;open('/password/reset#token=private-test-secret');await password();fireEvent.click(screen.getByRole('button',{name:'Redefinir senha'}));expect(await screen.findByRole('alert')).toHaveTextContent('A senha não atende aos requisitos');});
it('existing identity authenticates own account and accepts without new password',async () => {existing=true;open('/invite/accept#token=private-test-secret');fireEvent.change(await screen.findByLabelText('E-mail'),{target:{value:'recipient@example.test'}});fireEvent.change(screen.getByLabelText('Senha atual'),{target:{value:'existing-password'}});fireEvent.click(screen.getByRole('button',{name:'Autenticar e aceitar convite'}));expect(await screen.findByText('Convite aceito.')).toBeInTheDocument();expect(calls.find(c=>c.path==='/auth/accept-invite')?.body).toEqual({token:'private-test-secret'});expect(calls.some(c=>c.path==='/auth/login')).toBe(true);});
it('public pages preserve theme controls and official logo',async () => {open('/password/forgot');fireEvent.click(screen.getByRole('button',{name:'Tema escuro'}));expect(screen.getByRole('main')).toHaveAttribute('data-theme','dark');fireEvent.click(screen.getByRole('button',{name:'Tema claro'}));expect(screen.getByRole('main')).toHaveAttribute('data-theme','light');expect(screen.getByRole('img',{name:'HiAtlas — Supply Chain Intelligence'})).toBeInTheDocument();});
it('StrictMode preserves the in-memory token while removing it from URL',async () => {
 const { StrictMode } = await import('react'); history.replaceState(null,'','/password/reset#token=strict-secret'); render(<StrictMode><App/></StrictMode>);
 await screen.findByLabelText('Nova senha'); expect(location.hash).toBe('');
 expect(calls.filter(c=>c.path==='/auth/token/validate').every(c=>c.body.token==='strict-secret')).toBe(true);
});
it('missing token fails closed without validation request',async () => {open('/invite/accept');expect(await screen.findByRole('alert')).toHaveTextContent('Link inválido');expect(calls.some(c=>c.path==='/auth/token/validate')).toBe(false);});
it('allows long passwords without silent truncation and displays server policy',async () => {
 open('/password/reset#token=long-password-test'); await password(); expect(screen.getByText(/Use de 12 a 1024 caracteres/)).toBeInTheDocument();
 const long = 'a'.repeat(1000); fireEvent.change(screen.getByLabelText('Nova senha'),{target:{value:long}});fireEvent.change(screen.getByLabelText('Confirmar nova senha'),{target:{value:long}});
 expect(screen.getByLabelText('Nova senha')).not.toHaveAttribute('maxlength');fireEvent.click(screen.getByRole('button',{name:'Redefinir senha'}));await screen.findByText('Senha redefinida.');expect(calls.find(c=>c.path==='/auth/reset-password')?.body.new_password).toBe(long);
});
it('completion moves keyboard focus to status and never stores secrets',async () => {
 const write = vi.spyOn(Storage.prototype,'setItem');open('/password/reset#token=memory-only-test');await password();fireEvent.click(screen.getByRole('button',{name:'Redefinir senha'}));const status=await screen.findByText('Senha redefinida.');expect(status).toHaveFocus();expect(write.mock.calls.every(([key])=>key==='hiatlas-theme')).toBe(true);write.mockRestore();
});
it.each(['/password/reset','/invite/accept'])('ends unrelated browser session after %s',async path=>{open(path+'#token=browser-session');await password();fireEvent.click(screen.getByRole('button',{name:path.includes('invite')?'Aceitar convite':'Redefinir senha'}));await screen.findByText(path.includes('invite')?'Convite aceito.':'Senha redefinida.');expect(calls.some(c=>c.path==='/auth/logout')).toBe(true);});
it.each(['/auth/token/validate','/auth/password-policy'])('retries transient %s failure with memory token',async endpoint=>{const original=fetch;let failed=false;vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>{if(url.endsWith(endpoint)&&!failed){failed=true;return Promise.resolve(new Response('{}',{status:503}));}return original(url,init);}));open('/password/reset#token=retry-memory');await screen.findByRole('alert');fireEvent.click(screen.getByRole('button',{name:'Tentar novamente'}));await password();fireEvent.click(screen.getByRole('button',{name:'Redefinir senha'}));await screen.findByText('Senha redefinida.');expect(calls.find(c=>c.path==='/auth/reset-password')?.body.token).toBe('retry-memory');});
it('accepts already-ended logout session',async()=>{const original=fetch;vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url.endsWith('/auth/logout')?Promise.resolve(new Response('{}',{status:401})):original(url,init)));existing=true;open('/invite/accept#token=logout-401');fireEvent.change(await screen.findByLabelText('E-mail'),{target:{value:'recipient@example.test'}});fireEvent.change(screen.getByLabelText('Senha atual'),{target:{value:'existing-password'}});fireEvent.click(screen.getByRole('button',{name:'Autenticar e aceitar convite'}));await screen.findByText('Convite aceito.');expect(screen.queryByRole('button',{name:'Encerrar sessão'})).not.toBeInTheDocument();});
it('ends fresh invite login after rejected acceptance',async()=>{const original=fetch;vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url.endsWith('/auth/accept-invite')?Promise.resolve(new Response(JSON.stringify({code:'TOKEN_INVALID'}),{status:400})):original(url,init)));existing=true;open('/invite/accept#token=rejected-invite');fireEvent.change(await screen.findByLabelText('E-mail'),{target:{value:'recipient@example.test'}});fireEvent.change(screen.getByLabelText('Senha atual'),{target:{value:'existing-password'}});fireEvent.click(screen.getByRole('button',{name:'Autenticar e aceitar convite'}));await screen.findByText('Link inválido ou já utilizado. Solicite um novo link.');expect(calls.some(c=>c.path==='/auth/logout')).toBe(true);});
it('unmount during login prevents later invitation consumption',async()=>{
 const {act,waitFor}=await import('@testing-library/react');const original=fetch;let finish:((response:Response)=>void)|undefined;
 vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url.endsWith('/auth/login')?new Promise<Response>(resolve=>{finish=resolve;}):original(url,init)));
 existing=true;history.replaceState(null,'','/invite/accept#token=cancel-invite');const view=render(<App/>);fireEvent.change(await screen.findByLabelText('E-mail'),{target:{value:'recipient@example.test'}});fireEvent.change(screen.getByLabelText('Senha atual'),{target:{value:'existing-password'}});fireEvent.click(screen.getByRole('button',{name:'Autenticar e aceitar convite'}));await waitFor(()=>expect(finish).toBeDefined());view.unmount();await act(async()=>{finish!(new Response(null,{status:204}));await new Promise(resolve=>setTimeout(resolve,0));});expect(calls.some(c=>c.path==='/auth/accept-invite')).toBe(false);
});
