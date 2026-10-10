import {cleanup,fireEvent,render,screen,waitFor,within} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {AuthContext,type Auth} from '../../auth/state';
import {Context,type ContextState} from '../../platform/state';
import {OperationalContext,type OperationalScopeState} from '../../operational/state';
import {ApiClient} from '../../api/client';
import {scope,request} from './fixtures';
import {RequestWorkspace} from './RequestWorkspace';
const context:ContextState={selected:{id:'ctx',tenant_name:'Tenant',contract_id:'contract',contract_code:'CTR',environment:'TEST',expires_at:'2099-01-01',capabilities:[]},loading:false,busy:false,error:null,recovering:false,select:async()=>{},clear:async()=>{},retry:()=>{}};
function Harness({state={status:'ready',scope},client=new ApiClient()}:{state?:OperationalScopeState;client?:ApiClient}){const auth:Auth={api:client,user:{user_id:'user',display_name:'User',platform_role:null},loading:false,busy:false,error:null,login:async()=>{},logout:async()=>{},retry:()=>{}};return <AuthContext.Provider value={auth}><Context.Provider value={state.status==='ready'?{...context,selected:{...context.selected!,id:state.scope.context_id,contract_id:state.scope.contract.id}}:context}><OperationalContext.Provider value={state}><RequestWorkspace/></OperationalContext.Provider></Context.Provider></AuthContext.Provider>;}
afterEach(()=>{cleanup();vi.unstubAllGlobals();vi.restoreAllMocks();});
it('unknown_state_module_contradiction_closes_controls',()=>{render(<Harness state={{status:'loading',scope:null}}/>);expect(screen.queryByRole('button',{name:'Nova solicitação'})).not.toBeInTheDocument();expect(screen.queryByRole('button',{name:'Enviar solicitação'})).not.toBeInTheDocument();});
it('custom_role_real_unit_submission',async()=>{
 const posts:Record<string,unknown>[]=[];vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{if(url==='/api/auth/csrf')return new Response(JSON.stringify({token:'csrf'}));if(init.method==='POST'){posts.push(JSON.parse(init.body as string));return new Response(JSON.stringify(request()));}if(url.includes('/history'))return new Response(JSON.stringify({items:[],total:0,limit:50,next_cursor:null}));return new Response(JSON.stringify({items:[],total:0,limit:50,next_cursor:null}));}));
 render(<Harness/>);fireEvent.click(screen.getByRole('button',{name:'Nova solicitação'}));fireEvent.change(screen.getByLabelText('Título'),{target:{value:'Need'}});fireEvent.click(screen.getByRole('button',{name:'Adicionar item'}));fireEvent.change(screen.getByLabelText('Descrição do item 1'),{target:{value:'Actual need'}});fireEvent.change(screen.getByLabelText('Quantidade do item 1'),{target:{value:'0.000001'}});fireEvent.click(screen.getByRole('button',{name:'Salvar rascunho'}));await waitFor(()=>expect(posts.length).toBe(1));expect(posts[0].requesting_node_id).toBe('unit');expect((posts[0].items as {requested_quantity:string}[])[0].requested_quantity).toBe('0.000001');expect(posts[0]).not.toHaveProperty('tenant_id');
});
it('late_response_cannot_restore_previous_context',async()=>{
 let complete!:(value:Response)=>void;vi.stubGlobal('fetch',vi.fn(()=>new Promise<Response>(done=>{complete=done;})));const client=new ApiClient();const view=render(<Harness client={client}/>);view.rerender(<Harness client={client} state={{status:'unavailable',scope:null,errorCode:'CONTEXT_INVALID'}}/>);complete(new Response(JSON.stringify({items:[request()],total:1,limit:50,next_cursor:null})));await waitFor(()=>expect(screen.queryByText('Actual need')).not.toBeInTheDocument());expect(screen.queryByRole('button',{name:'Nova solicitação'})).not.toBeInTheDocument();
});
it('tabs_are_independent',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[],total:0,limit:50,next_cursor:null}))));const a=render(<Harness/>);fireEvent.click(screen.getByRole('button',{name:'Nova solicitação'}));fireEvent.change(screen.getByLabelText('Título'),{target:{value:'Tab A'}});a.unmount();render(<Harness/>);fireEvent.click(screen.getByRole('button',{name:'Nova solicitação'}));expect(screen.getByLabelText('Título')).toHaveValue('');
});

it('two mounted tabs hold independent drafts and lifecycles',async()=>{
 vi.stubGlobal('fetch',vi.fn(async()=>new Response(JSON.stringify({items:[],total:0,limit:50,next_cursor:null}))));
 const a=render(<Harness/>),b=render(<Harness/>);fireEvent.click(within(a.container).getByRole('button',{name:'Nova solicitação'}));fireEvent.click(within(b.container).getByRole('button',{name:'Nova solicitação'}));
 fireEvent.change(within(a.container).getByLabelText('Título'),{target:{value:'Tab A'}});fireEvent.change(within(b.container).getByLabelText('Título'),{target:{value:'Tab B'}});a.unmount();expect(within(b.container).getByLabelText('Título')).toHaveValue('Tab B');
});




it('context changes abort mutations and late success cannot reopen old detail',async()=>{
 let complete!:(v:Response)=>void;let posted=false;let oldSignal:AbortSignal|undefined;
 vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{if(url==='/api/auth/csrf')return new Response(JSON.stringify({token:'csrf'}));if(init.method==='POST'){posted=true;oldSignal=init.signal as AbortSignal;return new Promise<Response>(done=>{complete=done;});}if(url.includes('/history'))return new Response(JSON.stringify({items:[],total:0,limit:50,next_cursor:null}));if(url==='/api/procurement/requests/request')return new Response(JSON.stringify(request()));const isB=new Headers(init.headers).get('X-HiAtlas-Context')==='ctxB';return new Response(JSON.stringify({items:isB?[]:[request()],total:isB?0:1,limit:50,next_cursor:null}));}));
 const client=new ApiClient(),view=render(<Harness client={client}/>);fireEvent.click(await screen.findByRole('button',{name:'Actual need'}));fireEvent.click(await screen.findByRole('button',{name:'Enviar solicitação'}));await waitFor(()=>expect(posted).toBe(true));
 const b=structuredClone(scope);b.context_id='ctxB';b.tenant.id='tenantB';b.contract.id='contractB';view.rerender(<Harness client={client} state={{status:'ready',scope:b}}/>);expect(oldSignal?.aborted).toBe(true);complete(new Response(JSON.stringify({...request(),status:'SUBMITTED',version:2})));await waitFor(()=>expect(screen.getByText('0 solicitação(ões)')).toBeInTheDocument());expect(screen.queryByText('Actual need')).not.toBeInTheDocument();expect(screen.queryByRole('button',{name:'Enviar solicitação'})).not.toBeInTheDocument();
});
it.each(['inactive','unknown','internal','company','action-only'])('closes workspace controls for contradicted scope %s',kind=>{
 const wire=structuredClone(scope);if(wire.actor_kind!=='TENANT')throw new Error();if(kind==='inactive')wire.customer_scope.modules[0].active=false;if(kind==='unknown')wire.customer_scope.capabilities.push('procurement.requests.future');if(kind==='internal')(wire as unknown as {actor_kind:string}).actor_kind='INTERNAL';if(kind==='company')wire.customer_scope.organization_nodes[0].kind='COMPANY';if(kind==='action-only')wire.customer_scope.capabilities=['procurement.requests.create'];render(<Harness state={{status:'ready',scope:wire}}/>);expect(screen.queryByRole('button',{name:'Nova solicitação'})).not.toBeInTheDocument();expect(screen.queryByRole('button',{name:'Enviar solicitação'})).not.toBeInTheDocument();
});
