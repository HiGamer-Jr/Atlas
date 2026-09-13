import { useId, useState } from 'react'
import type { HorizonSignal } from './types'
const kinds = { ACTION: 'Ação', RISK: 'Risco', OPPORTUNITY: 'Oportunidade', DATA_QUALITY: 'Qualidade de dados' }
export default function SignalCard({signal}: {signal: HorizonSignal}) {
 const [expanded, setExpanded] = useState(false)
 const evidenceId = useId()
 return <article className="horizon-signal" aria-label={signal.title}>
  <div className="horizon-signal-meta"><span>{kinds[signal.kind]}</span><span className={`ws-badge ${signal.severity === 'Crítico' ? 'critical' : signal.severity === 'Atenção' ? 'warning' : 'normal'}`}>{signal.severity}</span></div>
  <h4>{signal.title}</h4><p className="horizon-entity">{signal.entityLabel} {signal.entityId}</p><p>{signal.summary}</p>
  <p><strong>Impacto: </strong>{signal.impact}</p><p className="horizon-recommendation"><strong>Próxima ação: </strong>{signal.recommendation}</p>
  <button className="horizon-why" aria-label={`Por quê? ${signal.title}`} aria-expanded={expanded} aria-controls={evidenceId} onClick={() => setExpanded(!expanded)}>Por quê?</button>
  {expanded && <div id={evidenceId}><ul>{signal.evidence.map(line => <li key={line}>{line}</li>)}</ul></div>}
 </article>
}

