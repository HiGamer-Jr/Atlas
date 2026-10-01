import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../auth/state';
import { useAccessContext } from '../platform/state';
import { isAbort } from '../api/errors';
import ErrorNotice from '../api/ErrorNotice';
import AccessDialog from '../platform/access/AccessDialog';
import { useScopedQuery } from '../platform/access/useScopedQuery';
import { formatDate, timezone, type AuditPage as AuditResult, type AuditRow } from '../platform/access/types';
export default function AuditPage({ memberId }: {
    memberId?: string;
}) {
    const { user, api } = useAuth(), { selected } = useAccessContext();
    const admin = user?.platform_role === 'PLATFORM_ADMIN';
    const [action, setAction] = useState(''), [outcome, setOutcome] = useState(''), [from, setFrom] = useState(''), [to, setTo] = useState(''), [filters, setFilters] = useState(''), [cursor, setCursor] = useState(''), [previous, setPrevious] = useState<string[]>([]), [detail, setDetail] = useState<AuditRow | null>(null), [snapshot, setSnapshot] = useState<unknown>(null), [detailError, setDetailError] = useState<unknown>(null), [detailLoading, setDetailLoading] = useState(false);
    const controller = useRef<AbortController | null>(null);
    useEffect(() => () => controller.current?.abort(), []);
    const base = memberId ? `/memberships/${encodeURIComponent(memberId)}/access-history` : '/audit';
    const { data, error, loading, retry } = useScopedQuery<AuditResult>(`${base}?limit=20&cursor=${encodeURIComponent(cursor)}${filters}`);
    async function open(row: AuditRow) { if (!selected)
        return; controller.current?.abort(); controller.current = new AbortController(); const signal = controller.current.signal; setDetail(row); setSnapshot(null); setDetailError(null); setDetailLoading(true); try {
        const result = await api.request(`/audit/${encodeURIComponent(row.id)}`, { contextId: selected.id, signal });
        if (!signal.aborted)
            setSnapshot(result);
    }
    catch (e) {
        if (!isAbort(e) && !signal.aborted)
            setDetailError(e);
    }
    finally {
        if (!signal.aborted)
            setDetailLoading(false);
    } }
    function close() { controller.current?.abort(); setDetail(null); }
    return <section className="access-page"><h2>{memberId ? 'Histórico do vínculo' : admin ? 'Auditoria' : 'Histórico'}</h2><p>Eventos deste contrato · Fuso horário: {timezone}</p><form className="access-filters" onSubmit={event => { event.preventDefault(); const query = new URLSearchParams(); if (action.trim())
        query.set('action', action.trim()); if (outcome)
        query.set('outcome', outcome); if (from)
        query.set('from_at', new Date(from).toISOString()); if (to)
        query.set('to_at', new Date(to).toISOString()); setFilters(query.size ? `&${query}` : ''); setCursor(''); setPrevious([]); retry(); }}><label>Ação<input value={action} maxLength={100} onChange={event => setAction(event.target.value)}/></label><label>Resultado<select aria-label="Resultado" value={outcome} onChange={event => setOutcome(event.target.value)}><option value="">Todos</option><option value="SUCCESS">Sucesso</option><option value="DENIED">Negado</option><option value="FAILURE">Falha</option></select></label><label>De<input type="datetime-local" value={from} onChange={event => setFrom(event.target.value)}/></label><label>Até<input type="datetime-local" value={to} min={from || undefined} onChange={event => setTo(event.target.value)}/></label><button>Filtrar histórico</button></form>{loading && <p role="status">Carregando eventos…</p>}<ErrorNotice error={error}/>{!!error && <button onClick={retry}>Tentar novamente</button>}{data && <>{!data.items.length ? <p>Nenhum evento encontrado neste contexto.</p> : <div className="table-scroll" role="region" aria-label="Tabela de eventos do contrato" tabIndex={0}><table className="audit-table"><caption>Eventos no contexto selecionado</caption><thead><tr><th>Data</th><th>Ação / resultado</th><th>Ator</th><th>Entidade / referência</th><th>Requisição</th>{admin && <th>Detalhes</th>}</tr></thead><tbody>{data.items.map(row => <tr key={row.id}><td>{formatDate(row.occurred_at)}</td><td>{row.action}<br />{row.outcome}</td><td>{row.actor_name ?? 'Ator indisponível'}</td><td>{row.entity_type} · {row.entity_id}{row.reference && <><br />{row.reference}</>}</td><td>{row.request_id}</td>{admin && <td><button onClick={() => void open(row)}>Detalhes do evento</button></td>}</tr>)}</tbody></table></div>}<div className="pagination"><button disabled={!previous.length} onClick={() => { setCursor(previous.at(-1) ?? ''); setPrevious(previous.slice(0, -1)); }}>Eventos anteriores</button><span>Página {previous.length + 1}</span><button disabled={!data.next_cursor} onClick={() => { setPrevious([...previous, cursor]); setCursor(data.next_cursor!); }}>Próximos eventos</button></div></>}{detail && <AccessDialog title="Detalhes do evento" onClose={close}><p>{detail.action} · {detail.outcome}</p><p>Requisição: {detail.request_id}</p>{detailLoading && <p role="status">Carregando detalhes autorizados…</p>}<ErrorNotice error={detailError}/>{!!detailError && <button onClick={() => void open(detail)}>Tentar novamente</button>}{!!snapshot && <pre className="audit-snapshot">{JSON.stringify(snapshot, null, 2)}</pre>}</AccessDialog>}</section>;
}
