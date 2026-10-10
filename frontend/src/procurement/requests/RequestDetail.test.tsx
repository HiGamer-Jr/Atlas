import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {AuthContext,type Auth} from '../../auth/state';
import {Context,type ContextState} from '../../platform/state';
import {OperationalContext} from '../../operational/state';
import {ApiClient} from '../../api/client';
import {scope,request} from './fixtures';
import {RequestDetail} from './RequestDetail';
function mount(value:ReturnType<typeof request>,response?:(url:string,init:RequestInit)=>Response){
 const posts:{url:string;body:Record<string,unknown>;headers:Headers}[]=[];
 vi.stubGlobal('fetch',vi.fn(async(url:string,init:RequestInit)=>{if(url==='/api/auth/csrf')return new Response(JSON.stringify({token:'csrf'}));if(init.method==='POST'){posts.push({url,body:JSON.parse(init.body as string),headers:new Headers(init.headers)});return response?response(url,init):new Response(JSON.stringify({...value,version:value.version+1}));}if(url.includes('/history'))return new Response(JSON.stringify({items:[],total:0,limit:50,next_cursor:null}));return new Response(JSON.stringify(value));}));
 const auth:Auth={api:new ApiClient(),user:{user_id:'user',display_name:'User',platform_role:null},loading:false,busy:false,error:null,login:async()=>{},logout:async()=>{},retry:()=>{}};
 const context:ContextState={selected:{id:'ctx',tenant_name:'Tenant',contract_id:'contract',contract_code:'CTR',environment:'TEST',expires_at:'2099-01-01',capabilities:[]},loading:false,busy:false,error:null,recovering:false,select:async()=>{},clear:async()=>{},retry:()=>{}};
 const allowed=structuredClone(scope);if(allowed.actor_kind==='TENANT')allowed.customer_scope.capabilities.push(...['triage','approve','assign','fulfill','cancel','close','comment','read_unit'].map(a=>'procurement.requests.'+a));
 render(<AuthContext.Provider value={auth}><Context.Provider value={context}><OperationalContext.Provider value={{status:'ready',scope:allowed}}><RequestDetail requestId="request"/></OperationalContext.Provider></Context.Provider></AuthContext.Provider>);
 return posts;
}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('urgent sends separate reason in addition to stored justification',async()=>{const value={...request(),priority:'URGENT'};const posts=mount(value);await screen.findByRole('button',{name:'Enviar solicitação'});fireEvent.click(screen.getByRole('button',{name:'Enviar solicitação'}));expect(posts).toHaveLength(0);fireEvent.change(screen.getByLabelText('Motivo da ação'),{target:{value:'Immediate safety risk'}});fireEvent.click(screen.getByRole('button',{name:'Enviar solicitação'}));await waitFor(()=>expect(posts).toHaveLength(1));expect(posts[0].body).toEqual({expected_version:1,reason:'Immediate safety risk'});expect(posts[0].headers.get('Idempotency-Key')).toBeTruthy();});
it('409 requires explicit refresh and decision without automatic retry or merge',async()=>{const posts=mount(request(),()=>new Response(JSON.stringify({code:'VERSION_CONFLICT'}),{status:409}));fireEvent.click(await screen.findByRole('button',{name:'Enviar solicitação'}));await waitFor(()=>expect(screen.getByRole('button',{name:'Enviar solicitação'})).toBeDisabled());expect(posts).toHaveLength(1);expect(screen.getByText(/as alterações não foram mescladas/)).toBeInTheDocument();fireEvent.click(screen.getByRole('button',{name:'Atualizar detalhe'}));await waitFor(()=>expect(screen.getByRole('button',{name:'Enviar solicitação'})).toBeEnabled());expect(posts).toHaveLength(1);});
it('unknown server representation closes all action controls',async()=>{mount(request(),()=>new Response(JSON.stringify({...request(),status:'UNKNOWN'})));fireEvent.click(await screen.findByRole('button',{name:'Enviar solicitação'}));await waitFor(()=>expect(screen.queryByRole('button',{name:'Enviar solicitação'})).not.toBeInTheDocument());});
it('triage delegates policy to server and never sends waiver choice',async()=>{const posts=mount({...request(),status:'IN_TRIAGE'});fireEvent.click(await screen.findByRole('button',{name:'Concluir triagem pela política do contrato'}));await waitFor(()=>expect(posts).toHaveLength(1));expect(posts[0].url).toBe('/api/procurement/requests/request/request-approval');expect(posts[0].body).toEqual({expected_version:1});expect(screen.queryByRole('combobox',{name:/política/i})).not.toBeInTheDocument();});
it('manual fulfillment preserves exact quantity evidence and version',async()=>{const posts=mount({...request(),status:'IN_FULFILLMENT',buyer:{membership_id:'buyer',display_name:'Eligible buyer'}} as ReturnType<typeof request>);await screen.findByRole('button',{name:'Registrar atendimento'});fireEvent.change(screen.getByLabelText('Item atendido'),{target:{value:'item'}});fireEvent.change(screen.getByLabelText('Quantidade atendida'),{target:{value:'0.000001'}});fireEvent.change(screen.getByLabelText('Evidência do atendimento'),{target:{value:'Receipt checked'}});fireEvent.change(screen.getByLabelText('Motivo da ação'),{target:{value:'Manual external record'}});fireEvent.click(screen.getByRole('button',{name:'Registrar atendimento'}));await waitFor(()=>expect(posts).toHaveLength(1));expect(posts[0].body).toEqual({expected_version:1,item_id:'item',quantity:'0.000001',evidence:'Receipt checked',reason:'Manual external record'});});

it('request unit outside current server scope never opens detail controls',async()=>{mount({...request(),requesting_node:{...request().requesting_node,id:'foreign-unit'}});await waitFor(()=>expect(screen.getByText('Detalhe indisponível neste escopo.')).toBeInTheDocument());expect(screen.queryByRole('button',{name:'Enviar solicitação'})).not.toBeInTheDocument();});


it('comment accepts Unicode at server limit without UTF16 maxlength',async()=>{
 const posts=mount({...request(),status:'SUBMITTED'});
 const input=await screen.findByLabelText('Comentário') as HTMLTextAreaElement;
 expect(input.maxLength).toBe(-1);
 fireEvent.change(input,{target:{value:'🚀'.repeat(4000)}});
 expect(input.checkValidity()).toBe(true);
 fireEvent.click(screen.getByRole('button',{name:'Adicionar comentário'}));
 await waitFor(()=>expect(posts).toHaveLength(1));
 expect(posts[0].body.text).toBe('🚀'.repeat(4000));
});
it('comment rejects above Unicode limit before transport',async()=>{
 const posts=mount({...request(),status:'SUBMITTED'});
 const input=await screen.findByLabelText('Comentário') as HTMLTextAreaElement;
 fireEvent.change(input,{target:{value:'🚀'.repeat(4001)}});
 expect(input.checkValidity()).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'Adicionar comentário'}));
 expect(await screen.findByRole('alert')).toHaveTextContent(/caracteres/);
 expect(posts).toHaveLength(0);
});


it.each([['Motivo da ação','😀'.repeat(2001)],['Evidência do atendimento','🚀'.repeat(4001)]])('fulfillment rejects text beyond codepoint bound for %s',async(label,text)=>{
 const posts=mount({...request(),status:'IN_FULFILLMENT',buyer:{membership_id:'buyer',display_name:'Buyer'}});
 await screen.findByRole('button',{name:'Registrar atendimento'});
 fireEvent.change(screen.getByLabelText('Item atendido'),{target:{value:'item'}});
 fireEvent.change(screen.getByLabelText('Quantidade atendida'),{target:{value:'0.000001'}});
 fireEvent.change(screen.getByLabelText('Motivo da ação'),{target:{value:'External record'}});
 fireEvent.change(screen.getByLabelText('Evidência do atendimento'),{target:{value:'Receipt'}});
 const input=screen.getByLabelText(label) as HTMLTextAreaElement;
 fireEvent.change(input,{target:{value:text}});
 expect(input.checkValidity()).toBe(false);
 fireEvent.click(screen.getByRole('button',{name:'Registrar atendimento'}));
 expect(await screen.findByRole('alert')).toHaveTextContent(/caracteres/);
 expect(posts).toHaveLength(0);
});
