import type { HorizonSignal } from './types'
import SignalCard from './SignalCard'
export default function HorizonSection({title, subtitle, signals}: {title: string; subtitle: string; signals: HorizonSignal[]}) {
 return <section className="horizon-window" aria-label={title}><header><h3>{title}</h3><p>{subtitle}</p></header>
  {signals.length ? signals.map(signal => <SignalCard key={signal.id} signal={signal}/>) : <p className="ws-empty">Sem sinais nesta janela e filtro.</p>}
 </section>
}
