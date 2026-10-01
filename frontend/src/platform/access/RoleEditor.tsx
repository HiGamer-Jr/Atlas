import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/state';
import { useAccessContext } from '../state';
import { ApiError, isAbort } from '../../api/errors';
import ErrorNotice from '../../api/ErrorNotice';
import AccessDialog from './AccessDialog';
import { useScopedQuery } from './useScopedQuery';
import type { Capability, Role } from './types';
export default function RoleEditor({ role, onClose, onSaved, onRefresh }: {
    role: Role | null;
    onClose: () => void;
    onSaved: () => void;
    onRefresh: () => void;
}) {
    const { api } = useAuth(), { selected } = useAccessContext();
    const { data: catalog, error: catalogError, loading, retry } = useScopedQuery<{
        items: Capability[];
    }>('/capabilities');
    const [name, setName] = useState(role?.name ?? ''), [code, setCode] = useState(role?.code ?? ''), [description, setDescription] = useState(role?.description ?? ''), [classification, setClassification] = useState(role?.classification ?? 'STANDARD'), [active, setActive] = useState(role?.active ?? true), [support, setSupport] = useState(role?.support_assignable ?? false), [permissions, setPermissions] = useState<string[]>(role?.permissions ?? []), [review, setReview] = useState(false), [error, setError] = useState<unknown>(null), [busy, setBusy] = useState(false), [conflict, setConflict] = useState(false);
    const controller = useRef<AbortController | null>(null);
    useEffect(() => () => controller.current?.abort(), []);
    const sensitive = classification !== 'STANDARD' || permissions.some(value => catalog?.items.find(item => item.code === value)?.sensitive);
    const locked = role?.sensitivity_locked ?? false;
    async function save() { if (!selected || busy || conflict)
        return; setBusy(true); setError(null); controller.current = new AbortController(); try {
        const fields = { name: name.trim(), description: description.trim(), classification, active, support_assignable: support, permissions };
        await api.request(role ? `/roles/${encodeURIComponent(role.id)}` : '/roles', { method: role ? 'PATCH' : 'POST', contextId: selected.id, signal: controller.current.signal, body: role ? { ...fields, expected_version: role.version } : { ...fields, code } });
        if (!controller.current.signal.aborted)
            onSaved();
    }
    catch (e) {
        if (!isAbort(e)) {
            setError(e);
            if (e instanceof ApiError && (e.status === 403 || e.status === 409)) {
                setConflict(true);
                onRefresh();
                retry();
            }
        }
    }
    finally {
        if (!controller.current?.signal.aborted)
            setBusy(false);
    } }
    return <AccessDialog title={review ? 'Confirmar perfil' : role ? 'Editar perfil' : 'Criar perfil'} onClose={onClose} busy={busy}>{review ? <><p><strong>{name}</strong> ({code})</p><p>Descrição: {description || 'Sem descrição'}</p><p>Classificação: {({ STANDARD: 'Padrão', ADMINISTRATIVE: 'Administrativo', FINANCIAL_FISCAL: 'Financeiro / fiscal', SENSITIVE: 'Sensível' } as Record<string, string>)[classification] ?? classification}</p><p>Perfil: {active ? 'Ativo' : 'Inativo'} · Atribuível pelo suporte: {support ? 'Sim' : 'Não'}</p><p>{role?.member_count ?? 0} vínculos afetados pelas permissões deste perfil.</p>{permissions.length > 0 && <p>Permissões: {permissions.join(', ')}</p>}{(sensitive || locked) && <p className="review-warning">Permissões sensíveis ou classificação protegida: revise o impacto nos vínculos deste contrato.</p>}{role && support !== role.support_assignable && <p>A elegibilidade de novas atribuições pelo suporte será alterada. Vínculos existentes permanecem associados.</p>}{role && !active && role.active && <p>O perfil será inativado; novas atribuições deixam de ser elegíveis.</p>}<ErrorNotice error={error}/>{conflict && <p>Feche este diálogo e reabra o perfil atualizado antes de revisar novamente.</p>}<button disabled={busy} onClick={() => setReview(false)}>Voltar aos campos</button><button disabled={busy || conflict} onClick={() => void save()}>{busy ? 'Processando…' : 'Confirmar'}</button></> : <form onSubmit={event => { event.preventDefault(); setReview(true); }}><label>Código<input required pattern="[A-Z][A-Z0-9_]+" minLength={2} maxLength={64} disabled={!!role} value={code} onChange={event => setCode(event.target.value.toUpperCase())}/></label><label>Nome do perfil<input required maxLength={200} value={name} onChange={event => setName(event.target.value)}/></label><label>Descrição<textarea maxLength={2000} value={description} onChange={event => setDescription(event.target.value)}/></label><label>Classificação<select aria-label="Classificação" value={classification} onChange={event => { setClassification(event.target.value); if (event.target.value !== 'STANDARD')
        setSupport(false); }}><option value="STANDARD">Padrão</option><option value="ADMINISTRATIVE">Administrativo</option><option value="FINANCIAL_FISCAL">Financeiro / fiscal</option><option value="SENSITIVE">Sensível</option></select></label><label className="check-label"><input type="checkbox" checked={active} onChange={event => setActive(event.target.checked)}/>Perfil ativo</label><label className="check-label"><input type="checkbox" checked={support} disabled={!support && (sensitive || locked || !active)} onChange={event => setSupport(event.target.checked)}/>Atribuível pelo suporte</label>{locked && <p>Elegibilidade protegida pelo servidor.</p>}<fieldset><legend>Permissões do catálogo</legend>{loading && <p role="status">Carregando catálogo…</p>}<ErrorNotice error={catalogError}/>{!!catalogError && <button type="button" onClick={retry}>Tentar novamente</button>}{catalog?.items.map(item => <label className="check-label" key={item.code}><input type="checkbox" checked={permissions.includes(item.code)} onChange={event => { setPermissions(event.target.checked ? [...permissions, item.code] : permissions.filter(value => value !== item.code)); if (event.target.checked && item.sensitive)
        setSupport(false); }}/>{item.code}{item.sensitive ? ' (sensível)' : ''}<small>{item.domain}</small></label>)}</fieldset><ErrorNotice error={error}/><button disabled={!catalog || loading || !name.trim() || !code || conflict}>Revisar perfil</button></form>}</AccessDialog>;
}
