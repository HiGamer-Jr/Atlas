import {cleanup,fireEvent,render,screen,waitFor} from '@testing-library/react';
import {afterEach,expect,it,vi} from 'vitest';
import {AuthContext,type Auth} from '../auth/state';
import {Context,type ContextState} from '../platform/state';
import {ApiClient} from '../api/client';
import {OperationalContext,type OperationalScopeState} from '../operational/state';
import type {OperationalScope} from '../operational/types';
import TenantWorkspace from './TenantWorkspace';
const scope:OperationalScope={schema_version:1,actor_kind:'TENANT',context_id:'ctx',tenant:{id:'tenant',name:'Tenant'},contract:{id:'contract',name:'Contract',code:'CTR',environment:'TEST'},customer_scope:{role:{id:'role',code:'CUSTOM',name:'Custom'},unit_scope:{mode:'ALL'},organization_nodes:[],modules:[{code:'DATAHUB',label:'Data Hub',contracted:true,active:true,operational_available:true}],capabilities:['datahub.read']}};
const auth:Auth={api:new ApiClient(),user:{user_id:'u',display_name:'User',platform_role:null},loading:false,busy:false,error:null,login:async()=>{},logout:async()=>{},retry:()=>{}};
const context:ContextState={selected:{id:'ctx',tenant_name:'Tenant',contract_id:'contract',contract_code:'CTR',environment:'TEST',expires_at:'2099-01-01',capabilities:[]},loading:false,busy:false,error:null,recovering:false,select:async()=>{},clear:async()=>{},retry:()=>{}};
function Harness({state}:{state:OperationalScopeState}){return <AuthContext.Provider value={auth}><Context.Provider value={context}><OperationalContext.Provider value={state}><TenantWorkspace/></OperationalContext.Provider></Context.Provider></AuthContext.Provider>;}
afterEach(()=>{cleanup();vi.unstubAllGlobals();});
it('preserves selected file through successful same-context revalidation with controls hidden',async()=>{
 vi.stubGlobal('fetch',vi.fn(async(url:string)=>new Response(JSON.stringify(url==='/api/datahub/templates'?{profile:'Custom',units:[],items:[{id:'COORDENACAO',version:1,label:'Coordenação',available:true,can_download:true,can_import:true,can_export:true,datasets:[]}]}:{items:[],total:0,page:1,page_size:10}))));
 const ready:OperationalScopeState={status:'ready',scope};const view=render(<Harness state={ready}/>);const input=await screen.findByLabelText('Planilha XLSX');
 fireEvent.change(input,{target:{files:[new File(['xlsx'],'chosen.xlsx')]}});expect(screen.getByRole('button',{name:'Validar e gerar preview'})).toBeEnabled();
 view.rerender(<Harness state={{status:'loading',scope:null}}/>);expect(screen.queryByRole('button',{name:'Validar e gerar preview'})).not.toBeInTheDocument();
 view.rerender(<Harness state={ready}/>);await waitFor(()=>expect(screen.getByRole('button',{name:'Validar e gerar preview'})).toBeEnabled());
 const changed:OperationalScope={...scope,customer_scope:{...scope.customer_scope!,role:{id:'other-role',code:'OTHER',name:'Changed'}}} as OperationalScope;
 view.rerender(<Harness state={{status:'ready',scope:changed}}/>);await waitFor(()=>expect(screen.getByRole('button',{name:'Validar e gerar preview'})).toBeDisabled());
 view.rerender(<Harness state={{status:'unavailable',scope:null,errorCode:'CONTEXT_INVALID'}}/>);expect(screen.queryByRole('button',{name:'Validar e gerar preview'})).not.toBeInTheDocument();
 view.rerender(<Harness state={ready}/>);await waitFor(()=>expect(screen.getByRole('button',{name:'Validar e gerar preview'})).toBeDisabled());
});
