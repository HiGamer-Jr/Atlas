import { cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, beforeEach, expect, it, vi } from 'vitest';
import App from '../App';
let validation = 200, code = 'TOKEN_EXPIRED', existing = false, target = 'TENANT', inspectionExtra = {}, unavailable = false, rejectPassword = false;
let calls: { path: string; body: Record<string, string> }[];
beforeEach(() => {
 validation = 200; existing = false; target='TENANT'; inspectionExtra={}; unavailable = false; rejectPassword = false; calls = [];
 localStorage.clear(); sessionStorage.clear();
 vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit = {}) => {
  const path = url.replace('/api', ''); const body = JSON.parse(String(init.body || '{}')); calls.push({path, body});
  const reply = (data: unknown, status = 200) => new Response(JSON.stringify(data), {status});
  if (path === '/auth/csrf') return reply({token:'csrf'});
  if (path === '/auth/password-policy') return reply({min_length:12,max_length:1024});
  if (path === '/auth/token/validate') return reply(validation === 200 ? {target_kind:body.purpose==='PASSWORD_RESET'?'USER':target,requires_authentication:existing,...inspectionExtra} : {code}, validation);
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
it('existing identity authenticates own account and accepts without new password',async () => {existing=true;open('/invite/accept#token=private-test-secret');fireEvent.change(await screen.findByLabelText('E-mail'),{target:{value:'recipient@example.test'}});fireEvent.change(screen.getByLabelText('Senha atual'),{target:{value:'existing-password'}});fireEvent.click(screen.getByRole('button',{name:'Autenticar e aceitar convite'}));expect(await screen.findByText('Convite aceito.')).toBeInTheDocument();expect(calls.find(c=>c.path==='/auth/accept-invite')?.body).toEqual({token:'private-test-secret',target_kind:'TENANT'});expect(calls.some(c=>c.path==='/auth/login')).toBe(true);});
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
 const write = vi.spyOn(Storage.prototype,'setItem');open('/password/reset#token=memory-only-test');await password();fireEvent.click(screen.getByRole('button',{name:'Redefinir senha'}));const status=await screen.findByText('Senha redefinida.');await waitFor(()=>expect(status).toHaveFocus());expect(write.mock.calls.every(([key])=>key==='hiatlas-theme')).toBe(true);write.mockRestore();
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

it.each(['PARTNER','INTERNAL','TENANT'])('shows explicit %s invite target and accepts its discriminator',async kind=>{target=kind;open('/invite/accept#token=target-secret');await password();expect(screen.getByText(kind==='PARTNER'?'Convite para parceiro':kind==='INTERNAL'?'Convite para acesso interno':'Convite para organização')).toBeInTheDocument();expect(screen.queryByRole('combobox')).not.toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'Aceitar convite'}));await screen.findByText('Convite aceito.');expect(calls.find(c=>c.path==='/auth/accept-invite')?.body).toEqual({token:'target-secret',target_kind:kind,new_password:'A-long-private-password!'});});
it.each(['UNKNOWN','USER'])('invalid invite target %s blocks password form',async kind=>{target=kind;open('/invite/accept#token=wrong-target');expect(await screen.findByRole('alert')).toHaveTextContent('Link inválido');expect(screen.queryByLabelText('Nova senha')).not.toBeInTheDocument();});
it('authority-bearing inspection blocks acceptance',async()=>{inspectionExtra={capabilities:['approve']};open('/invite/accept#token=extra-authority');expect(await screen.findByRole('alert')).toHaveTextContent('Link inválido');expect(screen.queryByRole('button',{name:'Aceitar convite'})).not.toBeInTheDocument();});

it('swapped invite ignores late inspection and clears credentials',async()=>{const {act}=await import('@testing-library/react');const original=fetch;let finish!:(response:Response)=>void;vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>{const body=JSON.parse(String(init?.body||'{}'));if(url.endsWith('/auth/token/validate')&&body.token==='old-invite')return new Promise<Response>(resolve=>{finish=resolve;});return original(url,init);}));open('/invite/accept#token=old-invite');await waitFor(()=>expect(finish).toBeDefined());target='PARTNER';await act(async()=>{history.replaceState(null,'','/invite/accept#token=new-invite');window.dispatchEvent(new HashChangeEvent('hashchange'));});await password();await act(async()=>finish(new Response(JSON.stringify({target_kind:'INTERNAL',requires_authentication:true}))));expect(screen.getByText('Convite para parceiro')).toBeInTheDocument();expect(screen.queryByLabelText('Senha atual')).not.toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'Aceitar convite'}));await screen.findByText('Convite aceito.');expect(calls.find(c=>c.path==='/auth/accept-invite')?.body.token).toBe('new-invite');});
it('unmount clears password fields retained by browser DOM',async()=>{history.replaceState(null,'','/invite/accept#token=unmount-secret');const view=render(<App/>);await password();const field=screen.getByLabelText('Nova senha') as HTMLInputElement;view.unmount();expect(field.value).toBe('');});

it('late replaced submission cannot clear new invitation credentials',async()=>{const {act}=await import('@testing-library/react');const original=fetch;let finish!:(response:Response)=>void;let acceptCount=0;vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url.endsWith('/auth/accept-invite')?new Promise<Response>(resolve=>{acceptCount++;if(acceptCount===1)finish=resolve;}):original(url,init)));open('/invite/accept#token=old-submission');await password();fireEvent.click(screen.getByRole('button',{name:'Aceitar convite'}));await waitFor(()=>expect(finish).toBeDefined());await act(async()=>{history.replaceState(null,'','/invite/accept#token=new-submission');window.dispatchEvent(new HashChangeEvent('hashchange'));});await password();const field=screen.getByLabelText('Nova senha') as HTMLInputElement;fireEvent.click(screen.getByRole('button',{name:'Aceitar convite'}));await waitFor(()=>expect(acceptCount).toBe(2));await act(async()=>finish(new Response(null,{status:204})));fireEvent.submit(field.form!);await act(async()=>{await new Promise(resolve=>setTimeout(resolve,0));});expect(acceptCount).toBe(2);expect(field.value).toBe('A-long-private-password!');expect(screen.queryByText('Convite aceito.')).not.toBeInTheDocument();});

it.each([204,503])('replaced invite ignores old logout retry completion %s',async status=>{
 const {act}=await import('@testing-library/react');
 const original=fetch;let attempts=0;let finish!:(response:Response)=>void;
 vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>{
  if(url.endsWith('/auth/logout')){attempts++;if(attempts===1)return Promise.resolve(new Response('{}',{status:503}));return new Promise<Response>(resolve=>{finish=resolve;});}
  return original(url,init);
 }));
 open('/invite/accept#token=old-logout');await password();fireEvent.click(screen.getByRole('button',{name:'Aceitar convite'}));
 await screen.findByText('Convite aceito.');fireEvent.click(await screen.findByRole('button',{name:'Encerrar sess\u00e3o'}));await waitFor(()=>expect(finish).toBeDefined());
 target='PARTNER';await act(async()=>{history.replaceState(null,'','/invite/accept#token=new-logout');window.dispatchEvent(new HashChangeEvent('hashchange'));});
 await screen.findByText('Convite para parceiro');expect(screen.queryByRole('button',{name:'Encerrar sess\u00e3o'})).not.toBeInTheDocument();
 await password();await act(async()=>finish(status===204?new Response(null,{status}):new Response('{}',{status})));
 expect(screen.getByLabelText('Nova senha')).toHaveValue('A-long-private-password!');expect(screen.queryByRole('button',{name:'Encerrar sess\u00e3o'})).not.toBeInTheDocument();expect(screen.queryByText('Convite aceito.')).not.toBeInTheDocument();
});
it('current invitation keeps genuine logout retry failure visible',async()=>{
 const original=fetch;vi.stubGlobal('fetch',vi.fn((url:string,init?:RequestInit)=>url.endsWith('/auth/logout')?Promise.resolve(new Response('{}',{status:503})):original(url,init)));
 open('/invite/accept#token=current-logout');await password();fireEvent.click(screen.getByRole('button',{name:'Aceitar convite'}));await screen.findByText('Convite aceito.');fireEvent.click(await screen.findByRole('button',{name:'Encerrar sess\u00e3o'}));await waitFor(()=>expect(calls.filter(c=>c.path==='/auth/csrf').length).toBeGreaterThan(3));expect(screen.getByRole('button',{name:'Encerrar sess\u00e3o'})).toBeInTheDocument();expect(screen.getByRole('alert')).toHaveTextContent('Tente novamente antes de voltar ao login');
});
