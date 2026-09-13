import HorizonSection from './HorizonSection'
import { useState } from 'react'
import type { DemoRecord } from '../catalog'
import { buyerConfiguration, getDemoSignals } from './demoData'
import HorizonSummary, { summaryLabels, type SummaryFilter } from './HorizonSummary'
export default function HorizonDashboard({profileId, company, unit, operationalRecords, onOpenRelated}: {
 profileId: string; company: string; unit: string; operationalRecords: DemoRecord[]; onOpenRelated: (record: DemoRecord) => void
}) {
 const [filter, setFilter] = useState<SummaryFilter | null>(null)
 const scope = profileId === 'comprador-internacional' ? 'INTERNATIONAL' : 'NATIONAL'
 const signals = getDemoSignals(scope).filter(s => s.company === company && (unit === 'Todas as unidades' || s.unit === unit))
 const statusFor = {ATTENTION: 'Crítico', FOLLOW_UP: 'Atenção', ON_TRACK: 'Em dia'} as const
 const counts = {
  ATTENTION: signals.filter(s => s.severity === 'Crítico').length + operationalRecords.filter(r => r.status === 'Crítico').length,
  FOLLOW_UP: signals.filter(s => s.severity === 'Atenção').length + operationalRecords.filter(r => r.status === 'Atenção').length,
  ON_TRACK: signals.filter(s => s.severity === 'Em dia').length + operationalRecords.filter(r => r.status === 'Em dia').length,
  HORIZON: signals.filter(s => s.window !== 'TODAY').length,
 }
 const visibleSignals = signals.filter(s => !filter || (filter === 'HORIZON' ? s.window !== 'TODAY' : s.severity === statusFor[filter]))
 const visibleRecords = operationalRecords.filter(r => !filter || (filter !== 'HORIZON' && r.status === statusFor[filter]))
 return <div className="horizon-dashboard">
  <section className="horizon-indicators" aria-label="Indicadores do comprador">
   <div><strong>{buyerConfiguration[scope].label}</strong><p>Um novo horizonte para o seu negócio.</p></div>
   {signals.length ? <dl>{buyerConfiguration[scope].indicators.map(indicator => <div key={indicator.label}><dt>{indicator.label}</dt><dd>{indicator.value}</dd></div>)}</dl> : <p>Sem dados demonstrativos neste contexto.</p>}
   <small>Valores de exemplo · Sem atualização ao vivo</small>
  </section>
  <HorizonSummary counts={counts} activeFilter={filter} onFilterChange={value => setFilter(filter === value ? null : value)}/>
  <section className="ws-panel" aria-label="Central de atenção">
   <div className="ws-panel-title"><div><h2>Central de atenção</h2><p>{filter ? summaryLabels[filter] : 'Prioridades e próximos passos da sua operação.'}</p></div>{filter && <button onClick={() => setFilter(null)}>Limpar filtro</button>}</div>
   <div className="horizon-windows">
    <HorizonSection title="Hoje" subtitle="Ações que precisam começar agora." signals={visibleSignals.filter(s => s.window === 'TODAY')}/>
    <HorizonSection title="Próximos 1–7 dias" subtitle="Riscos antes do próximo recebimento." signals={visibleSignals.filter(s => s.window === 'DAYS_1_7')}/>
    <HorizonSection title="Horizonte 7–30 dias" subtitle="Oportunidades para preparar o próximo ciclo." signals={visibleSignals.filter(s => s.window === 'DAYS_7_30')}/>
   </div>
   <div className="ws-attention">{visibleRecords.map(r => <button key={r.id} onClick={() => onOpenRelated(r)}><div><strong>{r.title}</strong><small>{r.unit} · {r.detail}</small></div><span>{r.status}</span></button>)}</div>
   {!visibleSignals.length && !visibleRecords.length && <p className="ws-empty">Nenhum item neste contexto e filtro.</p>}
  </section>
 </div>
}


