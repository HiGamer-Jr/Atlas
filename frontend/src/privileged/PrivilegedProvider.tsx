import {useCallback,useEffect,useRef,useState,type ReactNode} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext,type AccessContext} from '../platform/state';
import {useSupport} from '../support/state';
import {ApiError,isAbort} from '../api/errors';
import {readPrivileged,storePrivileged} from './storage';
import {PrivilegedContext} from './state';
import type {Grant,MaintenanceScope} from './types';
export default function PrivilegedProvider({children}:{children:ReactNode}){
 const {api,user,busy:authBusy}=useAuth();
 const {selected,invalidate,retry:refreshParent,registerPrivileged}=useAccessContext();
 const support=useSupport();
 const [grant,setGrant]=useState<Grant|null>(null);
 const [restoring,setRestoring]=useState(()=>!!readPrivileged());
 const [unresolved,setUnresolved]=useState(false);
 const [busy,setBusy]=useState(false);
 const [error,setError]=useState<unknown>(null);
 const [endedContext,setEndedContext]=useState<string|null>(null);
 const current=useRef<Grant|null>(null);
 const generation=useRef(0),controller=useRef<AbortController|null>(null);
 const locked=useRef(false),focusReturn=useRef(false);
 const parent=selected?.id,contract=selected?.contract_id,operator=user?.user_id;
 const discovered=selected?.privileged_context_id;
 const discard=useCallback(()=>{
  generation.current++;
  controller.current?.abort();
  api.cancelContext();
  current.current=null;
  storePrivileged(null);
  registerPrivileged?.(null);
  setGrant(null);
  setUnresolved(false);
  setRestoring(false);
  setBusy(false);
  setError(null);
  invalidate?.('Acesso temporário encerrado, expirado ou revogado. Selecione um ambiente para continuar.');
 },[api,invalidate,registerPrivileged]);
 const validate=useCallback((value:Grant)=>{
  if(user?.platform_role!=='PLATFORM_ADMIN'||support?.session||support?.restoring
   ||value.parent_context_id!==parent||value.contract_id!==contract
   ||value.operator?.user_id!==operator||value.operator?.platform_role!=='PLATFORM_ADMIN'
   ||!['FINANCIAL_FISCAL','MAINTENANCE'].includes(value.grant_type)||value.status!=='ACTIVE'
   ||!value.context_id||!Number.isFinite(Date.parse(value.expires_at))
   ||Date.parse(value.expires_at)<=Date.now())throw new ApiError(403);
  return value;
 },[user?.platform_role,support?.session,support?.restoring,parent,contract,operator]);
 const verify=useCallback(async(id:string,signal:AbortSignal)=>{
  const epoch=generation.current;
  try{
   const value=validate(await api.request<Grant>('/grants/context',{contextId:id,signal}));
   if(value.context_id!==id)throw new ApiError(403);
   if(signal.aborted||epoch!==generation.current)return;
   current.current=value;
   registerPrivileged?.(value.context_id);
   storePrivileged(value.context_id);
   setGrant(value);
   setUnresolved(false);
   setRestoring(false);
   setError(null);
  }catch(e){
   if(signal.aborted||epoch!==generation.current||isAbort(e))return;
   if(e instanceof ApiError&&[401,403,404].includes(e.status))discard();
   else{setError(e);setRestoring(true);}
  }
 },[api,validate,discard,registerPrivileged]);
 // An interrupted creation is unknown until the parent is authoritatively reconciled.
 // This state is never treated as an ordinary administrative context.
 const reconcile=useCallback(async()=>{
  if(!parent)return;
  const epoch=generation.current;
  controller.current?.abort();
  const abort=new AbortController();
  controller.current=abort;
  try{
   const value=await api.request<AccessContext>('/context',{contextId:parent,signal:abort.signal});
   if(abort.signal.aborted||epoch!==generation.current)return;
   if(value.id!==parent||value.contract_id!==contract)throw new ApiError(403);
   if(value.privileged_context_id){
    registerPrivileged?.(value.privileged_context_id);
    storePrivileged(value.privileged_context_id);
    await verify(value.privileged_context_id,abort.signal);
   }else{
    current.current=null;
    storePrivileged(null);
    registerPrivileged?.(null);
    setGrant(null);
    setUnresolved(false);
    setRestoring(false);
   }
  }catch(e){
   if(abort.signal.aborted||epoch!==generation.current||isAbort(e))return;
   if(e instanceof ApiError&&[401,403,404].includes(e.status))discard();
   else{setError(e);setRestoring(true);}
  }
 },[api,parent,contract,verify,registerPrivileged,discard]);
 const restore=useCallback(()=>{
  const id=current.current?.context_id??(discovered!==endedContext?discovered:null)??readPrivileged();
  if(!id){void reconcile();return;}
  controller.current?.abort();
  const abort=new AbortController();
  controller.current=abort;
  setRestoring(true);
  void verify(id,abort.signal);
 },[discovered,endedContext,verify,reconcile]);
 useEffect(()=>{
  if(authBusy||unresolved)return;
  const id=current.current?.context_id??(discovered!==endedContext?discovered:null)??readPrivileged();
  if(!id)return;
  const abort=new AbortController();
  controller.current=abort;
  void verify(id,abort.signal);
  return()=>abort.abort();
 },[authBusy,unresolved,discovered,endedContext,verify]);
 // Reconcile an interrupted server mutation once authentication becomes usable.
 // eslint-disable-next-line react/set-state-in-effect
 useEffect(()=>{if(unresolved&&!authBusy)void reconcile();},[unresolved,authBusy,reconcile]);
 useEffect(()=>{
  const focus=()=>{if(!locked.current&&!authBusy&&(current.current||unresolved))restore();};
  window.addEventListener('focus',focus);
  return()=>window.removeEventListener('focus',focus);
 },[authBusy,restore,unresolved]);
 useEffect(()=>()=>{generation.current++;controller.current?.abort();},[]);
 useEffect(()=>{
  if(!grant)return;
  const timer=window.setTimeout(()=>{
   const id=grant.context_id;
   discard();
   void api.request('/grants/context',{contextId:id}).catch(()=>{});
  },Math.min(Math.max(Date.parse(grant.expires_at)-Date.now(),0),2147483647));
  return()=>window.clearTimeout(timer);
 },[grant,api,discard]);
 useEffect(()=>{
  if(focusReturn.current&&!grant&&!restoring&&!busy){
   focusReturn.current=false;
   document.querySelector<HTMLElement>('[data-support-return]')?.focus();
  }
 },[grant,restoring,busy]);
 async function createGrant(grantType:'FINANCIAL_FISCAL'|'MAINTENANCE',reason:string,reference:string|null,scopes:MaintenanceScope[]){
  if(grantType==='MAINTENANCE'&&(!reference?.trim()||reason.trim().length<3||!scopes.length||scopes.some(scope=>scope.entity_type!=='organization_node'||!scope.entity_id)))throw new ApiError(422);
  if(locked.current||current.current||unresolved||!parent||support?.session||support?.restoring)throw new ApiError(403);
  locked.current=true;
  setBusy(true);
  setError(null);
  const epoch=++generation.current;
  controller.current?.abort();
  api.cancelContext();
  const abort=new AbortController();
  controller.current=abort;
  try{
   const value=validate(await api.request<Grant>('/grants',{method:'POST',contextId:parent,signal:abort.signal,body:{grant_type:grantType,reason,reference,scopes}}));
   if(epoch!==generation.current||abort.signal.aborted)return;
   if(value.grant_type!==grantType||value.scopes.length!==scopes.length||scopes.some(scope=>!value.scopes.some(actual=>actual.action_code===scope.action_code&&actual.entity_type===scope.entity_type&&actual.entity_id===scope.entity_id))){discard();throw new ApiError(403);}
   api.cancelContext();
   current.current=value;
   registerPrivileged?.(value.context_id);
   storePrivileged(value.context_id);
   setGrant(value);
  }catch(e){
   if(epoch===generation.current){
    const ambiguous=isAbort(e)||!(e instanceof ApiError)||e.status>=500||e.status===409;
    if(!isAbort(e))setError(e);
    if(ambiguous){setUnresolved(true);setRestoring(true);}
   }
   throw e;
  }finally{locked.current=false;setBusy(false);}
 }
 const start=(reason:string,reference:string|null)=>createGrant('FINANCIAL_FISCAL',reason,reference,[]);
 const startMaintenance=(reason:string,reference:string,scopes:MaintenanceScope[])=>createGrant('MAINTENANCE',reason,reference,scopes);
 async function end(){
  const value=current.current;
  if(!value||locked.current)return;
  locked.current=true;
  setBusy(true);
  setError(null);
  const epoch=++generation.current;
  controller.current?.abort();
  api.cancelContext();
  const abort=new AbortController();
  controller.current=abort;
  try{
   await api.request(`/grants/${encodeURIComponent(value.id)}/end`,{method:'POST',contextId:value.context_id,signal:abort.signal,body:{expected_version:value.version}});
   if(epoch!==generation.current||abort.signal.aborted)return;
   setEndedContext(value.context_id);
   current.current=null;
   storePrivileged(null);
   registerPrivileged?.(null);
   api.cancelContext();
   setGrant(null);
   setRestoring(false);
   focusReturn.current=true;
   refreshParent();
  }catch(e){
   if(epoch===generation.current&&!isAbort(e)){
    if(e instanceof ApiError&&[401,403,404].includes(e.status))discard();
    else setError(e);
   }
   throw e;
  }finally{locked.current=false;setBusy(false);}
 }
 return <PrivilegedContext.Provider value={{grant,restoring:restoring||unresolved||!!(discovered&&discovered!==endedContext&&grant?.context_id!==discovered),busy,error,start,startMaintenance,end,retry:restore}}>{children}</PrivilegedContext.Provider>;
}
