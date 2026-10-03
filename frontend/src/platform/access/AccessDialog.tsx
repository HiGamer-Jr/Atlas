import { useEffect, useId, useRef, type ReactNode } from 'react';
import { useAccessContext } from '../state';
import { environmentLabel } from '../labels';
export default function AccessDialog({ title, children, onClose, busy = false }: {
    title: string;
    children: ReactNode;
    onClose: () => void;
    busy?: boolean;
}) {
    const ref = useRef<HTMLDialogElement>(null), id = useId();
    const { selected } = useAccessContext();
    useEffect(() => { const previous = document.activeElement as HTMLElement | null; const dialog = ref.current; if (dialog && typeof dialog.showModal === 'function')
        dialog.showModal();
    else
        dialog?.setAttribute('open', ''); dialog?.querySelector<HTMLElement>('input,textarea,select,button')?.focus(); return () => { dialog?.close?.(); if (previous?.isConnected && !previous.matches(':disabled')) previous.focus(); else previous?.closest<HTMLElement>('[tabindex]')?.focus(); }; }, []);
    return <dialog ref={ref} className="access-dialog" aria-labelledby={id} onCancel={event => { event.preventDefault(); if (!busy)
        onClose(); }} onKeyDown={event => { if (event.key === 'Escape') {
        event.preventDefault();
        if (!busy)
            onClose();
    } if (event.key === 'Tab') {
        const elements = Array.from(ref.current?.querySelectorAll<HTMLElement>('button:not(:disabled),input:not(:disabled),select:not(:disabled),textarea:not(:disabled),[tabindex="0"]') ?? []);
        if (event.shiftKey && document.activeElement === elements[0]) {
            event.preventDefault();
            elements.at(-1)?.focus();
        }
        else if (!event.shiftKey && document.activeElement === elements.at(-1)) {
            event.preventDefault();
            elements[0]?.focus();
        }
    } }}><h2 id={id}>{title}</h2><p className="dialog-context">Empresa: {selected?.tenant_name} · Contrato: {selected?.contract_code} · Ambiente: {selected && environmentLabel(selected.environment)}</p>{children}<button type="button" disabled={busy} onClick={onClose}>Cancelar</button></dialog>;
}
