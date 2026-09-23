import { useEffect, useState } from 'react';
import { useAuth } from '../auth/state';
import ErrorNotice from '../api/ErrorNotice';
import { isAbort } from '../api/errors';
import { useAccessContext } from './state';
import { environmentLabel } from './labels';
type Contract = {
    id: string;
    tenant_name: string;
    code: string;
    environment: string;
    modules?: string[];
};
export default function ContractPicker() {
    const { api, user, busy: authBusy } = useAuth(), { select, busy } = useAccessContext();
    const [search, setSearch] = useState(''), [offset, setOffset] = useState(0), [version, setVersion] = useState(0);
    const [items, setItems] = useState<Contract[]>([]), [loading, setLoading] = useState(true), [error, setError] = useState<unknown>(null);
    useEffect(() => {
        const controller = new AbortController();
        api.request<{
            items: Contract[];
        }>(`/contracts?search=${encodeURIComponent(search)}&limit=50&offset=${offset}`, { contextId: null, signal: controller.signal })
            .then(result => { if (!controller.signal.aborted) {
            setItems(result.items);
            setError(null);
        } })
            .catch(e => { if (!isAbort(e))
            setError(e); })
            .finally(() => { if (!controller.signal.aborted)
            setLoading(false); });
        return () => controller.abort();
    }, [api, search, offset, version]);
    return <section className="portal-content" aria-labelledby="picker-title">
  <p className="eyebrow">Bem-vindo, {user?.display_name}</p><h1 id="picker-title">Selecionar ambiente</h1>
  <p>Selecione a empresa e o contrato que deseja acessar.</p>
  <label htmlFor="contract-search">Pesquisar empresa ou código do contrato</label>
  <input id="contract-search" type="search" maxLength={128} value={search} onChange={e => { setLoading(true); setItems([]); setError(null); setSearch(e.target.value); setOffset(0); }}/>
  <ErrorNotice error={error}/>{!!error && <button onClick={() => { setLoading(true); setError(null); setVersion(v => v + 1); }}>Tentar novamente</button>}
  {loading ? <p role="status">Carregando contratos…</p> : !error && items.length === 0 ? <p role="status">Nenhum contrato disponível para esta pesquisa.</p> : null}
  <div className="contract-grid">{items.map(contract => <article className="contract-card" key={contract.id}>
   <h2>{contract.tenant_name}</h2><dl><div><dt>Contrato</dt><dd>{contract.code}</dd></div><div><dt>Ambiente</dt><dd>{environmentLabel(contract.environment)}</dd></div><div><dt>Status</dt><dd>Ativo</dd></div></dl>
   {contract.modules && <p>Módulos: {contract.modules.join(', ')}</p>}
   <button className="primary" aria-label={`Acessar contrato ${contract.code}`} disabled={busy || authBusy} onClick={() => void select(contract.id)}>{busy ? 'Acessando…' : 'Acessar contrato'}</button>
  </article>)}</div>
  <nav aria-label="Páginas de contratos"><button disabled={offset === 0 || loading} onClick={() => { setLoading(true); setItems([]); setOffset(v => Math.max(0, v - 50)); }}>Anterior</button><button disabled={items.length < 50 || loading || offset >= 10000} onClick={() => { setLoading(true); setItems([]); setOffset(v => v + 50); }}>Próxima</button></nav>
 </section>;
}
