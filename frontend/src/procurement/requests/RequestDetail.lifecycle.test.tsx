import { act, cleanup, fireEvent, render, screen, waitFor } from '@testing-library/react';
import { afterEach, expect, it, vi } from 'vitest';
import { AuthContext, type Auth } from '../../auth/state';
import { Context, type ContextState } from '../../platform/state';
import { OperationalContext } from '../../operational/state';
import { ApiClient } from '../../api/client';
import { scope, request } from './fixtures';
import { RequestDetail } from './RequestDetail';
function event(id: string, text: string, sequence = 1) {
    return { id, sequence, aggregate_version: 1, action: 'procurement.request.note_added',
        actor: { membership_id: 'member', user_id: 'user', display_name: 'Requester' },
        tenant_role_id: 'role', tenant_role_code: 'CUSTOM_BUYER', occurred_at: '2026-10-10T12:00:00Z',
        reason: null, payload: { schema_version: 1, text } };
}
function page(items: unknown[], cursor: string | null = null) { return { items, total: cursor ? 2 : items.length, limit: 50, next_cursor: cursor }; }
function deferred() {
    let resolve!: (response: Response) => void;
    const promise = new Promise<Response>(done => { resolve = done; });
    return { promise, resolve };
}
function response(value: unknown) { return new Response(JSON.stringify(value)); }
function harness() {
    const auth: Auth = { api: new ApiClient(), user: { user_id: 'user', display_name: 'User', platform_role: null }, loading: false, busy: false, error: null, login: async () => { }, logout: async () => { }, retry: () => { } };
    const context: ContextState = { selected: { id: 'ctx', tenant_name: 'Tenant', contract_id: 'contract', contract_code: 'CTR', environment: 'TEST', expires_at: '2099-01-01', capabilities: [] }, loading: false, busy: false, error: null, recovering: false, select: async () => { }, clear: async () => { }, retry: () => { } };
    const allowed = structuredClone(scope);
    if (allowed.actor_kind === 'TENANT')
        allowed.customer_scope.capabilities.push(...['triage', 'approve', 'assign', 'fulfill', 'cancel', 'close', 'comment', 'read_unit'].map(a => 'procurement.requests.' + a));
    return function Harness({ id }: {
        id: string;
    }) { return <AuthContext.Provider value={auth}><Context.Provider value={context}><OperationalContext.Provider value={{ status: 'ready', scope: allowed }}><RequestDetail requestId={id}/></OperationalContext.Provider></Context.Provider></AuthContext.Provider>; };
}
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });
it.each(['candidates', 'action', 'history'])('request A to B aborts pending %s and ignores late private callbacks', async (kind) => {
    const late = deferred();
    let signal: AbortSignal | undefined;
    let started = false;
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
        if (url === '/api/auth/csrf')
            return response({ token: 'csrf' });
        if ((kind === 'candidates' && url.includes('/buyer-candidates')) || (kind === 'action' && init.method === 'POST') || (kind === 'history' && url.includes('cursor='))) {
            started = true;
            signal = init.signal as AbortSignal;
            return late.promise;
        }
        const isB = url.includes('/B');
        if (url.includes('/history'))
            return response(page([event(isB ? 'B-event' : 'A-event', isB ? 'B current history' : 'A initial history')], kind === 'history' && !isB ? 'A-next' : null));
        return response({ ...request(), id: isB ? 'B' : 'A', title: isB ? 'B current request' : 'A old request', status: 'APPROVED' });
    }));
    const Harness = harness(), view = render(<Harness id="A"/>);
    await screen.findByText('A old request');
    fireEvent.change(screen.getByLabelText('Motivo da ação'), { target: { value: 'A private reason' } });
    fireEvent.change(screen.getByLabelText('Comentário'), { target: { value: 'A private comment' } });
    fireEvent.click(screen.getByRole('button', { name: kind === 'candidates' ? 'Consultar compradores elegíveis' : kind === 'action' ? 'Adicionar comentário' : 'Mais histórico' }));
    await waitFor(() => expect(started).toBe(true));
    view.rerender(<Harness id="B"/>);
    await screen.findByText('B current request');
    const aborted = signal?.aborted;
    const value = kind === 'candidates' ? page([{ membership_id: 'stale-buyer', display_name: 'A stale buyer' }]) : kind === 'history' ? page([event('A-late', 'A late history', 2)]) : { ...request(), id: 'A', title: 'A mutation result', status: 'APPROVED', version: 2 };
    await act(async () => { late.resolve(response(value)); await late.promise; });
    expect(screen.getByText('B current request')).toBeInTheDocument();
    expect(screen.getByText('B current history')).toBeInTheDocument();
    expect(screen.queryByText('A stale buyer')).not.toBeInTheDocument();
    expect(screen.queryByText('A late history')).not.toBeInTheDocument();
    expect(screen.getByLabelText('Motivo da ação')).toHaveValue('');
    expect(screen.getByLabelText('Comentário')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Consultar compradores elegíveis' })).toBeEnabled();
    expect(aborted).toBe(true);
});
it.each(['refresh', 'mutation'])('older history pagination cannot overwrite same-request %s', async (kind) => {
    const late = deferred();
    let started = false, signal: AbortSignal | undefined, revision = 1;
    vi.stubGlobal('fetch', vi.fn(async (url: string, init: RequestInit) => {
        if (url === '/api/auth/csrf')
            return response({ token: 'csrf' });
        if (url.includes('cursor=')) {
            started = true;
            signal = init.signal as AbortSignal;
            return late.promise;
        }
        if (init.method === 'POST') {
            revision = 2;
            return response({ ...request(), id: 'A', title: 'A current request', status: 'APPROVED', version: 2 });
        }
        if (url.includes('/history'))
            return response(page([event(revision === 1 ? 'initial' : 'fresh', revision === 1 ? 'Initial history' : 'Fresh history')], revision === 1 ? 'old-page' : null));
        return response({ ...request(), id: 'A', title: 'A current request', status: 'APPROVED', version: revision });
    }));
    const Harness = harness();
    render(<Harness id="A"/>);
    await screen.findByText('Initial history');
    fireEvent.click(screen.getByRole('button', { name: 'Mais histórico' }));
    await waitFor(() => expect(started).toBe(true));
    if (kind === 'refresh') {
        revision = 2;
        fireEvent.click(screen.getByRole('button', { name: 'Atualizar detalhe' }));
    }
    else {
        fireEvent.change(screen.getByLabelText('Comentário'), { target: { value: 'Current intent' } });
        fireEvent.click(screen.getByRole('button', { name: 'Adicionar comentário' }));
    }
    await screen.findByText('Fresh history');
    const aborted = signal?.aborted;
    await act(async () => { late.resolve(response(page([event('stale', 'Old pagination evidence', 2)]))); await late.promise; });
    expect(screen.getByText('Fresh history')).toBeInTheDocument();
    expect(screen.queryByText('Old pagination evidence')).not.toBeInTheDocument();
    expect(screen.queryByText('Initial history')).not.toBeInTheDocument();
    expect(aborted).toBe(true);
});

it('request change resets all fulfillment and private file input state',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url.includes('/history'))return response(page([]));
  const id=url.includes('/B')?'B':'A';
  return response({...request(),id,title:id+' request',status:'IN_FULFILLMENT',buyer:{membership_id:'buyer',display_name:'Eligible buyer'}});
 }));
 const Harness=harness(),view=render(<Harness id="A"/>);
 await screen.findByText('A request');
 fireEvent.change(screen.getByLabelText('Motivo da ação'),{target:{value:'A reason'}});
 fireEvent.change(screen.getByLabelText('Comentário'),{target:{value:'A comment'}});
 fireEvent.change(screen.getByLabelText('Item atendido'),{target:{value:'item'}});
 fireEvent.change(screen.getByLabelText('Quantidade atendida'),{target:{value:'0.000001'}});
 fireEvent.change(screen.getByLabelText('Evidência do atendimento'),{target:{value:'A evidence'}});
 fireEvent.change(screen.getByLabelText('Item do arquivo'),{target:{value:'item'}});
 fireEvent.change(screen.getByLabelText('Arquivo privado'),{target:{files:[new File(['A evidence'],'a.txt',{type:'text/plain'})]}});
 expect(screen.getByRole('button',{name:'Anexar arquivo'})).toBeEnabled();
 view.rerender(<Harness id="B"/>);
 await screen.findByText('B request');
 for(const label of ['Motivo da ação','Comentário','Item atendido','Quantidade atendida','Evidência do atendimento','Item do arquivo'])expect(screen.getByLabelText(label)).toHaveValue('');
 expect(screen.getByLabelText('Arquivo privado')).toHaveValue('');
 expect(screen.getByRole('button',{name:'Anexar arquivo'})).toBeDisabled();
});
it('request change exits old draft editing',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>{
  if(url.includes('/history'))return response(page([]));
  const id=url.includes('/B')?'B':'A';
  return response({...request(),id,title:id+' draft'});
 }));
 const Harness=harness(),view=render(<Harness id="A"/>);
 fireEvent.click(await screen.findByRole('button',{name:'Editar rascunho'}));
 fireEvent.change(screen.getByLabelText('Título'),{target:{value:'A unsaved edit'}});
 view.rerender(<Harness id="B"/>);
 await screen.findByText('B draft');
 expect(screen.queryByLabelText('Título')).not.toBeInTheDocument();
 fireEvent.click(screen.getByRole('button',{name:'Editar rascunho'}));
 expect(screen.getByLabelText('Título')).toHaveValue('B draft');
});

it.each(['refresh','mutation'])('older buyer candidates cannot overwrite same-request %s',async(kind)=>{
 const late=deferred();let signal:AbortSignal|undefined,queries=0,revision=1;
 vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{
  if(url==='/api/auth/csrf')return response({token:'csrf'});
  if(url.includes('/buyer-candidates')){queries++;if(queries===1){signal=init.signal as AbortSignal;return late.promise;}return response(page([{membership_id:'fresh',display_name:'Fresh buyer'}]));}
  if(init.method==='POST'){revision=2;return response({...request(),id:'A',title:'A current request',status:'APPROVED',version:2});}
  if(url.includes('/history'))return response(page([event('event-'+revision,revision===1?'Initial history':'Fresh history')]));
  return response({...request(),id:'A',title:'A current request',status:'APPROVED',version:revision});
 }));
 const Harness=harness();render(<Harness id="A"/>);
 fireEvent.click(await screen.findByRole('button',{name:'Consultar compradores elegíveis'}));
 await waitFor(()=>expect(queries).toBe(1));
 if(kind==='refresh'){revision=2;fireEvent.click(screen.getByRole('button',{name:'Atualizar detalhe'}));}
 else{fireEvent.change(screen.getByLabelText('Comentário'),{target:{value:'Current note'}});fireEvent.click(screen.getByRole('button',{name:'Adicionar comentário'}));}
 await screen.findByText('Fresh history');
 fireEvent.click(screen.getByRole('button',{name:'Consultar compradores elegíveis'}));
 await screen.findByRole('option',{name:'Fresh buyer'});
 await act(async()=>{late.resolve(response(page([{membership_id:'stale',display_name:'Stale buyer'}])));await late.promise;});
 expect(signal?.aborted).toBe(true);
 expect(screen.getByRole('option',{name:'Fresh buyer'})).toBeInTheDocument();
 expect(screen.queryByRole('option',{name:'Stale buyer'})).not.toBeInTheDocument();
});
