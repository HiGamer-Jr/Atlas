const messages: Record<number, string> = {
    401: 'Sua sessão expirou. Entre novamente.',
    403: 'Acesso negado para esta operação.',
    404: 'Registro não encontrado ou indisponível.',
    409: 'Os dados foram alterados. Atualize a página e tente novamente.',
    422: 'Confira os campos informados e tente novamente.',
    429: 'Limite de tentativas atingido. Aguarde antes de tentar novamente.',
    503: 'Serviço temporariamente indisponível. Tente novamente mais tarde.',
};
export class ApiError extends Error {
    status: number;
    code: string;
    requestId?: string;
    constructor(status: number, payload: Record<string, unknown> = {}) {
        super(payload.code === 'AUTH_INVALID' ? 'E-mail ou senha inválidos.' : messages[status] ?? 'Não foi possível concluir a operação. Tente novamente.');
        this.name = 'ApiError';
        this.status = status;
        this.code = typeof payload.code === 'string' ? payload.code : '';
        this.requestId = typeof payload.request_id === 'string' && /^[a-zA-Z0-9-]{1,80}$/.test(payload.request_id) ? payload.request_id : undefined;
    }
}
export function isAbort(error: unknown) { return error instanceof Error && error.name === 'AbortError'; }
export function errorText(error: unknown) { return error instanceof ApiError ? error.message : 'Não foi possível conectar ao serviço. Tente novamente.'; }
