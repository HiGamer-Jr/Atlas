import { useEffect, useLayoutEffect, useMemo, useState } from 'react';
import { usePurchaseRequests } from './state';
import { RequestForm } from './RequestForm';
import { decimalUnits } from './validate';
import type { AttachmentView, Buyer, Command, HistoryEvent, Page, RequestView } from './types';
import { ApiError, errorText, isAbort } from '../../api/errors';
type OperationTicket = {
    epoch: number;
    controller: AbortController;
};
class DetailOperations {
    private epoch = 0;
    private pending = new Map<string, OperationTicket>();
    begin(channel: string): OperationTicket {
        this.pending.get(channel)?.controller.abort();
        const ticket = { epoch: this.epoch, controller: new AbortController() };
        this.pending.set(channel, ticket);
        return ticket;
    }
    current(ticket: OperationTicket) {
        return ticket.epoch === this.epoch && !ticket.controller.signal.aborted;
    }
    async forward<T>(ticket: OperationTicket, scopeSignal: AbortSignal, operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
        if (!this.current(ticket)) throw new DOMException('Request changed', 'AbortError');
        const abort = () => ticket.controller.abort();
        scopeSignal.addEventListener('abort', abort, {once: true});
        if (scopeSignal.aborted) abort();
        try {
            const value = await operation(ticket.controller.signal);
            if (!this.current(ticket)) throw new DOMException('Request changed', 'AbortError');
            return value;
        } finally {
            scopeSignal.removeEventListener('abort', abort);
        }
    }

    finish(ticket: OperationTicket) {
        for (const [channel, pending] of this.pending) {
            if (pending === ticket)
                this.pending.delete(channel);
        }
    }
    invalidate() {
        this.epoch++;
        this.pending.forEach(ticket => ticket.controller.abort());
        this.pending.clear();
    }
}
export function RequestDetail({ requestId }: {
    requestId: string;
}) {
    const [revision, setRevision] = useState(0);
    // Each request and explicit refresh owns all local fields and pending operations.
    return <RequestDetailSession key={JSON.stringify([requestId, revision])} requestId={requestId} onRefresh={() => setRevision(value => value + 1)}/>;
}
function RequestDetailSession({ requestId, onRefresh }: {
    requestId: string;
    onRefresh: () => void;
}) {
    const p = usePurchaseRequests();
    const signature = p.signature;
    const binding = p.state.status === 'ready' ? p.state.binding : null;
    const operations = useMemo(() => new DetailOperations(), []);
    const [result, setResult] = useState<{
        signature: string;
        value: RequestView;
    } | null>(null);
    const [history, setHistory] = useState<Page<HistoryEvent> | null>(null);
    const [candidates, setCandidates] = useState<Page<Buyer> | null>(null);
    const [buyer, setBuyer] = useState('');
    const [editing, setEditing] = useState(false);
    const [busy, setBusy] = useState(false);
    const [conflict, setConflict] = useState(false);
    const [error, setError] = useState('');
    const [reason, setReason] = useState('');
    const [note, setNote] = useState('');
    const [itemId, setItemId] = useState('');
    const [quantity, setQuantity] = useState('');
    const [evidence, setEvidence] = useState('');
    const [file, setFile] = useState<File | null>(null);
    const [fileItem, setFileItem] = useState('');
    const token = JSON.stringify([signature, requestId]);
    useLayoutEffect(() => () => operations.invalidate(), [operations]);
    async function run<T>(ticket: OperationTicket, operation: (signal: AbortSignal) => Promise<T>): Promise<T> {
        if (!operations.current(ticket))
            throw new DOMException('Request changed', 'AbortError');
        const value = await p.run(scopeSignal => operations.forward(ticket, scopeSignal, operation));
        if (!operations.current(ticket))
            throw new DOMException('Request changed', 'AbortError');
        return value;
    }
    function fail(error: unknown, ticket: OperationTicket) {
        if (!operations.current(ticket) || isAbort(error))
            return;
        setError(errorText(error));
        if (error instanceof ApiError && error.status === 409)
            setConflict(true);
    }
    useEffect(() => {
        if (!binding || !signature)
            return;
        const ticket = operations.begin('load');
        // The effect owns its controller; the operation also retains scope validation.
        const load = async () => {
            const loaded = await p.run(scopeSignal => operations.forward(ticket, scopeSignal, async signal => ({
                value: await p.api.detail(binding, requestId, signal),
                events: await p.api.history(binding, requestId, undefined, signal),
            })));
            if (!operations.current(ticket))
                return;
            setResult({ signature: token, value: loaded.value });
            setHistory(loaded.events);
            setConflict(false);
        };
        void load().catch(error => {
            if (!operations.current(ticket) || isAbort(error))
                return;
            setError(errorText(error));
        }).finally(() => operations.finish(ticket));
        return () => ticket.controller.abort();
    }, [p, binding, signature, requestId, token, operations]);
    const r = result?.signature === token ? result.value : null;
    if (p.state.status !== 'ready' || !binding)
        return <p>Detalhe indisponível neste escopo.</p>;
    if (!r)
        return <>
    <p role="status">{error ? 'Solicitação indisponível.' : 'Carregando solicitação…'}</p>
    {error && <p role="alert">{error}</p>}
    <button onClick={onRefresh}>Atualizar detalhe</button>
  </>;
    const owned = r.requester.user_id === p.user?.user_id;
    const active = !busy && !conflict && (p.has('read_unit') || (owned && p.has('read_own')));
    const buyerEligible = !!r.buyer && p.has('fulfill');
    const draft = r.status === 'DRAFT' && owned && p.has('create');
    function clearActionFields() {
        setBuyer('');
        setReason('');
        setNote('');
        setItemId('');
        setQuantity('');
        setEvidence('');
        setFile(null);
        setFileItem('');
        setCandidates(null);
    }
    async function act(operation: (signal: AbortSignal) => Promise<RequestView>) {
        if (!active)
            return;
        // A new mutation supersedes all older candidates and history continuations.
        operations.invalidate();
        const ticket = operations.begin('action');
        setBusy(true);
        setError('');
        setCandidates(null);
        setHistory(null);
        try {
            const value = await run(ticket, operation);
            if (!operations.current(ticket))
                return;
            setResult({ signature: token, value });
            clearActionFields();
            const events = await run(ticket, signal => p.api.history(binding!, requestId, undefined, signal));
            if (operations.current(ticket))
                setHistory(events);
        }
        catch (error) {
            fail(error, ticket);
        }
        finally {
            if (operations.current(ticket))
                setBusy(false);
            operations.finish(ticket);
        }
    }
    function command(action: Command, needsReason = false) {
        if (needsReason && !reason.trim()) {
            setError('Informe o motivo desta ação.');
            return;
        }
        void act(signal => p.api.command(binding!, r!.id, action, {
            expected_version: r!.version,
            ...(needsReason ? { reason: reason.trim() } : {}),
        }, signal));
    }
    async function loadCandidates(cursor?: string) {
        const ticket = operations.begin('candidates');
        try {
            const value = await run(ticket, signal => p.api.candidates(binding!, r!.requesting_node.id, cursor, signal));
            if (operations.current(ticket)) {
                setCandidates(value);
                setBuyer('');
            }
        }
        catch (error) {
            fail(error, ticket);
        }
        finally {
            operations.finish(ticket);
        }
    }
    async function loadMoreHistory() {
        if (!history?.next_cursor)
            return;
        const previous = history;
        const ticket = operations.begin('history');
        try {
            const value = await run(ticket, signal => p.api.history(binding!, r!.id, previous.next_cursor!, signal));
            if (operations.current(ticket))
                setHistory({ ...value, items: [...previous.items, ...value.items] });
        }
        catch (error) {
            fail(error, ticket);
        }
        finally {
            operations.finish(ticket);
        }
    }
    async function download(attachment: AttachmentView) {
        const ticket = operations.begin('download');
        setBusy(true);
        try {
            await run(ticket, signal => p.api.downloadAttachment(binding!, r!.id, attachment, signal));
        }
        catch (error) {
            fail(error, ticket);
        }
        finally {
            if (operations.current(ticket))
                setBusy(false);
            operations.finish(ticket);
        }
    }
    function recordFulfillment() {
        try {
            decimalUnits(quantity, true);
            if (!itemId || !evidence.trim() || !reason.trim()) throw new Error();
            void act(signal => p.api.fulfill(binding!, r!.id, {
                expected_version: r!.version, item_id: itemId, quantity, evidence, reason,
            }, signal));
        } catch {
            setError('Informe item, quantidade exata, evidência e motivo.');
        }
    }

    function reverseEntry(entryId: string) {
        if (!reason.trim()) {
            setError('Informe o motivo da reversão.');
            return;
        }
        void act(signal => p.api.reverse(binding!, r!.id, entryId, {
            expected_version: r!.version, reason,
        }, signal));
    }

    function selectFile(value: File | null) {
        if (value && value.size > 5 * 1024 * 1024) {
            setError('Arquivo excede 5 MiB.');
            setFile(null);
            return;
        }
        setFile(value);
    }

    function addSelectedFile() {
        if (!file) return;
        void act(signal => p.api.addAttachment(binding!, r!.id, r!.version, file, fileItem || null, signal));
    }

    function saveEditedDraft(value: RequestView) {
        if (value.id !== requestId)
            return;
        operations.invalidate();
        onRefresh();
    }
    const now = new Date();
    const today = [now.getFullYear(), String(now.getMonth() + 1).padStart(2, '0'), String(now.getDate()).padStart(2, '0')].join('-');
    if (editing)
        return <>
    <button onClick={() => setEditing(false)}>Voltar ao detalhe</button>
    <RequestForm key={r.version} draft={r} onSaved={saveEditedDraft}/>
  </>;
    const canUpload = draft || (p.has('comment') && ['SUBMITTED', 'IN_TRIAGE', 'AWAITING_APPROVAL', 'APPROVED', 'IN_FULFILLMENT', 'FULFILLED'].includes(r.status));
    return <article>
    <h2>{r.title}</h2>
    <p>Identificador: {r.id}</p>
    <p>Estado: {r.status} · versão {r.version} · {r.requesting_node.name}</p>
    <p>Solicitante: {r.requester.display_name}</p>
    <p>Comprador elegível: {r.buyer?.display_name ?? 'Não disponível ou não atribuído'}</p>
    <p>{r.description}</p>
    <p>Justificativa: {r.justification}</p>
    <p>Observações: {r.notes}</p>
    <p>Prioridade: {r.priority} · Data necessária: {r.needed_on ?? 'Não informada'}{r.needed_on && r.needed_on < today ? ' — data passada (data local)' : ''}</p>
 <p>Política decidida: {r.approval_mode ?? 'Ainda não decidida'} · versão {r.approval_policy_version ?? '—'} · decisão: {r.approval_decision_kind === 'HUMAN' ? 'HUMAN — aprovação humana' : r.approval_decision_kind === 'POLICY_WAIVER' ? 'POLICY_WAIVER — dispensa por política' : 'Pendente'}</p>
 <p>Atendimento registrado manualmente: {r.fulfillment_state}. Cada ação é validada pelo servidor, incluindo a atribuição atual do comprador.</p>
 <table>
    <thead>
    <tr>
    <th>Item</th>
    <th>Especificação</th>
    <th>Solicitado</th>
    <th>Atendido</th>
    <th>Restante</th>
    </tr>
    </thead>
    <tbody>{r.items.map(i => <tr key={i.id}>
        <td>{i.description}</td>
        <td>{i.specification}</td>
        <td>{i.requested_quantity} {i.uom_code}</td>
        <td>{i.fulfilled_quantity} {i.uom_code}</td>
        <td>{i.remaining_quantity} {i.uom_code}</td>
        </tr>)}</tbody>
    </table>
 {error && <p role="alert">{error}</p>}{conflict && <p role="alert">Conflito de versão. Atualize o detalhe e decida novamente; as alterações não foram mescladas.</p>}<button disabled={busy} onClick={onRefresh}>Atualizar detalhe</button>
 <fieldset disabled={!active}>
    <legend>Ações disponíveis</legend>
 {draft && <>
        <button onClick={() => setEditing(true)}>Editar rascunho</button>
        <button onClick={() => command('submit', r.priority === 'URGENT')}>Enviar solicitação</button>{r.priority === 'URGENT' && <p>A urgência exige motivo de envio, além da justificativa salva.</p>}</>}
 <label>Motivo da ação<textarea maxLength={2000} value={reason} onChange={e => setReason(e.target.value)}/>
    </label>
 {r.status === 'SUBMITTED' && p.has('triage') && <button onClick={() => command('start-triage')}>Iniciar triagem</button>}
 {r.status === 'IN_TRIAGE' && p.has('triage') && <>
        <button onClick={() => command('request-approval')}>Concluir triagem pela política do contrato</button>
        <button onClick={() => command('reject', true)}>Rejeitar solicitação</button>
        </>}
 {r.status === 'AWAITING_APPROVAL' && p.has('approve') && !owned && <>
        <button onClick={() => command('approve')}>Aprovar solicitação</button>
        <button onClick={() => command('reject', true)}>Rejeitar solicitação</button>
        </>}
 {p.has('assign') && p.has('read_unit') && ['APPROVED', 'IN_FULFILLMENT'].includes(r.status) && <>
        <button onClick={() => void loadCandidates()}>Consultar compradores elegíveis</button>{candidates && <>
            <label>Comprador<select value={buyer} onChange={e => setBuyer(e.target.value)}>
            <option value="">Selecione</option>{candidates.items.map(c => <option value={c.membership_id} key={c.membership_id}>{c.display_name}</option>)}</select>
            </label>
            <button disabled={!buyer} onClick={() => void act(signal => p.api.assign(binding, r.id, { expected_version: r.version, buyer_membership_id: buyer }, signal))}>Atribuir comprador</button>{candidates.next_cursor && <button onClick={() => void loadCandidates(candidates.next_cursor!)}>Próximos compradores</button>}</>}</>}
 {r.status === 'APPROVED' && buyerEligible && <button onClick={() => command('start-fulfillment')}>Iniciar atendimento</button>}
 {['DRAFT', 'SUBMITTED', 'IN_TRIAGE', 'AWAITING_APPROVAL', 'APPROVED', 'IN_FULFILLMENT'].includes(r.status) && p.has('cancel') && (r.status === 'DRAFT' ? owned : r.status === 'IN_FULFILLMENT' ? p.has('triage') : owned || p.has('triage')) && <button onClick={() => command('cancel', true)}>Cancelar solicitação</button>}
 {r.status === 'FULFILLED' && p.has('close') && (owned || !!r.buyer) && <button onClick={() => command('close')}>Confirmar encerramento</button>}
 {r.status === 'IN_FULFILLMENT' && buyerEligible && <>
        <h3>Registrar atendimento manual</h3>
        <label>Item atendido<select value={itemId} onChange={e => setItemId(e.target.value)}>
        <option value="">Selecione</option>{r.items.filter(i => decimalUnits(i.remaining_quantity) > 0n).map(i => <option value={i.id} key={i.id}>{i.description} ({i.uom_code})</option>)}</select>
        </label>
        <label>Quantidade atendida<input inputMode="decimal" value={quantity} onChange={e => setQuantity(e.target.value)}/>
        </label>
        <label>Evidência do atendimento<textarea maxLength={4000} value={evidence} onChange={e => setEvidence(e.target.value)}/>
        </label>
        <button onClick={recordFulfillment}>Registrar atendimento</button>
        </>}
 {p.has('comment') && r.status !== 'DRAFT' && r.status !== 'CLOSED' && <>
        <label>Comentário<textarea maxLength={4000} value={note} onChange={e => setNote(e.target.value)}/>
        </label>
        <button disabled={!note.trim()} onClick={() => void act(signal => p.api.note(binding, r.id, { expected_version: r.version, text: note }, signal))}>Adicionar comentário</button>
        </>}
 </fieldset>
    <h3>Arquivos privados</h3>
    <ul>{r.attachments.map(a => <li key={a.id}>{a.filename} · {a.size} bytes · {a.media_type}<small>SHA-256: {a.digest}</small>
        <button disabled={!active} onClick={() => void download(a)}>Baixar {a.filename}</button>{draft && <button disabled={!active} onClick={() => void act(signal => p.api.removeAttachment(binding, r.id, a.id, r.version, signal))}>Remover {a.filename}</button>}</li>)}</ul>
 {canUpload && <fieldset disabled={!active || r.attachments.length >= 10}>
        <legend>Adicionar arquivo</legend>
        <p>Até 5 MiB por arquivo e 10 arquivos. PDF, PNG, JPEG ou TXT; o servidor verifica conteúdo e limites conservadores de PDF.</p>
        <label>Arquivo privado<input type="file" accept=".pdf,.png,.jpg,.jpeg,.txt" onChange={e => selectFile(e.target.files?.[0] ?? null)}/>
        </label>
        <label>Item do arquivo<select value={fileItem} onChange={e => setFileItem(e.target.value)}>
        <option value="">Solicitação inteira</option>{r.items.map(i => <option value={i.id} key={i.id}>{i.description}</option>)}</select>
        </label>
        <button disabled={!file} onClick={addSelectedFile}>Anexar arquivo</button>
        </fieldset>}
    <h3>Histórico privado</h3>
    {history && <>
        <ol>
            {history.items.map(event => {
                const canReverse = r.status === 'IN_FULFILLMENT' && buyerEligible
                    && event.action === 'procurement.request.fulfillment_recorded'
                    && !!event.payload.entry_id
                    && !history.items.some(other => other.payload.original_entry_id === event.payload.entry_id);
                return <li key={event.id}>
                    {event.action} · {event.actor.display_name} ({event.tenant_role_code})
                    · {event.occurred_at} · versão {event.aggregate_version}
                    {event.reason && <p>Motivo: {event.reason}</p>}
                    {event.payload.text && <p>{event.payload.text}</p>}
                    {event.payload.quantity && <p>{event.payload.quantity} {event.payload.uom_code}</p>}
                    {event.payload.approval_mode && <p>
                        {event.payload.approval_mode} · política versão {event.payload.approval_policy_version}
                        · {event.payload.approval_decision_kind ?? 'Pendente'}
                    </p>}
                    {canReverse && <button disabled={!active} onClick={() => reverseEntry(event.payload.entry_id!)}>
                        Reverter atendimento {event.sequence}
                    </button>}
                </li>;
            })}
        </ol>
        {history.next_cursor && <button disabled={!active} onClick={() => void loadMoreHistory()}>
            Mais histórico
        </button>}
    </>}
    </article>;
}
