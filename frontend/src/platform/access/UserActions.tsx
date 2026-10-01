import { useEffect, useRef, useState } from 'react';
import { useAuth } from '../../auth/state';
import { useAccessContext } from '../state';
import { ApiError, isAbort } from '../../api/errors';
import ErrorNotice from '../../api/ErrorNotice';
import AccessDialog from './AccessDialog';
import RoleOptions from './RoleOptions';
import type { Member } from './types';
const actions: Record<string, {
    label: string;
    capability: string;
    explanation: string;
}> = { invite: { label: 'Reemitir convite', capability: 'users.invite', explanation: 'O convite anterior será invalidado. A solicitação de um novo link será registrada; a entrega depende do processamento.' }, reset_password: { label: 'Enviar link de redefinição', capability: 'users.password_reset', explanation: 'Será solicitada a emissão de um link de redefinição. Apenas o destinatário define a senha.' }, block: { label: 'Bloquear acesso', capability: 'users.status', explanation: 'O acesso deste vínculo será bloqueado. O estado ativo é independente do bloqueio.' }, unblock: { label: 'Desbloquear acesso', capability: 'users.status', explanation: 'O bloqueio deste vínculo será removido. Um vínculo inativo permanece inativo.' }, activate: { label: 'Ativar vínculo', capability: 'users.status', explanation: 'O vínculo será ativado. Um bloqueio existente permanece aplicado.' }, inactivate: { label: 'Inativar vínculo', capability: 'users.status', explanation: 'O vínculo neste contrato será inativado e o acesso será revogado.' }, assign_role: { label: 'Alterar perfil', capability: 'roles.assign', explanation: 'O novo perfil substituirá o perfil atual apenas neste contrato.' } };
export default function UserActions({ member, onChanged, onNotice, refreshing = false, refreshError }: {
    member: Member;
    onChanged: () => void;
    onNotice: (text: string) => void;
    refreshing?: boolean;
    refreshError?: unknown;
}) {
    const { api } = useAuth(), { selected } = useAccessContext();
    const [action, setAction] = useState<string | null>(null), [role, setRole] = useState(''), [roleName, setRoleName] = useState(''), [busy, setBusy] = useState(false), [error, setError] = useState<unknown>(null), [revision, setRevision] = useState(0), [conflict, setConflict] = useState(false);
    const controller = useRef<AbortController | null>(null);
    useEffect(() => () => controller.current?.abort(), []);
    const close = () => { setAction(null); setError(null); setRole(''); setConflict(false); };
    async function confirm() { if (!action || !selected || busy || refreshing || conflict)
        return; setBusy(true); setError(null); controller.current = new AbortController(); try {
        let path = `/memberships/${encodeURIComponent(member.id)}`, method: 'POST' | 'PATCH' | 'PUT' = 'POST', body: unknown;
        switch (action) {
            case 'assign_role':
                path += '/role';
                method = 'PUT';
                body = { role_id: role, expected_version: member.version };
                break;
            case 'invite':
                path += '/invite';
                break;
            case 'reset_password':
                path += '/reset-password';
                break;
            default:
                path += '/status';
                method = 'PATCH';
                body = { expected_version: member.version, ...(action === 'block' || action === 'unblock' ? { blocked: action === 'block' } : { active: action === 'activate' }) };
        }
        await api.request(path, { method, body, contextId: selected.id, signal: controller.current.signal });
        if (controller.current.signal.aborted)
            return;
        onNotice(method === 'POST' ? 'Solicitação aceita. Aguarde o processamento do link.' : 'Alteração concluída.');
        close();
        onChanged();
    }
    catch (e) {
        if (!isAbort(e)) {
            setError(e);
            if (e instanceof ApiError && e.status === 403) {
                setRevision(value => value + 1);
                setRole('');
                onChanged();
            }
            if (e instanceof ApiError && e.status === 409) {
                setConflict(true);
                onChanged();
            }
        }
    }
    finally {
        if (!controller.current?.signal.aborted)
            setBusy(false);
    } }
    const permitted = (member.allowed_actions ?? []).filter(value => actions[value] && selected?.capabilities?.includes(actions[value].capability));
    return <><div className="access-actions">{permitted.map(value => <button key={value} onClick={() => { setAction(value); setError(null); setConflict(false); }}>{actions[value].label}</button>)}</div>{action && <AccessDialog title={actions[action].label} onClose={close} busy={busy}><p><strong>{member.display_name}</strong> · {member.email}</p><p>Perfil atual: {member.role_name}</p><p>Estado atual: {member.active ? 'Ativo' : 'Inativo'} · {member.blocked ? 'Bloqueado' : 'Não bloqueado'} · Convite {member.invitation_pending ? 'pendente' : 'não pendente'}</p><p>{actions[action].explanation}</p>{action === 'assign_role' && <RoleOptions onName={setRoleName} label="Novo perfil" value={role} onChange={setRole} revision={revision}/>}{action === 'assign_role' && roleName && <p>Novo perfil: {roleName}</p>}<ErrorNotice error={error}/><ErrorNotice error={refreshError}/>{(conflict || !!refreshError) && <button disabled={busy} onClick={() => { onChanged(); setConflict(false); }}>Atualizar dados</button>}<button disabled={busy || refreshing || conflict || (action === 'assign_role' && !role) || !permitted.includes(action)} onClick={() => void confirm()}>{busy ? 'Processando…' : 'Confirmar'}</button></AccessDialog>}</>;
}
