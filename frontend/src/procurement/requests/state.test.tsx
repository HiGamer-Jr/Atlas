import {cleanup,render,screen} from '@testing-library/react';
import {afterEach,expect,it} from 'vitest';
import {AuthContext,type Auth} from '../../auth/state';
import {Context,type ContextState} from '../../platform/state';
import {OperationalContext} from '../../operational/state';
import {ApiClient} from '../../api/client';
import {scope} from './fixtures';
import {usePurchaseRequests} from './state';
afterEach(cleanup);
function Probe(){const p=usePurchaseRequests();return <><p>{p.state.status}</p>{p.state.status==='ready'&&p.has('create')&&<button>Candidate create</button>}</>;}
function mount(caps:string[]){const wire=structuredClone(scope);if(wire.actor_kind==='TENANT')wire.customer_scope.capabilities=caps;const auth:Auth={api:new ApiClient(),user:{user_id:'user',display_name:'User',platform_role:null},loading:false,busy:false,error:null,login:async()=>{},logout:async()=>{},retry:()=>{}};const context:ContextState={selected:{id:'ctx',tenant_name:'Tenant',contract_id:'contract',contract_code:'CTR',environment:'TEST',expires_at:'2099-01-01',capabilities:[]},loading:false,busy:false,error:null,recovering:false,select:async()=>{},clear:async()=>{},retry:()=>{}};return render(<AuthContext.Provider value={auth}><Context.Provider value={context}><OperationalContext.Provider value={{status:'ready',scope:wire}}><Probe/></OperationalContext.Provider></Context.Provider></AuthContext.Provider>);}
it('read_unit permits own workflow fallback for custom role',()=>{mount(['procurement.requests.read_unit','procurement.requests.create']);expect(screen.getByText('ready')).toBeInTheDocument();expect(screen.getByRole('button',{name:'Candidate create'})).toBeInTheDocument();});
it('actions never grant read authority',()=>{mount(['procurement.requests.create','procurement.requests.fulfill']);expect(screen.getByText('unavailable')).toBeInTheDocument();expect(screen.queryByRole('button',{name:'Candidate create'})).not.toBeInTheDocument();});
