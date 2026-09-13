import type { HorizonSignal, PurchaseScope } from './types'
const signals: HorizonSignal[] = [
 { id: 'int-free-time', purchaseScope: 'INTERNATIONAL', window: 'TODAY', kind: 'ACTION', severity: 'Crítico', title: 'Free Time crítico', summary: 'Container disponível em Santos: rolamentos e válvulas industriais.', impact: 'Devolução após amanhã pode gerar US$ 150 por dia de demurrage.', recommendation: 'Confirmar retirada hoje e reservar descarga e devolução do vazio.', evidence: ['Free Time termina amanhã às 18h; tarifa demonstrativa de US$ 150/dia.', 'Descarga exige 8 horas e o transportador ainda não confirmou a coleta.'], entityLabel: 'Container', entityId: 'MSCU1234567', company: 'Aurora Distribuição', unit: 'Matriz' },
 { id: 'nac-bauru', purchaseScope: 'NATIONAL', window: 'TODAY', kind: 'ACTION', severity: 'Crítico', title: 'CD Bauru · família Aço', summary: 'Carga rodoviária em trânsito com perfis, juntas e cantoneiras.', impact: 'Cobertura de 3 dias contra ETA em 5 dias: risco de ruptura por 2 dias.', recommendation: 'Confirmar antecipação com a transportadora e avaliar transferência para Bauru.', evidence: ['Estoque disponível: 300 peças; consumo médio: 100 peças/dia.', 'Carga já expedida; ETA em 5 dias para o CD Bauru.'], entityLabel: 'Carga', entityId: 'NAC-2026-01842', company: 'Aurora Distribuição', unit: 'Matriz' },
]
export function getDemoSignals(scope: PurchaseScope): HorizonSignal[] {
 return signals.filter(signal => signal.purchaseScope === scope)
}
