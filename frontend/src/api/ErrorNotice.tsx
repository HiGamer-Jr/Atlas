import { ApiError, errorText } from './errors';
export default function ErrorNotice({ error }: {
    error: unknown;
}) {
    if (!error)
        return null;
    return <div role="alert" className="error-notice"><p>{errorText(error)}</p>{error instanceof ApiError && error.requestId && <p>Código de atendimento: {error.requestId}</p>}</div>;
}
