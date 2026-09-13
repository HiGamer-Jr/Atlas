export type PurchaseScope = 'NATIONAL' | 'INTERNATIONAL'
export type HorizonWindow = 'TODAY' | 'DAYS_1_7' | 'DAYS_7_30'
export type SignalKind = 'ACTION' | 'RISK' | 'OPPORTUNITY' | 'DATA_QUALITY'
export type HorizonSignal = {
 id: string; purchaseScope: PurchaseScope; window: HorizonWindow; kind: SignalKind
 severity: 'Crítico' | 'Atenção' | 'Em dia'; title: string; summary: string
 impact: string; recommendation: string; evidence: string[]
 entityLabel: string; entityId: string; company: string; unit: string
}
