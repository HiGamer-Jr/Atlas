import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/state';
import { useAccessContext } from '../state';
import { ApiError, isAbort } from '../../api/errors';
import ErrorNotice from '../../api/ErrorNotice';
import AccessDialog from '../access/AccessDialog';
import { useScopedQuery } from '../access/useScopedQuery';
import ParentOptions from './ParentOptions';
import { parentLabel, type NodeType, type OrganizationNode, type Parent } from './types';
type Action = 'create' | 'edit' | 'activate' | 'inactivate';
function physicalParent(node: OrganizationNode | null): Parent | null { return node?.parent_id ? {id:node.parent_id,name:node.parent_name ?? 'Pai indisponível',code:node.parent_code ?? '—'} : null; }
export default function NodeEditor({ node, action, types, onClose, onSaved, onRefresh }: {node:OrganizationNode|null; action:Action; types:NodeType[]; onClose:()=>void; onSaved:()=>void; onRefresh:(discard?:boolean)=>void}) {
 const {api} = useAuth(), {selected} = useAccessContext();
 const detail = useScopedQuery<OrganizationNode>(node ? `/organization/nodes/${encodeURIComponent(node.id)}` : null);
 const [current,setCurrent] = useState(node), [kind,setKind] = useState(node?.kind ?? types[0]?.kind ?? ''), [name,setName] = useState(node?.name ?? ''), [code,setCode] = useState(node?.code ?? ''), [parent,setParent] = useState<Parent|null>(physicalParent(node)), [active,setActive] = useState(action==='activate' ? true : action==='inactivate' ? false : node?.active ?? true);
 const [review,setReview] = useState(action==='activate'||action==='inactivate'), [busy,setBusy] = useState(false), [error,setError] = useState<unknown>(null), [conflict,setConflict] = useState(false), [refreshPending,setRefreshPending] = useState(false);
 const controller = useRef<AbortController|null>(null); const [initialized,setInitialized] = useState(false);
 useEffect(()=>()=>controller.current?.abort(),[]);
 useEffect(()=>{
  if(detail.error instanceof ApiError && [401,403,404].includes(detail.error.status)) { onClose(); onRefresh(true); return; }
  if(detail.data && !detail.loading && !detail.error && (!initialized || refreshPending)) {
   // This state marks completion of the validated scoped detail request.
   // eslint-disable-next-line react/set-state-in-effect
   setInitialized(true); const fresh=detail.data;
   // Synchronize the form with newly validated scoped server detail.
   // eslint-disable-next-line react/set-state-in-effect
   setCurrent(fresh);setKind(fresh.kind);setName(fresh.name);setCode(fresh.code);setParent(physicalParent(fresh));setActive(action==='activate' ? true : action==='inactivate' ? false : fresh.active);
   // Clear the review only after successful server synchronization.
   // eslint-disable-next-line react/set-state-in-effect
   if(refreshPending) { setReview(false);setConflict(false);setRefreshPending(false);setError(null); }
  }
 },[detail.data,detail.loading,detail.error,refreshPending,action,initialized,onClose,onRefresh]);
 const knownType = types.find(item=>item.kind===kind);
 const permitted = !!selected?.capabilities.includes('organization.manage') && (action==='create' || !!current?.allowed_actions.includes(action));
 const blocked = busy || conflict || refreshPending || !!detail.error || detail.loading || !permitted || !knownType;
 async function save() {
  if(!selected || blocked || !name.trim() || !code) return;
  setBusy(true);setError(null);controller.current=new AbortController();
  try {
   const fields = action==='edit' ? {name:name.trim(),parent_id:parent?.id ?? null,active,expected_version:current!.version} : action==='create' ? {kind,name:name.trim(),code,parent_id:parent?.id ?? null,active} : {active,expected_version:current!.version};
   await api.request(current ? `/organization/nodes/${encodeURIComponent(current.id)}` : '/organization/nodes',{method:current?'PATCH':'POST',body:fields,contextId:selected.id,signal:controller.current.signal});
   if(!controller.current.signal.aborted) onSaved();
  } catch(e) { if(!isAbort(e)) {setError(e);if(e instanceof ApiError && [401,403,404].includes(e.status)) {onClose();onRefresh(true);} else if(e instanceof ApiError && e.status===409) {if(current) {setConflict(true);onRefresh();detail.retry();} else {setReview(false);}}} }
  finally {if(!controller.current?.signal.aborted) setBusy(false);}
 }
 const title = review ? 'Confirmar unidade' : action==='create' ? 'Nova unidade' : action==='edit' ? 'Editar unidade' : action==='activate' ? 'Ativar unidade' : 'Inativar unidade';
 return <AccessDialog title={title} onClose={onClose} busy={busy}>{review ? <><p><strong>{name}</strong> ({code})</p><p>Tipo: {knownType?.label}</p><p>Pai: {parentLabel(parent)}</p><p>Estado proposto: {active?'Ativo':'Inativo'}</p><p>{current?.child_count ?? 0} filhos diretos · {current?.active_child_count ?? 0} filhos ativos · {current?.scope_membership_count ?? 0} escopos de vínculo ativos.</p>{current && <p>Estado atual: {current.active?'Ativo':'Inativo'} · Versão {current.version}</p>}{!active && <p>A inativação preserva o histórico. Filhos ou escopos ativos impedem a alteração.</p>}{active && <p>Ativação exige pai e ancestrais ativos. A alteração afeta somente a estrutura física deste contrato.</p>}{action==='edit' && <p>Revise a mudança de pai e o impacto na hierarquia existente.</p>}<ErrorNotice error={error}/><ErrorNotice error={detail.error}/>{detail.loading && <p role="status">Atualizando unidade…</p>}{conflict && <><p>Carregue os dados atuais e revise a unidade novamente.</p><button disabled={busy || detail.loading} onClick={()=>{setRefreshPending(true);detail.retry();}}>Atualizar dados</button></>}{!conflict && <button disabled={busy} onClick={()=>setReview(false)}>Voltar aos campos</button>}<button disabled={blocked} onClick={()=>void save()}>{busy?'Processando…':'Confirmar'}</button></> : <form onSubmit={event=>{event.preventDefault();if(!blocked)setReview(true);}}><label>Tipo de unidade<select aria-label="Tipo de unidade" value={kind} disabled={!!current || busy} onChange={event=>{setKind(event.target.value);setParent(null);}}>{types.map(item=><option key={item.kind} value={item.kind}>{item.label}</option>)}</select></label><label>Nome da unidade<input aria-label="Nome da unidade" required maxLength={200} disabled={busy || detail.loading || action==='activate'||action==='inactivate'} value={name} onChange={event=>setName(event.target.value)}/></label><label>Código<input aria-label="Código" required maxLength={64} disabled={!!current || busy} value={code} onChange={event=>setCode(event.target.value.toUpperCase())}/></label>{(action==='edit'||action==='create') && <ParentOptions key={kind} kind={kind} excluded={current?.id} value={parent} onChange={setParent} canHaveParent={!!knownType?.allowed_parent_kinds.length} disabled={busy || detail.loading || (!!current && !initialized)}/>}<label className="check-label"><input type="checkbox" aria-label="Unidade ativa" checked={active} disabled={busy || detail.loading || action==='activate'||action==='inactivate'} onChange={event=>setActive(event.target.checked)}/>Unidade ativa</label><ErrorNotice error={detail.error}/><ErrorNotice error={error}/>{detail.loading && <p role="status">Atualizando unidade…</p>}<button disabled={blocked || !name.trim() || !code}>Revisar unidade</button></form>}</AccessDialog>;
}
