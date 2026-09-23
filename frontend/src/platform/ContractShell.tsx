import { useAuth } from '../auth/state';
import { useAccessContext } from './state';
import { environmentLabel } from './labels';
export default function ContractShell() {
    const { user, busy: authBusy } = useAuth(), { selected, clear, busy } = useAccessContext();
    if (!selected)
        return null;
    const admin = user?.platform_role === 'PLATFORM_ADMIN';
    return <>
  <header className="context-header" data-testid="contract-context"><dl>
   <div><dt>Empresa</dt><dd>{selected.tenant_name}</dd></div>
   <div><dt>Contrato</dt><dd>{selected.contract_code}</dd></div>
   <div><dt>Ambiente</dt><dd>{environmentLabel(selected.environment)}</dd></div>
  </dl><button disabled={busy || authBusy} onClick={() => void clear()}>{busy ? 'Encerrando contexto…' : 'Trocar empresa/contrato'}</button></header>
  <section className="portal-content"><p className="eyebrow">Portal interno</p><h1>{admin ? 'Administração HiAtlas' : 'Suporte HiAtlas'}</h1>
   <div className="portal-placeholder"><h2>{admin ? 'Administração do ambiente' : 'Atendimento ao cliente'}</h2><p>{admin ? 'Áreas administrativas serão disponibilizadas nas próximas fases.' : 'Ferramentas de suporte serão disponibilizadas nas próximas fases.'}</p></div>
  </section>
 </>;
}
