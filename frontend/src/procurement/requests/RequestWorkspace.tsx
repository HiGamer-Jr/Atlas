import {useEffect,useState} from 'react';
import {usePurchaseRequests} from './state';
import {RequestForm} from './RequestForm';
import {RequestDetail} from './RequestDetail';
import {statuses,type RequestPage} from './types';
import {errorText,isAbort} from '../../api/errors';
import './requests.css';
export function RequestWorkspace(){const p=usePurchaseRequests();const [visibility,setVisibility]=useState<'own'|'unit'>('own'),[status,setStatus]=useState(''),[node,setNode]=useState(''),[cursor,setCursor]=useState<string|undefined>(),[selected,setSelected]=useState<string|null>(null),[creating,setCreating]=useState(false),[page,setPage]=useState<{signature:string;value:RequestPage}|null>(null),[error,setError]=useState(''),[refresh,setRefresh]=useState(0);
 const binding=p.state.status==='ready'?p.state.binding:null;const signature=p.signature;const token=JSON.stringify([signature,visibility,status,node,cursor,refresh]);const [workflow,setWorkflow]=useState(signature);if(workflow!==signature){setWorkflow(signature);setSelected(null);setCreating(false);setPage(null);setCursor(undefined);setError('');}

 useEffect(()=>{if(!binding||!signature)return;let disposed=false;void p.run(signal=>p.api.list(binding,{visibility,...(status?{status}:{}),...(node?{node_id:node}:{}),...(cursor?{cursor}:{})},signal)).then(value=>{if(!disposed)setPage({signature:token,value});}).catch(e=>{if(!disposed&&!isAbort(e))setError(errorText(e));});return()=>{disposed=true;};},[p,binding,signature,token,visibility,status,node,cursor]);
 if(p.state.status!=='ready')return <section className="request-workspace"><h2>Solicitações de compra</h2><p role="status">{p.state.status==='loading'?'Validando escopo operacional…':'Solicitações indisponíveis neste contexto.'}</p></section>;
 if(creating)return <section className="request-workspace" key={signature}><button onClick={()=>setCreating(false)}>Voltar à lista</button><RequestForm draft={null} onSaved={r=>{setCreating(false);setSelected(r.id);setRefresh(v=>v+1);}}/></section>;
 if(selected)return <section className="request-workspace" key={signature}><button onClick={()=>{setSelected(null);setRefresh(v=>v+1);}}>Voltar à lista</button><RequestDetail requestId={selected}/></section>;
 const data=page?.signature===token?page.value:null;const loading=!data&&!error;
 return <section className="request-workspace"><h2>Solicitações de compra</h2><p>Registre necessidades reais. O atendimento é registrado manualmente.</p>{p.has('create')&&<button onClick={()=>setCreating(true)}>Nova solicitação</button>}<button onClick={()=>setRefresh(v=>v+1)}>Atualizar lista</button>
 <label>Visibilidade<select value={visibility} onChange={e=>{setVisibility(e.target.value as 'own'|'unit');setCursor(undefined);}}><option value="own">Minhas solicitações</option>{p.has('read_unit')&&<option value="unit">Fila da unidade</option>}</select></label>
 <label>Estado<select value={status} onChange={e=>{setStatus(e.target.value);setCursor(undefined);}}><option value="">Todos</option>{statuses.map(s=><option key={s}>{s}</option>)}</select></label><label>Unidade<select value={node} onChange={e=>{setNode(e.target.value);setCursor(undefined);}}><option value="">Todas autorizadas</option>{p.state.scope.customer_scope.organization_nodes.filter(n=>n.kind!=='COMPANY').map(n=><option key={n.id} value={n.id}>{n.name}</option>)}</select></label>
 {loading&&<p role="status">Carregando solicitações…</p>}{error&&<p role="alert">{error}</p>}{data&&<><p>{data.total} solicitação(ões)</p><ul>{data.items.map(r=><li key={r.id}><button onClick={()=>setSelected(r.id)}>{r.title}</button> — {r.status} — {r.requesting_node.name}<small>{r.id}</small></li>)}</ul>{data.next_cursor&&<button onClick={()=>setCursor(data.next_cursor!)}>Próxima página</button>}{cursor&&<button onClick={()=>setCursor(undefined)}>Primeira página</button>}</>}</section>;
}
