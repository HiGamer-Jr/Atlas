import { getDemoSignals } from './demoData'
export default function HorizonDashboard({profileId, company, unit}: {profileId: string; company: string; unit: string}) {
 const scope = profileId === 'comprador-internacional' ? 'INTERNATIONAL' : 'NATIONAL'
 const signals = getDemoSignals(scope).filter(s => s.company === company && (unit === 'Todas as unidades' || s.unit === unit))
 return <section aria-label="Horizon">{signals.map(s => <article key={s.id}><h2>{s.title}</h2><p>{s.entityLabel} {s.entityId}</p><p>{s.summary}</p></article>)}</section>
}
