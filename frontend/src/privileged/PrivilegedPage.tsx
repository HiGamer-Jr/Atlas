import { useEffect, useState } from 'react';
import { useAuth } from '../auth/state';
import { useAccessContext } from '../platform/state';
import ErrorNotice from '../api/ErrorNotice';
import { isAbort } from '../api/errors';
import RequestGrantDialog from './RequestGrantDialog';
import type { Grant } from './types';
// Initial and contextual loads clear stale history before the server response.
// eslint-disable-next-line react/set-state-in-effect
export default function PrivilegedPage() { const { api, user } = useAuth(), { selected } = useAccessContext(); const [dialog, setDialog] = useState(false), [items, setItems] = useState<Grant[]>([]), [total, setTotal] = useState(0), [offset, setOffset] = useState(0), [revision, setRevision] = useState(0), [loading, setLoading] = useState(true), [error, setError] = useState<unknown>(null), [actions, setActions] = useState<unknown[] | null>(null); useEffect(() => { const abort = new AbortController(); let current = true; setLoading(true); setError(null); Promise.all([api.request<{
        items: Grant[];
        total: number;
    }>(`/grants?limit=20&offset=${offset}`, { contextId: selected?.id, signal: abort.signal }), api.request<{
        items: unknown[];
    }>('/grants/maintenance-actions', { contextId: selected?.id, signal: abort.signal })]).then(([history, catalog]) => { if (current) {
    setItems(history.items);
    setTotal(history.total);
    setActions(catalog.items);
} }).catch(e => { if (current && !isAbort(e))
    setError(e); }).finally(() => { if (current)
    setLoading(false); }); return () => { current = false; abort.abort(); }; }, [api, selected?.id, offset, revision]); if (user?.platform_role !== 'PLATFORM_ADMIN')
    return null; return <section className="privileged-page"><h2>Acessos Temporários</h2><p>Acessos excepcionais vinculados ao operador, à sessão e ao contrato atual.</p><button onClick={() => setDialog(true)}>Solicitar acesso Financeiro/Fiscal</button><h3>Manutenção autorizada</h3>{actions?.length === 0 && <p>Nenhuma operação de manutenção está disponível nesta versão.</p>}<h3>Histórico contextual</h3><ErrorNotice error={error}/>{loading ? <p role="status">Carregando acessos temporários…</p> : error ? <button onClick={() => setRevision(v => v + 1)}>Tentar novamente</button> : items.length === 0 ? <p>Nenhuma concessão registrada neste contexto.</p> : <ul className="grant-history">{items.map(item => <li key={item.id}><strong>{item.grant_type === 'FINANCIAL_FISCAL' ? 'Financeiro/Fiscal' : 'Manutenção'}</strong><p>Operador: {item.operator.display_name}</p><p>Status: {({ ACTIVE: 'Ativo', ENDED: 'Encerrado', REVOKED: 'Revogado', EXPIRED: 'Expirado' } as Record<string, string>)[item.status] ?? 'Indisponível'}</p><p>Início: {new Date(item.started_at).toLocaleString('pt-BR',{timeZoneName:'short'})} · Expiração: {new Date(item.expires_at).toLocaleString('pt-BR',{timeZoneName:'short'})}</p><p>Motivo: {item.reason}</p><p>Referência: {item.reference ?? 'Não informada'}</p></li>)}</ul>}<div className="pagination"><button disabled={loading || offset === 0} onClick={() => setOffset(v => Math.max(0, v - 20))}>Página anterior</button><span>{total} concessões</span><button disabled={loading || offset + 20 >= total} onClick={() => setOffset(v => v + 20)}>Próxima página</button></div>{dialog && <RequestGrantDialog onClose={() => setDialog(false)}/>}</section>; }
