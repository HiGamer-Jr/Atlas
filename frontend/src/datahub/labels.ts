const labels:Record<string,string>={RECEIVED:'Recebida',VALIDATING:'Em validação',READY_FOR_CONFIRMATION:'Pronta para confirmação',REJECTED:'Dados rejeitados',EXPIRED:'Preview expirado',COMMITTED:'Importação confirmada',FAILED:'Falha técnica'};
export function stateLabel(status:string){return labels[status]??'Indisponível';}
