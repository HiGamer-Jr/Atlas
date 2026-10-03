import { useEffect, useRef, useState } from 'react';
import AccessDialog from '../platform/access/AccessDialog';
import ErrorNotice from '../api/ErrorNotice';
import { useAuth } from '../auth/state';
import { useAccessContext } from '../platform/state';
import { isAbort } from '../api/errors';
import { usePrivileged } from './state';
export default function RequestGrantDialog({ onClose }: {
    onClose: () => void;
}) { const { api, user } = useAuth(), { selected } = useAccessContext(), state = usePrivileged()!; const [reason, setReason] = useState(''), [reference, setReference] = useState(''), [password, setPassword] = useState(''), [review, setReview] = useState(false), [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(null); const abort = useRef(new AbortController()); useEffect(() => { const mountedController = new AbortController(); abort.current = mountedController; return () => mountedController.abort(); }, []); async function reauth() { const requestController = abort.current; setBusy(true); setError(null); const secret = password; setPassword(''); try {
    await api.request('/auth/reauthenticate', { method: 'POST', contextId: selected?.id, signal: requestController.signal, body: { password: secret } });
    if (!requestController.signal.aborted)
        setReview(true);
}
catch (e) {
    if (!isAbort(e))
        setError(e);
}
finally {
    setBusy(false);
} } return <AccessDialog title={review ? 'Revisar acesso temporário Financeiro/Fiscal' : 'Solicitar acesso Financeiro/Fiscal'} busy={busy || state.busy} onClose={onClose}><ErrorNotice error={error ?? state.error}/>{review ? <><p>Operador: {user?.display_name}</p><p>Motivo: {reason.trim()}</p><p>Referência: {reference.trim() || 'Não informada'}</p><p>A concessão terá duração limitada pelo servidor e pela validade da sessão e do contexto. Ela não libera módulos operacionais indisponíveis.</p><button disabled={state.busy} onClick={() => void state.start(reason.trim(), reference.trim() || null).then(onClose).catch(e => { setError(e); setReview(false); })}>Confirmar acesso temporário</button></> : <form onSubmit={e => { e.preventDefault(); void reauth(); }}><label htmlFor="grant-reason">Motivo do acesso temporário</label><textarea id="grant-reason" required minLength={3} maxLength={1000} value={reason} onChange={e => setReason(e.target.value)}/><label htmlFor="grant-reference">Referência / chamado (opcional)</label><input id="grant-reference" maxLength={100} value={reference} onChange={e => setReference(e.target.value)}/><label htmlFor="grant-password">Confirme sua senha</label><input id="grant-password" type="password" required autoComplete="current-password" value={password} onChange={e => setPassword(e.target.value)}/><p>A senha confirma a identidade do operador e não integra a concessão.</p><button disabled={busy || reason.trim().length < 3 || !password}>Reautenticar e revisar</button></form>}</AccessDialog>; }
