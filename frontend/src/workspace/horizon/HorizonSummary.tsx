import { summaryLabels, type SummaryFilter } from './summaryFilters'
export default function HorizonSummary({counts, activeFilter, onFilterChange, controlsId}: {
 controlsId: string; counts: Record<SummaryFilter, number>; activeFilter: SummaryFilter | null; onFilterChange: (filter: SummaryFilter) => void
}) {
 return <div className="ws-metrics horizon-summary">{(Object.keys(summaryLabels) as SummaryFilter[]).map(filter =>
  <button key={filter} className="ws-metric" aria-controls={controlsId} aria-pressed={activeFilter === filter} onClick={() => onFilterChange(filter)}>
   <span>{summaryLabels[filter]}</span><strong>{counts[filter]}</strong><small>{filter === 'HORIZON' ? 'Projeções de 1 a 30 dias' : 'Filtrar central de atenção'}</small>
  </button>)}</div>
}
