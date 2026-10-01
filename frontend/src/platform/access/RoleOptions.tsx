import ErrorNotice from '../../api/ErrorNotice';
import { useScopedQuery } from './useScopedQuery';
import type { Page, Role } from './types';
import { useEffect, useState } from 'react';
export default function RoleOptions({ value, onChange, label = 'Perfil', revision = 0, required = true, onName }: {
    value: string;
    onChange: (id: string) => void;
    label?: string;
    revision?: number;
    required?: boolean;
    onName?: (name: string) => void;
}) {
    const [offset, setOffset] = useState(0);
    const { data, error, loading, retry } = useScopedQuery<Page<Role>>(`/roles/assignable?limit=20&offset=${offset}`);
    useEffect(() => { if (revision)
        retry(); }, [revision, retry]);
    return <div><label>{label}<select aria-label={label} value={data?.items.some(role => role.id === value) ? value : ''} onChange={event => { onChange(event.target.value); onName?.(data?.items.find(role => role.id === event.target.value)?.name ?? ''); }} disabled={loading || !!error} required={required}><option value="">{required ? 'Selecione um perfil permitido' : 'Todos os perfis permitidos'}</option>{data?.items.map(role => <option key={role.id} value={role.id}>{role.name}</option>)}</select></label>{loading && <p role="status">Carregando perfis permitidos…</p>}<ErrorNotice error={error}/>{!!error && <button type="button" onClick={retry}>Tentar novamente</button>}{data && data.total === 0 && <p>Nenhum perfil elegível neste contrato.</p>}{data && data.total > data.limit && <div className="pagination"><button type="button" disabled={offset === 0} onClick={() => { onChange(''); onName?.(''); setOffset(Math.max(0, offset - 20)); }}>Perfis anteriores</button><span>{offset + 1}–{Math.min(offset + data.items.length, data.total)} de {data.total} perfis</span><button type="button" disabled={offset + data.limit >= data.total} onClick={() => { onChange(''); onName?.(''); setOffset(offset + 20); }}>Próximos perfis</button></div>}</div>;
}
