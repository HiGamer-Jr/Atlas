import {Activity, useState} from 'react';
import {useAuth} from '../auth/state';
import {useAccessContext} from '../platform/state';
import {useOperationalScope} from '../operational/state';
import {environmentLabel} from '../platform/labels';
import ExcelPage from './ExcelPage';

export default function TenantWorkspace() {
 const {selected, clear, busy} = useAccessContext();
 const {busy: authBusy} = useAuth();
 const state = useOperationalScope();
 const realScope = state.status === 'ready' && state.scope.actor_kind === 'TENANT' ? state.scope : null;
 const datahub = !!realScope && realScope.customer_scope.modules.some(module => module.code === 'DATAHUB' && module.contracted && module.active && module.operational_available) && realScope.customer_scope.capabilities.includes('datahub.read');
 // A workflow identity preserves drafts only while the same validated scope refreshes.
 // It never opens controls; only the current ready server snapshot can do that.
 const signature = datahub ? JSON.stringify(realScope!.customer_scope) : null;
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
    {datahub ? <nav className="access-nav" aria-label="Ferramentas do contexto"><button aria-current="page">Data Hub &gt; Excel</button></nav> : <p>Nenhuma ferramenta disponível para suas permissões neste contexto.</p>}
   </section>
  </> : <section className="portal-content">
   {state.status === 'unavailable' ? <><h1>Escopo operacional indisponível</h1><p>Não foi possível validar o escopo deste contrato. Nenhum controle operacional está disponível.</p></> : <p role="status">Validando escopo operacional…</p>}
   {change}
  </section>}
  {keepWorkflow && <Activity mode={datahub ? 'visible' : 'hidden'}><ExcelPage key={`${selected.id}:${workflowSignature}`} /></Activity>}
 </>;
}
