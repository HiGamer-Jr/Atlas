import {act, cleanup, fireEvent, render, screen, waitFor} from '@testing-library/react';
import {afterEach, expect, it, vi} from 'vitest';
import {AuthContext, type Auth} from '../auth/state';
import {Context, type ContextState} from '../platform/state';
import {ApiClient} from '../api/client';
import {OperationalScopeProvider} from './OperationalScopeProvider';
import {useOperationalScope} from './state';

const wire=(id='ctx')=>({schema_version:1,actor_kind:'TENANT',context_id:id,tenant:{id:'tenant',name:'Tenant'},contract:{id:'contract',code:'CTR',name:'Contract',environment:'TEST'},customer_scope:{role:{id:'role',code:'CUSTOM',name:'Custom'},unit_scope:{mode:'ALL'},organization_nodes:[],modules:[],capabilities:[]}});
const auth:Auth={api:new ApiClient(),user:{user_id:'user',display_name:'User',platform_role:null},loading:false,busy:false,error:null,login:async()=>{},logout:async()=>{},retry:()=>{}};
const context=(id='ctx'):ContextState=>({selected:{id,tenant_name:'Tenant',contract_id:'contract',contract_code:'CTR',environment:'TEST',expires_at:'2099-01-01',capabilities:[]},loading:false,busy:false,error:null,recovering:false,select:async()=>{},clear:async()=>{},retry:()=>{}});
function Probe(){const s=useOperationalScope();return <p data-testid="scope">{s.status}:{s.scope?.context_id??'closed'}</p>;}
function Harness({id='ctx'}:{id?:string}){return <AuthContext.Provider value={auth}><Context.Provider value={context(id)}><OperationalScopeProvider><Probe/></OperationalScopeProvider></Context.Provider></AuthContext.Provider>;}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('loads custom server scope then clears it immediately on focus failure',async()=>{let failed=false;vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(failed?{code:'OPERATIONAL_SCOPE_TOO_LARGE'}:wire()),{status:failed?503:200})));render(<Harness/>);await screen.findByText('ready:ctx');failed=true;fireEvent(window,new Event('focus'));expect(screen.getByTestId('scope')).toHaveTextContent('loading:closed');await screen.findByText('unavailable:closed');});
it('context switch ignores old response and never exposes stale scope',async()=>{let release:((r:Response)=>void)|undefined;vi.stubGlobal('fetch',vi.fn((_:string,init:RequestInit)=>new Headers(init.headers).get('X-HiAtlas-Context')==='ctx'?new Promise<Response>(r=>{release=r;}):Promise.resolve(new Response(JSON.stringify(wire('next'))))));const view=render(<Harness/>);await waitFor(()=>expect(release).toBeDefined());view.rerender(<Harness id="next"/>);await screen.findByText('ready:next');await act(async()=>{release!(new Response(JSON.stringify(wire())));});expect(screen.getByTestId('scope')).toHaveTextContent('ready:next');});
it('rejects missing or mismatched actor scope without synthetic fallback',async()=>{vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({...wire(),actor_kind:'INTERNAL',customer_scope:null}))));render(<Harness/>);await screen.findByText('unavailable:closed');});
it('independent providers preserve their own opaque context',async()=>{vi.stubGlobal('fetch',vi.fn(async(_:string,init:RequestInit)=>new Response(JSON.stringify(wire(new Headers(init.headers).get('X-HiAtlas-Context')!)))));render(<><Harness id="A"/><Harness id="B"/></>);await screen.findByText('ready:A');await screen.findByText('ready:B');expect(localStorage.getItem('hiatlas.operational-scope')).toBeNull();});

it.each(['mode','containment','module'])('malformed %s discovery remains unavailable',async(kind)=>{
 const value=wire();if(kind==='mode')(value.customer_scope.unit_scope as unknown as {mode:unknown}).mode=['ALL'];
 if(kind==='containment')(value.customer_scope as unknown as {organization_nodes:unknown[]}).organization_nodes=[{id:'office',code:'O',name:'Office',kind:'OFFICE',parent_id:null},{id:'company',code:'C',name:'Company',kind:'COMPANY',parent_id:'office'}];
 if(kind==='module'){(value.customer_scope as unknown as {modules:unknown[]}).modules=[{code:'DATAHUB',label:'Data Hub',contracted:true,active:false,operational_available:false}];(value.customer_scope as unknown as {capabilities:string[]}).capabilities=['datahub.read'];}
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify(value))));render(<Harness/>);await screen.findByText('unavailable:closed');
});
