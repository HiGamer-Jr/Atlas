import {useEffect,useState} from 'react';
import {useAuth} from '../auth/state';
import ErrorNotice from '../api/ErrorNotice';
import {ApiError,isAbort} from '../api/errors';
import type {WorkspaceView} from './types';
import {useSupport} from './state';
export default function Workspace(){
 const {api}=useAuth();const support=useSupport()!;const {session,busy,invalidate,revision:validationRevision}=support;
 const id=session?.id,contextId=session?.context_id;
 const [revision,setRevision]=useState(0);
 const key=`${id}:${contextId}:${busy}:${revision}:${validationRevision}`;
 const [result,setResult]=useState<{key:string;data:WorkspaceView|null;error:unknown}>({key:'',data:null,error:null});
 useEffect(()=>{
  if(!id||!contextId||busy)return;
  const abort=new AbortController();
  api.request<WorkspaceView>(`/support-sessions/${encodeURIComponent(id)}/workspace`,{contextId,signal:abort.signal}).then(value=>{
   if(abort.signal.aborted)return;
   if(value.effective_access?.read_only!==true||!Array.isArray(value.effective_access.capabilities)||!Array.isArray(value.modules))throw new ApiError(503);
   setResult({key,data:value,error:null});
  }).catch(error=>{
   if(isAbort(error)||abort.signal.aborted)return;
   if(error instanceof ApiError&&[401,403,404].includes(error.status))invalidate();
   else setResult({key,data:null,error});
  });
  return()=>abort.abort();
 },[api,id,contextId,busy,key,invalidate]);
 const data=result.key===key?result.data:null,error=result.key===key?result.error:null;
 return <section className="portal-content support-workspace"><h1>Ambiente do usuário</h1><p>Durante o atendimento, as áreas disponíveis podem ser consultadas. Alterações estão bloqueadas.</p><ErrorNotice error={error}/>{!!error&&<button onClick={()=>setRevision(value=>value+1)}>Tentar novamente</button>}{!data&&!error&&<p role="status">Validando ambiente…</p>}{data&&<>{data.modules.filter(module=>!['FINANCE','FISCAL','AUDIT'].includes(module.code)).map(module=><article className="support-module" key={module.code}><h2>{module.label}</h2><p>{module.contracted?'Módulo contratado':'Módulo não contratado'} · {module.active?'Ativo':'Inativo'}</p><p>Ambiente operacional indisponível</p></article>)}{data.modules.length===0&&<p>Nenhum ambiente operacional disponível neste contrato.</p>}</>}</section>;
}
