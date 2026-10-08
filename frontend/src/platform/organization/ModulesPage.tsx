import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/state';
import { useAccessContext } from '../state';
import { ApiError, isAbort } from '../../api/errors';
import ErrorNotice from '../../api/ErrorNotice';
import AccessDialog from '../access/AccessDialog';
import { useScopedQuery } from '../access/useScopedQuery';
import type { Module } from './types';
function ModuleEditor({ module, onClose, onSaved, onRefresh }: {module:Module;onClose:()=>void;onSaved:()=>void;onRefresh:(discard?:boolean)=>void}) {
 const {api,user}=useAuth(), {selected}=useAccessContext();
 const query=useScopedQuery<{items:Module[]}>('/contract/modules');
 const [current,setCurrent]=useState(module),[contracted,setContracted]=useState(module.contracted),[active,setActive]=useState(module.active),[review,setReview]=useState(false),[error,setError]=useState<unknown>(null),[busy,setBusy]=useState(false),[conflict,setConflict]=useState(false),[refreshPending,setRefreshPending]=useState(false);
 const controller=useRef<AbortController|null>(null);
 const [initialized,setInitialized]=useState(false);
 useEffect(()=>()=>controller.current?.abort(),[]);
 useEffect(()=>{
  if(query.error instanceof ApiError && [401,403,404].includes(query.error.status)) {onClose();onRefresh(true);return;}
  if(query.data && !query.loading && !query.error) {
   const fresh=query.data.items.find(item=>item.code===module.code);
   if(!fresh) {onClose();onRefresh(true);return;}
   // Synchronize the form with a successful scoped catalog refresh.
   // eslint-disable-next-line react/set-state-in-effect
   if(!initialized || refreshPending) {setInitialized(true);setCurrent(fresh);setContracted(fresh.contracted);setActive(fresh.active);if(refreshPending) {setReview(false);setConflict(false);setRefreshPending(false);setError(null);}}
  }
 },[query.data,query.loading,query.error,module.code,refreshPending,initialized,onClose,onRefresh]);
 const permitted=user?.platform_role==='PLATFORM_ADMIN' && selected?.capabilities.includes('modules.manage') && current.allowed_actions.includes('edit');
 const blocked=!initialized || busy || conflict || refreshPending || query.loading || !!query.error || !permitted;
 async function save() {
  if(!selected || blocked) return;
  setBusy(true);setError(null);controller.current=new AbortController();
  try {await api.request(`/contract/modules/${encodeURIComponent(current.code)}`,{method:'PATCH',body:{contracted,active,expected_version:current.version,module_id:current.id},contextId:selected.id,signal:controller.current.signal});if(!controller.current.signal.aborted) onSaved();}
  catch(e) {if(!isAbort(e)) {setError(e);if(e instanceof ApiError && [401,403,404].includes(e.status)) {onClose();onRefresh(true);}else if(e instanceof ApiError && e.status===409) {setConflict(true);onRefresh();query.retry();}}}
  finally {if(!controller.current?.signal.aborted) setBusy(false);}
 }
 return <AccessDialog title={review?'Confirmar módulo':`Configurar ${current.label}`} onClose={onClose} busy={busy}>{review?<><p><strong>{current.label}</strong> ({current.code})</p><p>Estado atual: contratado {current.contracted?'Sim':'Não'} · ativo {current.active?'Sim':'Não'} · versão {current.version}.</p><p>Contratado: {contracted?'Sim':'Não'} · Ativo: {active?'Sim':'Não'}</p><p>{current.operational_available?'Disponibilidade operacional informada pelo servidor.':'Operação indisponível nesta fase. A configuração registra o contrato e o estado; o domínio operacional ainda não está disponível.'}</p>{!active && current.active && <p>A inativação revoga a disponibilidade do módulo neste contrato.</p>}{!contracted && current.contracted && <p>O módulo deixará de ser contratado e ativo neste contrato.</p>}<p>A configuração não concede permissões aos usuários. Acesso continua sujeito às capacidades autorizadas.</p><ErrorNotice error={error}/><ErrorNotice error={query.error}/>{query.loading && <p role="status">Atualizando módulo…</p>}{conflict?<><p>Carregue o estado atual e revise o módulo novamente.</p><button disabled={busy || query.loading} onClick={()=>{setRefreshPending(true);query.retry();}}>Atualizar dados</button></>:<button disabled={busy} onClick={()=>setReview(false)}>Voltar aos campos</button>}<button disabled={blocked} onClick={()=>void save()}>{busy?'Processando…':'Confirmar'}</button></>:<form onSubmit={event=>{event.preventDefault();if(!blocked)setReview(true);}}><p>{current.label} ({current.code})</p><label className="check-label"><input aria-label="Módulo contratado" type="checkbox" checked={contracted} disabled={blocked} onChange={event=>{setContracted(event.target.checked);if(!event.target.checked)setActive(false);}}/>Módulo contratado</label><label className="check-label"><input aria-label="Módulo ativo" type="checkbox" checked={active} disabled={blocked || !contracted} onChange={event=>setActive(event.target.checked)}/>Módulo ativo</label><p>Ativo exige contratado. Contratação e ativação são estados independentes.</p>{!current.operational_available && <p>Operação indisponível nesta fase.</p>}<ErrorNotice error={query.error}/>{query.loading && <p role="status">Atualizando módulo…</p>}<button disabled={blocked}>Revisar módulo</button></form>}</AccessDialog>;
}
export default function ModulesPage() {
 const {user}=useAuth(),{selected}=useAccessContext();
 const {data,error,loading,retry,discardAndRetry}=useScopedQuery<{items:Module[]}>('/contract/modules');
 const [editor,setEditor]=useState<Module|null>(null),[notice,setNotice]=useState('');
 const manage=user?.platform_role==='PLATFORM_ADMIN' && selected?.capabilities.includes('modules.manage');
 return <section className="access-page"><div className="page-title"><div><h2>Módulos</h2><p>Catálogo e estados dos módulos neste contrato.</p></div></div>{!manage && <p>Consulta de módulos. Alterações disponíveis somente para administradores autorizados.</p>}{notice && <p role="status">{notice}</p>}{loading && <p role="status">Carregando módulos…</p>}<ErrorNotice error={error}/>{!!error && <button onClick={retry}>Tentar novamente</button>}{data && (data.items.length===0?<p>Nenhum módulo disponível neste contexto.</p>:<div className="module-grid">{data.items.map(item=><article key={item.code} className="module-card"><h3>{item.label}</h3><div className="module-state"><p>Contratado: {item.contracted?'Sim':'Não'}</p><p>Ativo: {item.active?'Sim':'Não'}</p><p>{item.operational_available?(item.enabled?'Operação disponível.':'Operação desabilitada neste contrato.'):'Operação indisponível nesta fase.'}</p></div>{manage && item.allowed_actions.includes('edit') && <button aria-label={`Configurar ${item.label}`} disabled={loading || !!error} onClick={()=>{setEditor(item);setNotice('');}}>Configurar {item.label}</button>}</article>)}</div>)}{editor && manage && <ModuleEditor key={editor.code} module={editor} onClose={()=>setEditor(null)} onRefresh={discard=>discard?discardAndRetry():retry()} onSaved={()=>{setEditor(null);setNotice('Módulo salvo.');retry();}}/>}</section>;
}
