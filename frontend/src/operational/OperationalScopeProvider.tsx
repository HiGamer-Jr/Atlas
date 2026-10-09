import {useEffect,useMemo,useState,type ReactNode} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext} from '../platform/state';
import {ApiError} from '../api/errors';
import {OperationalContext,type OperationalScopeState} from './state';
import {parseOperationalScope} from './validate';

export function OperationalScopeProvider({children}:{children:ReactNode}){
 const {api,user,loading:authLoading}=useAuth();const {selected,loading,recovering,busy}=useAccessContext();
 const customer=!!user&&user.platform_role===null;
 // Every lifecycle transition invalidates the old snapshot before effects run.
 const binding=useMemo(()=>({selected,customer,loading,authLoading,recovering,busy}),[selected,customer,loading,authLoading,recovering,busy]);
 const [result,setResult]=useState<{binding:typeof binding|null;state:OperationalScopeState}>({binding:null,state:{status:'idle',scope:null}});
 useEffect(()=>{
  const id=binding.selected?.id;
  if(!binding.customer||!id||binding.loading||binding.authLoading||binding.recovering||binding.busy)return;
  let disposed=false;let controller:AbortController|null=null;
  async function refresh(){controller?.abort();controller=new AbortController();const request=controller;setResult({binding,state:{status:'loading',scope:null}});
   try{const wire=await api.request<unknown>('/context/operational-scope',{contextId:id,signal:request.signal});const scope=parseOperationalScope(wire,id!);
    if(scope.actor_kind!=='TENANT'||scope.contract.id!==binding.selected!.contract_id)throw new Error('OPERATIONAL_SCOPE_INVALID');
    if(!disposed&&!request.signal.aborted)setResult({binding,state:{status:'ready',scope}});
   }catch(error){if(disposed||request.signal.aborted)return;setResult({binding,state:{status:'unavailable',scope:null,errorCode:error instanceof ApiError?error.code:'OPERATIONAL_SCOPE_INVALID'}});}
  }
  const focus=()=>{void refresh();};const visibility=()=>{if(document.visibilityState==='visible')void refresh();};
  void refresh();window.addEventListener('focus',focus);document.addEventListener('visibilitychange',visibility);
  return()=>{disposed=true;controller?.abort();window.removeEventListener('focus',focus);document.removeEventListener('visibilitychange',visibility);};
 },[api,binding]);
 const exposed:OperationalScopeState=!customer||!selected?{status:'idle',scope:null}:loading||authLoading||recovering||busy||result.binding!==binding?{status:'loading',scope:null}:result.state;
 return <OperationalContext.Provider value={exposed}>{children}</OperationalContext.Provider>;
}
