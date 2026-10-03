import {useEffect,useState} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext} from '../platform/state';
import {usePrivileged} from '../privileged/state';
import {ApiError,isAbort} from '../api/errors';
import ErrorNotice from '../api/ErrorNotice';
import {useMaintenanceAdapters,type MaintenanceAction} from './registry';
import RequestMaintenanceDialog from './RequestMaintenanceDialog';
import ProcessingPage from './ProcessingPage';
import './Maintenance.css';
export default function MaintenancePage(){
 const {api,user}=useAuth(),{selected}=useAccessContext(),privileged=usePrivileged()!,adapters=useMaintenanceAdapters();
 const grant=privileged.grant,contextId=grant?.context_id??selected?.id,retry=privileged.retry;
 const [result,setResult]=useState<{contextId:string|undefined;items:MaintenanceAction[];error:unknown}|null>(null),[revision,setRevision]=useState(0),[chosen,setChosen]=useState<MaintenanceAction|null>(null);
 useEffect(()=>{const abort=new AbortController();api.request<{items:MaintenanceAction[];mode:'NORMAL'|'MAINTENANCE'}>('/maintenance',{contextId,signal:abort.signal}).then(value=>{if(!abort.signal.aborted)setResult({contextId,items:value.items,error:null});}).catch(error=>{if(!abort.signal.aborted&&!isAbort(error)){if(grant&&error instanceof ApiError&&[401,403,404].includes(error.status))retry();setResult({contextId,items:[],error});}});return()=>abort.abort();},[api,contextId,revision,grant,retry]);
 if(user?.platform_role!=='PLATFORM_ADMIN')return null;
 const current=result?.contextId===contextId?result:null,items=current?.items.filter(action=>adapters.some(a=>a.actionCode===action.action_code&&a.entityType===action.entity_type))??[];
 return <section className="maintenance-page"><h2>Manutenção</h2><p>Operações registradas e autorizadas para o contrato atual.</p><ErrorNotice error={current?.error}/>{!current?<p role="status">Carregando operações de manutenção…</p>:current.error?<button onClick={()=>setRevision(v=>v+1)}>Tentar novamente</button>:items.length===0?<p>Nenhuma operação de manutenção está disponível para este contrato.</p>:<>{!grant&&<ul>{items.map(action=><li key={action.action_code}><strong>{action.label}</strong><button onClick={()=>setChosen(action)}>Solicitar acesso de manutenção</button></li>)}</ul>}{grant?.grant_type==='MAINTENANCE'&&items.map(action=>{const adapter=adapters.find(a=>a.actionCode===action.action_code)!;const scope=grant.scopes.find(s=>s.action_code===action.action_code&&s.entity_type===action.entity_type);return scope?.entity_id&&action.can_correct?<adapter.Form key={action.action_code} action={action} entityId={scope.entity_id}/>:null;})}</>}<ProcessingPage/>{chosen&&!grant&&<RequestMaintenanceDialog action={chosen} onClose={()=>setChosen(null)}/>}</section>;
}
