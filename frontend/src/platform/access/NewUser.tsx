import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/state';
import { useAccessContext } from '../state';
import { ApiError, isAbort } from '../../api/errors';
import ErrorNotice from '../../api/ErrorNotice';
import AccessDialog from './AccessDialog';
import RoleOptions from './RoleOptions';
export default function NewUser({ onClose, onCreated }: {
    onClose: () => void;
    onCreated: () => void;
}) {
    const { api } = useAuth(), { selected } = useAccessContext();
    const [name, setName] = useState(''), [email, setEmail] = useState(''), [role, setRole] = useState(''), [roleName, setRoleName] = useState(''), [review, setReview] = useState(false), [error, setError] = useState<unknown>(null), [busy, setBusy] = useState(false), [revision, setRevision] = useState(0);
    const controller = useRef<AbortController | null>(null);
    useEffect(() => () => controller.current?.abort(), []);
    async function submit() { if (!selected || busy || !role)
        return; setBusy(true); setError(null); controller.current = new AbortController(); try {
        await api.request('/memberships', { method: 'POST', contextId: selected.id, signal: controller.current.signal, body: { display_name: name.trim(), email: email.trim(), role_id: role } });
        if (!controller.current.signal.aborted)
            onCreated();
    }
    catch (e) {
        if (!isAbort(e)) {
            setError(e);
            if (e instanceof ApiError && e.status === 403) {
                setRevision(value => value + 1);
                setRole('');
                setReview(false);
            }
        }
    }
    finally {
        if (!controller.current?.signal.aborted)
            setBusy(false);
    } }
    return <AccessDialog title={review ? 'Revisar novo usuário' : 'Novo usuário'} onClose={onClose} busy={busy}>{review ? <><p>Nome: <strong>{name}</strong></p><p>E-mail: {email}</p><p>Perfil selecionado: {roleName}</p><p>A solicitação de acesso será registrada neste contrato. A confirmação não comprova envio ou entrega de e-mail.</p><ErrorNotice error={error}/><button disabled={busy} onClick={() => setReview(false)}>Voltar aos campos</button><button disabled={busy} onClick={() => void submit()}>{busy ? 'Processando…' : 'Confirmar'}</button></> : <form onSubmit={event => { event.preventDefault(); setReview(true); }}><label>Nome<input required maxLength={200} value={name} onChange={event => setName(event.target.value)}/></label><label>E-mail<input required type="email" maxLength={320} value={email} onChange={event => setEmail(event.target.value)}/></label><RoleOptions onName={setRoleName} value={role} onChange={setRole} revision={revision}/><ErrorNotice error={error}/><button disabled={!role || !name.trim() || !email.trim()}>Revisar solicitação</button></form>}</AccessDialog>;
}
