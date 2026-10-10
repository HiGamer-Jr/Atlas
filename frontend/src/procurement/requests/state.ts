import {useCallback,useLayoutEffect,useMemo,useState} from 'react';
import {useAuth} from '../../auth/state';
import {useAccessContext} from '../../platform/state';
import {useOperationalScope} from '../../operational/state';
import {parseOperationalScope} from '../../operational/validate';
import {purchaseRequestApi} from './api';
import type {Binding} from './types';
import type {ScopeNode,OperationalScope} from '../../operational/types';
import type {ApiClient} from '../../api/client';
class RequestGeneration {
 private active=true;
 readonly controllers=new Set<AbortController>();
 readonly signature:string|null;
 readonly api:ReturnType<typeof purchaseRequestApi>;
 constructor(client:ApiClient,signature:string|null){this.signature=signature;this.api=purchaseRequestApi(client);}
 isActive(){return this.active;}
 activate(){this.active=true;}
 dispose(){this.active=false;this.controllers.forEach(c=>c.abort());}
}
function validateReturnedUnits(value:unknown,nodes:ScopeNode[]){
 if(!value||typeof value!=='object')return;
 const record=value as Record<string,unknown>;
 if(record.schema_version===1&&record.requesting_node){const node=record.requesting_node as {id?:unknown;kind?:unknown};if(!nodes.some(n=>n.id===node.id&&n.kind===node.kind&&n.kind!=='COMPANY'))throw new Error('PURCHASE_REQUEST_INVALID');}
 if(Array.isArray(record.items))record.items.forEach(item=>validateReturnedUnits(item,nodes));
 if(record.value)validateReturnedUnits(record.value,nodes);
}
export type RequestScopeState={status:'idle'|'loading'|'unavailable';binding:null;scope:null}|{status:'ready';binding:Binding;scope:Extract<OperationalScope,{actor_kind:'TENANT'}>};
export function usePurchaseRequests(){
 const auth=useAuth(),context=useAccessContext(),operational=useOperationalScope();
 const scopeState=useMemo<RequestScopeState>(()=>{
  const closed:RequestScopeState={status:operational.status==='idle'?'idle':operational.status==='loading'?'loading':'unavailable',binding:null,scope:null};
  if(auth.loading||auth.busy||auth.user?.platform_role!==null||context.loading||context.busy||context.recovering||!context.selected||operational.status!=='ready')return closed;
  try{const scope=parseOperationalScope(operational.scope,context.selected.id);if(scope.actor_kind==='TENANT'&&scope.contract.id===context.selected.contract_id&&scope.customer_scope.modules.some(m=>m.code==='PROCUREMENT'&&m.contracted&&m.active&&m.operational_available)&&scope.customer_scope.organization_nodes.some(n=>n.kind!=='COMPANY')&&scope.customer_scope.capabilities.some(c=>['procurement.requests.read_own','procurement.requests.read_unit'].includes(c)))return {status:'ready',scope,binding:{contextId:scope.context_id,tenantId:scope.tenant.id,contractId:scope.contract.id}};}catch{/* Unknown snapshots close controls. */}
  return closed;
 },[auth.loading,auth.busy,auth.user?.platform_role,context.loading,context.busy,context.recovering,context.selected,operational]);
 const signature=scopeState.status==='ready'?JSON.stringify([scopeState.binding,scopeState.scope.customer_scope]):null;
 const session=useMemo(()=>new RequestGeneration(auth.api,signature),[auth.api,signature]);
 const [denied,setDenied]=useState<object|null>(null);
 // Commit cleanup invalidates every old generation, including transports ignoring abort.
 useLayoutEffect(()=>{session.activate();return()=>session.dispose();},[session]);
 const run=useCallback(async<T,>(operation:(signal:AbortSignal)=>Promise<T>):Promise<T>=>{
  if(!session.isActive()||!session.signature||denied===session)throw new DOMException('Scope unavailable','AbortError');
  const controller=new AbortController();session.controllers.add(controller);
  try{const value=await operation(controller.signal);if(controller.signal.aborted||!session.isActive())throw new DOMException('Scope changed','AbortError');if(scopeState.status!=='ready')throw new DOMException('Scope unavailable','AbortError');validateReturnedUnits(value,scopeState.scope.customer_scope.organization_nodes);return value;}catch(error){if(session.isActive()&&error instanceof Error&&(error.message==='PURCHASE_REQUEST_INVALID'||('status'in error&&[401,403,404,503].includes(Number(error.status))))){setDenied(session);auth.api.cancelContext();window.dispatchEvent(new Event('focus'));}throw error;}finally{session.controllers.delete(controller);}
 },[session,denied,auth.api,scopeState]);
 const state=useMemo<RequestScopeState>(()=>denied===session?{status:'unavailable',binding:null,scope:null}:scopeState,[denied,session,scopeState]);
 const has=useCallback((action:string)=>state.status==='ready'&&state.scope.customer_scope.capabilities.includes('procurement.requests.'+action),[state]);
 return useMemo(()=>({state,signature,api:session.api,run,has,user:auth.user}),[state,signature,session,run,has,auth.user]);
}
