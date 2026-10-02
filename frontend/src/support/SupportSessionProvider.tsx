import {useCallback,useEffect,useRef,useState,type ReactNode} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext,type AccessContext} from '../platform/state';
import {ApiError,isAbort} from '../api/errors';
import type {SupportSession} from './types';
import {readSupport,storeSupport} from './storage';
import {SupportContext} from './state';
export function SupportSessionProvider({children}:{children:ReactNode}){
 const {api,user,busy:authBusy}=useAuth();
 const {selected,invalidate:discardParent,retry:refreshParent,registerSupport}=useAccessContext();
 const parentId=selected?.id,contractId=selected?.contract_id,operatorId=user?.user_id;
 const discovered=selected?.support_session_id;
 const [session,setSession]=useState<SupportSession|null>(null);
 const [restoring,setRestoring]=useState(()=>!!(discovered||readSupport()));
 const [revision,setRevision]=useState(0);
 const [busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null);
 const generation=useRef(0),locked=useRef(false),active=useRef<SupportSession|null>(null);
 const controller=useRef<AbortController|null>(null),returnFocus=useRef(false),ended=useRef<string|null>(null);
 const invalidate=useCallback(()=>{
  generation.current++;controller.current?.abort();api.cancelContext();active.current=null;
  storeSupport(null);setSession(null);setRestoring(false);setBusy(false);setError(null);discardParent?.('Sessão de suporte encerrada, expirada ou indisponível. Selecione um ambiente para continuar.');
 },[api,discardParent]);
 const validate=useCallback((value:SupportSession)=>{
  if(!parentId||value.parent_context_id!==parentId||value.contract_id!==contractId||value.operator?.user_id!==operatorId||value.mode!=='READ_ONLY'||value.status!=='ACTIVE'||!value.context_id||!value.viewed?.display_name||!Number.isFinite(Date.parse(value.expires_at))||Date.parse(value.expires_at)<=Date.now())throw new ApiError(403);
  return value;
 },[parentId,contractId,operatorId]);
 const verify=useCallback(async(id:string,signal:AbortSignal)=>{
  const current=generation.current;
  try{
   const value=validate(await api.request<SupportSession>(`/support-sessions/${encodeURIComponent(id)}`,{contextId:parentId,signal}));
   if(current!==generation.current||signal.aborted)return;
   active.current=value;registerSupport?.(value.id);storeSupport(value.id);setSession(value);setRevision(value=>value+1);setRestoring(false);setError(null);
  }catch(e){
   if(signal.aborted||current!==generation.current||isAbort(e))return;
   if(e instanceof ApiError&&[401,403,404].includes(e.status))invalidate();
   else{setError(e);setRestoring(true);}
  }
 },[api,parentId,validate,invalidate,registerSupport]);
 const recover=useCallback(async()=>{
  const current=generation.current;
  controller.current?.abort();const abort=new AbortController();controller.current=abort;
  setRestoring(true);
  try{
   const parent=await api.request<AccessContext>('/context',{contextId:parentId,signal:abort.signal});
   if(abort.signal.aborted||current!==generation.current)return;
   if(parent.id!==parentId)throw new ApiError(403);
   const id=parent.support_session_id??active.current?.id;
   if(id)await verify(id,abort.signal);
   else{storeSupport(null);setRestoring(false);}
  }catch(e){
   if(abort.signal.aborted||current!==generation.current||isAbort(e))return;
   if(e instanceof ApiError&&[401,403,404].includes(e.status))invalidate();
   else setError(e);
  }
 },[api,parentId,verify,invalidate]);
 useEffect(()=>{
  if(authBusy)return;
  const id=active.current?.id??(discovered!==ended.current?discovered:null)??readSupport();if(!id)return;
  const abort=new AbortController();controller.current=abort;void verify(id,abort.signal);
  return()=>abort.abort();
 },[authBusy,discovered,verify]);
 useEffect(()=>{
  const focus=()=>{if(locked.current||authBusy)return;const id=active.current?.id;if(!id)return;controller.current?.abort();const abort=new AbortController();controller.current=abort;void verify(id,abort.signal);};
  window.addEventListener('focus',focus);return()=>window.removeEventListener('focus',focus);
 },[verify,authBusy]);
 useEffect(()=>()=>{
  // This ref is a request epoch, not a DOM node; its latest value invalidates all pending responses.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  generation.current++;
  // eslint-disable-next-line react-hooks/exhaustive-deps
  controller.current?.abort();
 },[]);
 useEffect(()=>{
  if(!session)return;
  const timer=window.setTimeout(()=>{
   const id=session.id;invalidate();
   // Observe the terminal boundary once; no polling or session renewal.
   void api.request(`/support-sessions/${encodeURIComponent(id)}`,{contextId:session.parent_context_id}).catch(()=>{});
  },Math.min(Math.max(Date.parse(session.expires_at)-Date.now(),0),2147483647));
  return()=>window.clearTimeout(timer);
 },[session,api,invalidate]);
 useEffect(()=>{if(returnFocus.current&&!session&&!restoring&&!busy){returnFocus.current=false;document.querySelector<HTMLElement>('[data-support-return]')?.focus();}},[session,restoring,busy]);
 async function start(membership:string,reason:string,reference:string|null){
  if(!parentId||locked.current||active.current)return;
  locked.current=true;setBusy(true);setError(null);const current=++generation.current;
  controller.current?.abort();api.cancelContext();
  try{
   const value=validate(await api.request<SupportSession>('/support-sessions',{method:'POST',contextId:parentId,body:{membership_id:membership,reason,reference,mode:'READ_ONLY'}}));
   if(current!==generation.current)return;
   api.cancelContext();active.current=value;registerSupport?.(value.id);storeSupport(value.id);setSession(value);
  }catch(e){
   if(current===generation.current){
    if(e instanceof ApiError&&e.status===401)invalidate();
    else{if(!isAbort(e))setError(e);await recover();}
   }
   throw e;
  }finally{locked.current=false;setBusy(false);}
 }
 async function end(){
  const value=active.current;if(!value||locked.current)return;
  locked.current=true;setBusy(true);setError(null);const current=++generation.current;
  controller.current?.abort();api.cancelContext();
  try{
   await api.request(`/support-sessions/${encodeURIComponent(value.id)}/end`,{method:'POST',contextId:value.parent_context_id});
   if(current!==generation.current)return;
   api.cancelContext();ended.current=value.id;active.current=null;registerSupport?.(null);storeSupport(null);refreshParent();returnFocus.current=true;setSession(null);setRestoring(false);
  }catch(e){
   if(e instanceof ApiError&&[401,403,404].includes(e.status))invalidate();
   else if(!isAbort(e))setError(e);
   throw e;
  }finally{locked.current=false;setBusy(false);}
 }
 return <SupportContext.Provider value={{session,revision,busy,restoring:restoring||!!(discovered&&discovered!==ended.current&&session?.id!==discovered),error,start,end,invalidate,retry:()=>void recover()}}>{children}</SupportContext.Provider>;
}
