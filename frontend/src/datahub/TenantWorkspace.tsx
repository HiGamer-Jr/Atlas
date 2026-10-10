import {Activity, useState} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext} from '../platform/state';
import {useOperationalScope} from '../operational/state';
import {environmentLabel} from '../platform/labels';
import ExcelPage from './ExcelPage';
import {RequestWorkspace} from '../procurement/requests/RequestWorkspace';
import {parseOperationalScope} from '../operational/validate';
import type {OperationalScope} from '../operational/types';

export default function TenantWorkspace() {
 const {selected, clear, busy} = useAccessContext();
 const {busy: authBusy} = useAuth();
 const state = useOperationalScope();
 let realScope:Extract<OperationalScope,{actor_kind:'TENANT'}>|null=null;
 try{if(state.status==='ready'&&selected){const parsed=parseOperationalScope(state.scope,selected.id);if(parsed.actor_kind==='TENANT'&&parsed.contract.id===selected.contract_id)realScope=parsed;}}catch{/* Invalid snapshots close navigation. */}
 const requests=!!realScope&&realScope.customer_scope.modules.some(m=>m.code==='PROCUREMENT'&&m.contracted&&m.active&&m.operational_available)&&realScope.customer_scope.organization_nodes.some(n=>n.kind!=='COMPANY')&&realScope.customer_scope.capabilities.some(c=>['procurement.requests.read_own','procurement.requests.read_unit'].includes(c));
 const [tool,setTool]=useState<'datahub'|'requests'>('datahub');
 const current=tool==='datahub'&&datahubAvailable(realScope)?'datahub':requests?'requests':'datahub';
 const datahub = !!realScope && realScope.customer_scope.modules.some(module => module.code === 'DATAHUB' && module.contracted && module.active && module.operational_available) && realScope.customer_scope.capabilities.includes('datahub.read');
 // A workflow identity preserves drafts only while the same validated scope refreshes.
 // It never opens controls; only the current ready server snapshot can do that.
 const signature = datahub || requests ? JSON.stringify(realScope!.customer_scope) : null;
 const [workflowSignature, setWorkflowSignature] = useState(signature);
 if (signature !== null && signature !== workflowSignature) setWorkflowSignature(signature);
 if (!selected) return null;
 const change = <button disabled={busy || authBusy} onClick={() => void clear()}>Trocar empresa/contrato</button>;
 const keepWorkflow = state.status === 'loading' || datahub;
 return <>
  {realScope ? <>
   <header className="context-header" data-testid="contract-context"><dl>
    <div><dt>Empresa</dt><dd>{realScope.tenant.name}</dd></div>
    <div><dt>Contrato</dt><dd>{realScope.contract.code}</dd></div>
    <div><dt>Ambiente</dt><dd>{environmentLabel(realScope.contract.environment)}</dd></div>
   </dl>{change}</header>
   <section className="portal-content"><h1>Ambiente do contrato</h1><p>{realScope.customer_scope.role.name}</p>
    <p>{realScope.customer_scope.unit_scope.mode === 'ALL' ? 'Escopo de unidades: acesso total às unidades disponíveis.' : `Escopo de unidades: ${realScope.customer_scope.organization_nodes.length} unidade(s) autorizada(s).`}</p>
    {datahub || requests ? <nav className="access-nav" aria-label="Ferramentas do contexto">{datahub && <button aria-current={current==="datahub"?"page":undefined} onClick={()=>setTool("datahub")}>Data Hub &gt; Excel</button>}{requests && <button aria-current={current==="requests"?"page":undefined} onClick={()=>setTool("requests")}>Solicitações de compra</button>}</nav> : <p>Nenhuma ferramenta disponível para suas permissões neste contexto.</p>}
   </section>
  </> : <section className="portal-content">
   {(state.status === 'unavailable' || state.status === 'ready') ? <><h1>Escopo operacional indisponível</h1><p>Não foi possível validar o escopo deste contrato. Nenhum controle operacional está disponível.</p></> : <p role="status">Validando escopo operacional…</p>}
   {change}
  </section>}
  {keepWorkflow && <Activity mode={datahub && current==='datahub' ? 'visible' : 'hidden'}><ExcelPage key={`${selected.id}:${workflowSignature}`} /></Activity>}
  {requests && <Activity mode={current==="requests"?"visible":"hidden"}><RequestWorkspace key={`${selected.id}:${workflowSignature}`} /></Activity>}
 </>;
}

function datahubAvailable(scope:Extract<OperationalScope,{actor_kind:'TENANT'}>|null){return !!scope&&scope.customer_scope.modules.some(m=>m.code==='DATAHUB'&&m.contracted&&m.active&&m.operational_available)&&scope.customer_scope.capabilities.includes('datahub.read');}
