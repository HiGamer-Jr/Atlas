import { SupportSessionProvider } from '../support/SupportSessionProvider';
import { useSupport } from '../support/state';
import SupportBanner from '../support/SupportBanner';
import Workspace from '../support/Workspace';
import SupportSessionHistory from '../support/SupportSessionHistory';
import ErrorNotice from '../api/ErrorNotice';
import '../support/Support.css';
import { useState } from 'react';
import { useAuth } from '../auth/state';
import { useAccessContext } from './state';
import { environmentLabel } from './labels';
import UsersPage from './access/UsersPage';
import RolesPage from './access/RolesPage';
import AuditPage from '../audit/AuditPage';
import OrganizationPage from './organization/OrganizationPage';
import ModulesPage from './organization/ModulesPage';
import './organization/Organization.css';
import './access/Access.css';
function Tools({ admin, capabilities }: {
    admin: boolean;
    capabilities: string[];
}) {
    const [page, setPage] = useState('users');
    const tools = [...(capabilities.includes('memberships.read') ? [{ id: 'users', name: 'Usuários' }] : []), ...(admin && capabilities.includes('roles.read') ? [{ id: 'roles', name: 'Perfis' }] : []), ...(admin && capabilities.includes('organization.manage') ? [{ id: 'organization', name: 'Estrutura' }] : []), ...(capabilities.includes('modules.read') ? [{ id: 'modules', name: 'Módulos' }] : []), ...(capabilities.includes('support.history.read') ? [{ id: 'support-history', name: 'Sessões de suporte' }] : []), ...(capabilities.includes('audit.read') ? [{ id: 'audit', name: admin ? 'Auditoria' : 'Histórico' }] : [])];
    const current = tools.find(tool => tool.id === page)?.id ?? tools[0]?.id;
    return <>{tools.length > 0 ? <><nav className="access-nav" aria-label="Ferramentas do contexto">{tools.map(tool => <button aria-current={current === tool.id ? 'page' : undefined} key={tool.id} onClick={() => setPage(tool.id)}>{tool.name}</button>)}</nav>{current === 'users' ? <UsersPage /> : current === 'roles' ? <RolesPage /> : current === 'organization' ? <OrganizationPage /> : current === 'modules' ? <ModulesPage /> : current === 'support-history' ? <SupportSessionHistory /> : <AuditPage />}</> : <p>Nenhuma ferramenta disponível neste contexto.</p>}</>;
}
function Shell() { const { user, busy: authBusy } = useAuth(), { selected, clear, busy } = useAccessContext(); const support=useSupport(); if(support?.session) return <><SupportBanner/>{support.restoring?<section className='portal-content'><p role='status'>Validando sessão de suporte…</p><button onClick={support.retry}>Validar sessão de suporte novamente</button></section>:<Workspace/>}</>; if(support?.restoring) return <section className='portal-content'><p role='status'>Validando sessão de suporte…</p><ErrorNotice error={support.error}/>{!!support.error&&<button onClick={support.retry}>Validar sessão de suporte novamente</button>}</section>; if(support?.busy) return <p role='status'>Iniciando sessão de suporte…</p>; if (!selected)
    return null; const admin = user?.platform_role === 'PLATFORM_ADMIN'; return <><ErrorNotice error={support?.error}/><header className="context-header" data-testid="contract-context"><dl><div><dt>Empresa</dt><dd>{selected.tenant_name}</dd></div><div><dt>Contrato</dt><dd>{selected.contract_code}</dd></div><div><dt>Ambiente</dt><dd>{environmentLabel(selected.environment)}</dd></div></dl><button disabled={busy || authBusy} onClick={() => void clear()}>{busy ? 'Encerrando contexto…' : 'Trocar empresa/contrato'}</button></header><section className="portal-content"><p className="eyebrow">Portal interno</p><h1 tabIndex={-1} data-support-return>{admin ? 'Administração HiAtlas' : 'Suporte HiAtlas'}</h1><Tools key={selected.id} admin={admin} capabilities={selected.capabilities ?? []}/></section></>; }

export default function ContractShell(){const {selected}=useAccessContext();return selected?<SupportSessionProvider key={selected.id}><Shell/></SupportSessionProvider>:null;}
