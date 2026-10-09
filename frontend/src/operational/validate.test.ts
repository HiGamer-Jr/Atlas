import {expect, it} from 'vitest';
import {parseOperationalScope} from './validate';

export const snapshot = () => ({schema_version:1, actor_kind:'TENANT', context_id:'ctx', tenant:{id:'tenant',name:'Actual tenant'}, contract:{id:'contract',code:'CTR',name:'Contract',environment:'TEST'}, customer_scope:{role:{id:'role',code:'CUSTOM_ROLE',name:'Customer role'},unit_scope:{mode:'RESTRICTED'},organization_nodes:[{id:'unit',code:'UNIT',name:'Actual unit',kind:'UNIT',parent_id:null}],modules:[{code:'DATAHUB',label:'Data Hub',contracted:true,active:true,operational_available:true}],capabilities:['datahub.read']}});
it('accepts a server custom role and exact scope',()=>{expect(parseOperationalScope(snapshot(),'ctx')).toEqual(snapshot());});
it.each([
 (s:ReturnType<typeof snapshot>)=>{s.schema_version=2;},
 (s:ReturnType<typeof snapshot>)=>{s.context_id='other';},
 (s:ReturnType<typeof snapshot>)=>{s.actor_kind='UNKNOWN';},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.unit_scope.mode='UNKNOWN';},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.role.code='';},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.organization_nodes[0].kind='FAKE';},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.organization_nodes[0].parent_id='foreign' as unknown as null;},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.organization_nodes.push(s.customer_scope.organization_nodes[0]);},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.modules[0].active=false;},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.modules[0].contracted=false;},
 (s:ReturnType<typeof snapshot>)=>{s.customer_scope.modules[0].code='FAKE';},
])('rejects invalid state without fallback %s',(mutate)=>{const s=snapshot();mutate(s);expect(()=>parseOperationalScope(s,'ctx')).toThrow();});
it('rejects cycles and too large arrays',()=>{const s=snapshot();s.customer_scope.organization_nodes[0].parent_id='unit' as unknown as null;expect(()=>parseOperationalScope(s,'ctx')).toThrow();s.customer_scope.organization_nodes=Array.from({length:1001},(_,i)=>({id:String(i),code:String(i),name:'Unit',kind:'UNIT',parent_id:null}));expect(()=>parseOperationalScope(s,'ctx')).toThrow();});
it('keeps internal operators separate',()=>{const s={...snapshot(),actor_kind:'INTERNAL',customer_scope:null};expect(parseOperationalScope(s,'ctx')).toEqual(s);expect(()=>parseOperationalScope({...s,customer_scope:snapshot().customer_scope},'ctx')).toThrow();});

it('does not coerce array mode into a valid policy',()=>{const s=snapshot();(s.customer_scope.unit_scope as unknown as {mode:unknown}).mode=['ALL'];expect(()=>parseOperationalScope(s,'ctx')).toThrow();});
it('rejects invalid physical containment even for acyclic nodes',()=>{const s=snapshot();s.customer_scope.organization_nodes=[{id:'office',kind:'OFFICE',parent_id:null,code:'O',name:'Office'},{id:'company',kind:'COMPANY',parent_id:'office' as unknown as null,code:'C',name:'Company'}];expect(()=>parseOperationalScope(s,'ctx')).toThrow();});
it('rejects capabilities contradicted by inactive contracted module',()=>{const s=snapshot();s.customer_scope.modules[0].active=false;s.customer_scope.modules[0].operational_available=false;expect(()=>parseOperationalScope(s,'ctx')).toThrow();});
