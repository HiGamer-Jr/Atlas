import { statuses, uoms, type RequestView, type RequestPage, type Page, type HistoryEvent, type Buyer } from './types';
const invalid = (): never => { throw new Error('PURCHASE_REQUEST_INVALID'); };
const obj = (v: unknown): Record<string, unknown> => !v || typeof v !== 'object' || Array.isArray(v) ? invalid() : v as Record<string, unknown>;
const str = (v: unknown, max = 4000, empty = false): string => typeof v !== 'string' || v.length > max || (!empty && !v.trim()) ? invalid() : v;
const integer = (v: unknown, min = 0, max = Number.MAX_SAFE_INTEGER) => typeof v !== 'number' || !Number.isSafeInteger(v) || v < min || v > max ? invalid() : v;
const choice = (v: unknown, values: readonly string[]) => typeof v !== 'string' || !values.includes(v) ? invalid() : v;
const list = (v: unknown, max = 100): unknown[] => !Array.isArray(v) || v.length > max ? invalid() : v;
const timestamp = (value: unknown) => {
    str(value, 64);
    if (Number.isNaN(Date.parse(value as string))) invalid();
};

export function decimalUnits(value: unknown, positive = false): bigint {
    const quantity = str(value, 32);
    if (!/^\d{1,12}(\.\d{1,6})?$/.test(quantity)) return invalid();
    const [whole, fraction = ''] = quantity.split('.');
    const amount = BigInt(whole) * 1000000n + BigInt(fraction.padEnd(6, '0'));
    if (amount >= 1000000000000000000n || (positive && amount === 0n)) return invalid();
    return amount;
}

function actor(value: unknown) {
    const actor = obj(value);
    str(actor.membership_id, 128);
    str(actor.user_id, 128);
    str(actor.display_name, 400);
}

function buyer(value: unknown) {
    const buyer = obj(value);
    str(buyer.membership_id, 128);
    str(buyer.display_name, 400);
}

function approval(value: Record<string, unknown>) {
    if (value.approval_mode !== null && value.approval_mode !== undefined) {
        choice(value.approval_mode, ['REQUIRED', 'NOT_REQUIRED']);
    }
    if (value.approval_policy_version !== null && value.approval_policy_version !== undefined) {
        integer(value.approval_policy_version);
    }
    if (value.approval_decision_kind !== null && value.approval_decision_kind !== undefined) {
        choice(value.approval_decision_kind, ['HUMAN', 'POLICY_WAIVER']);
    }
    if (value.approval_decision_kind === 'POLICY_WAIVER' && value.approval_mode !== 'NOT_REQUIRED') invalid();
    if (value.approval_decision_kind === 'HUMAN' && value.approval_mode !== 'REQUIRED') invalid();
}

export function parseRequest(value: unknown, expected: {
    tenantId: string;
    contractId: string;
}): RequestView {
    const v = obj(value);
    if (v.schema_version !== 1 || v.tenant_id !== expected.tenantId || v.contract_id !== expected.contractId)
        invalid();
    str(v.id, 128);
    actor(v.requester);
    const node = obj(v.requesting_node);
    for (const key of ['id', 'code', 'name'])
        str(node[key], 400);
    choice(node.kind, ['BRANCH', 'UNIT', 'STORE', 'DISTRIBUTION_CENTER', 'WAREHOUSE', 'OFFICE', 'WORKSITE']);
    if (v.buyer !== null)
        buyer(v.buyer);
    str(v.title, 200);
    for (const key of ['description', 'justification', 'notes'])
        str(v[key], 4000, true);
    choice(v.priority, ['NORMAL', 'HIGH', 'URGENT']);
    choice(v.status, statuses);
    choice(v.fulfillment_state, ['NONE', 'PARTIAL', 'COMPLETE']);
    integer(v.version, 1);
    approval(v);
    if (v.needed_on !== null) {
        const date = str(v.needed_on, 10);
        if (!/^\d{4}-\d{2}-\d{2}$/.test(date) || new Date(date).toISOString().slice(0, 10) !== date)
            invalid();
    }
    for (const key of ['created_at', 'updated_at'])
        timestamp(v[key]);
    for (const key of ['submitted_at', 'triage_started_at', 'approval_requested_at', 'approved_at', 'assigned_at', 'fulfillment_started_at', 'fulfilled_at', 'closed_at'])
        if (v[key] !== null)
            timestamp(v[key]);
    const ids = new Set();
    for (const raw of list(v.items)) {
        const i = obj(raw);
        str(i.id, 128);
        if (ids.has(i.id))
            invalid();
        ids.add(i.id);
        integer(i.position, 1, 100);
        str(i.description, 2000);
        str(i.specification, 4000, true);
        choice(i.uom_code, uoms);
        if (decimalUnits(i.requested_quantity, true) !== decimalUnits(i.fulfilled_quantity) + decimalUnits(i.remaining_quantity))
            invalid();
        timestamp(i.created_at);
        timestamp(i.updated_at);
    }
    const attachmentIds = new Set();
    for (const raw of list(v.attachments, 10)) {
        const a = obj(raw);
        str(a.id, 128);
        if (attachmentIds.has(a.id))
            invalid();
        attachmentIds.add(a.id);
        if (a.item_id !== null && !ids.has(a.item_id))
            invalid();
        str(a.filename, 255);
        choice(a.media_type, ['application/pdf', 'image/png', 'image/jpeg', 'text/plain']);
        if (!/^[a-f0-9]{64}$/.test(str(a.digest, 64)))
            invalid();
        integer(a.size, 1, 5 * 1024 * 1024);
        str(a.uploader_membership_id, 128);
        timestamp(a.created_at);
    }
    return structuredClone(value) as RequestView;
}
function page<T>(value: unknown, parse: (v: unknown) => T): Page<T> {
    const valueObject = obj(value);
    integer(valueObject.total);
    integer(valueObject.limit, 1, 100);
    const items = list(valueObject.items).map(parse);
    if (items.length > (valueObject.limit as number) || items.length > (valueObject.total as number)) invalid();
    if (valueObject.next_cursor !== null) str(valueObject.next_cursor, 2048);
    return {
        items,
        total: valueObject.total as number,
        limit: valueObject.limit as number,
        next_cursor: valueObject.next_cursor as string | null,
    };
}

export const parseRequestPage = (value: unknown, expected: {tenantId: string; contractId: string}): RequestPage =>
    page(value, item => parseRequest(item, expected));

const actions = [
    'created', 'draft_updated', 'submitted', 'triage_started', 'approval_requested',
    'approved', 'approval_waived', 'rejected', 'assigned', 'fulfillment_started',
    'fulfillment_recorded', 'fulfillment_reversed', 'fulfilled', 'cancelled',
    'closed', 'note_added', 'attachment_added', 'attachment_removed',
];

function validateHistoryPayload(value: unknown) {
    const payload = obj(value);
    if (payload.schema_version !== 1) invalid();
    const allowed = [
        'schema_version', 'from_status', 'to_status', 'item_ids', 'item_id', 'entry_id',
        'original_entry_id', 'attachment_id', 'buyer_membership_id', 'quantity',
        'uom_code', 'text', 'approval_mode', 'approval_policy_version',
        'approval_decision_kind', 'content_digest',
    ];
    if (Object.keys(payload).some(key => !allowed.includes(key))) invalid();
    for (const key of ['from_status', 'to_status']) {
        if (payload[key] != null) choice(payload[key], statuses);
    }
    for (const key of ['item_id', 'entry_id', 'original_entry_id', 'attachment_id', 'buyer_membership_id']) {
        if (payload[key] != null) str(payload[key], 128);
    }
    if (payload.item_ids !== undefined) list(payload.item_ids).forEach(id => str(id, 128));
    if (payload.quantity !== undefined) decimalUnits(payload.quantity, true);
    if (payload.uom_code !== undefined) choice(payload.uom_code, uoms);
    if (payload.text !== undefined) str(payload.text, 4000);
    if (payload.content_digest != null && !/^[a-f0-9]{64}$/.test(str(payload.content_digest, 64))) invalid();
    approval(payload);
}

function parseHistoryEvent(value: unknown): HistoryEvent {
    const event = obj(value);
    str(event.id, 128);
    integer(event.sequence, 1);
    integer(event.aggregate_version, 1);
    choice(event.action, actions.map(action => 'procurement.request.' + action));
    actor(event.actor);
    str(event.tenant_role_id, 128);
    str(event.tenant_role_code, 128);
    timestamp(event.occurred_at);
    if (event.reason !== null) str(event.reason, 2000);
    validateHistoryPayload(event.payload);
    return structuredClone(event) as HistoryEvent;
}

export function parseRequestHistory(value: unknown, expected: {tenantId: string; contractId: string}): Page<HistoryEvent> {
    if (!expected.tenantId || !expected.contractId) invalid();
    return page(value, parseHistoryEvent);
}

export const parseCandidates = (value: unknown): Page<Buyer> => page(value, item => {
    buyer(item);
    return structuredClone(item) as Buyer;
});
