import {useEffect,useRef,useState} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext} from '../platform/state';
import {usePrivileged} from '../privileged/state';
import {isAbort} from '../api/errors';
import ErrorNotice from '../api/ErrorNotice';
import AccessDialog from '../platform/access/AccessDialog';
import type {MaintenanceAction} from './registry';
export default function RequestMaintenanceDialog({action,onClose}:{action:MaintenanceAction;onClose:()=>void}){
 const {api,user}=useAuth(),{selected}=useAccessContext(),state=usePrivileged()!;
 const [entityId,setEntityId]=useState(''),[reason,setReason]=useState(''),[reference,setReference]=useState(''),[password,setPassword]=useState(''),[review,setReview]=useState(false),[busy,setBusy]=useState(false),[error,setError]=useState<unknown>(null);
 const abort=useRef<AbortController|null>(null),confirmation=useRef<HTMLButtonElement>(null);
 useEffect(()=>{if(review)confirmation.current?.focus();},[review]);
 useEffect(()=>{const controller=new AbortController();abort.current=controller;return()=>controller.abort();},[]);
 async function reauth(){const controller=abort.current!;setBusy(true);setError(null);const secret=password;setPassword('');try{await api.request('/auth/reauthenticate',{method:'POST',contextId:selected?.id,signal:controller.signal,body:{password:secret}});if(!controller.signal.aborted)setReview(true);}catch(e){if(!controller.signal.aborted&&!isAbort(e))setError(e);}finally{if(!controller.signal.aborted)setBusy(false);}}
 return <AccessDialog title={review?'Revisar acesso de manutenção':'Solicitar acesso de manutenção'} onClose={onClose} busy={busy||state.busy}><ErrorNotice error={error??state.error}/>{review?<><p>Operador: {user?.display_name}</p><p>Ação: {action.label}</p><p>Entidade: {entityId.trim()}</p><p>Motivo: {reason.trim()}</p><p>Referência: {reference.trim()}</p><p>A concessão autoriza somente a ação e a entidade revisadas, durante o prazo definido pelo servidor.</p><button ref={confirmation} disabled={state.busy} onClick={()=>void state.startMaintenance(reason.trim(),reference.trim(),[{action_code:action.action_code,entity_type:action.entity_type,entity_id:entityId.trim()}]).then(onClose).catch(e=>{if(!abort.current?.signal.aborted){setError(e);setReview(false);}})}>Confirmar acesso de manutenção</button></>:<form onSubmit={e=>{e.preventDefault();void reauth();}}><p>Ação: {action.label}</p><label htmlFor="maintenance-entity">Entidade autorizada</label><input id="maintenance-entity" required value={entityId} onChange={e=>setEntityId(e.target.value)}/><label htmlFor="maintenance-reason">Motivo do acesso de manutenção</label><textarea id="maintenance-reason" required minLength={3} maxLength={1000} value={reason} onChange={e=>setReason(e.target.value)}/><label htmlFor="maintenance-reference">Referência / chamado obrigatório</label><input id="maintenance-reference" required maxLength={100} value={reference} onChange={e=>setReference(e.target.value)}/><label htmlFor="maintenance-password">Confirme sua senha</label><input id="maintenance-password" type="password" autoComplete="current-password" required value={password} onChange={e=>setPassword(e.target.value)}/><button disabled={busy||!entityId.trim()||reason.trim().length<3||!reference.trim()||!password}>Reautenticar e revisar</button></form>}</AccessDialog>;
}
