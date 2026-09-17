import { getExecutiveOverview } from './overviewData'
import './ExecutiveDashboard.css'

const number = new Intl.NumberFormat('pt-BR', {maximumFractionDigits: 2})
const money = (value: number) => value >= 1000000
  ? `R$ ${number.format(value / 1000000)} mi`
  : value >= 1000 ? `R$ ${number.format(value / 1000)} mil` : `R$ ${number.format(value)}`
const months = ['Jan', 'Fev', 'Mar', 'Abr', 'Mai', 'Jun']

type Props = { company: string; unit: string; profileName: string }

export default function ExecutiveDashboard({company, unit, profileName}: Props) {
  const data = getExecutiveOverview(company, unit)
  const indicators = data ? [
    ['Capital em excesso de estoque', money(data.excessCapital), 'Potencial de capital a liberar'],
    ['Processos em risco', String(data.criticalProcesses + data.attentionProcesses), `${data.criticalProcesses} críticos · ${data.attentionProcesses} em atenção`],
    ['Economia/ganho identificado', money(data.potentialSavings), 'Potencial estimado, não realizado'],
    ['Cobertura média', `${data.coverageDays} dias`, 'Referência demonstrativa: 30–45 dias'],
    ['Compras em andamento', String(data.activePurchases), `${data.pendingApprovals} aguardando aprovação`],
    ['Valor em compras', money(data.purchaseValue), 'Total do semestre demonstrativo'],
    ['Estoque consolidado', `${number.format(data.inventoryUnits)} un.`, unit === 'Todas as unidades' ? 'Unidades do contexto selecionado' : unit],
    ['Importações em trânsito', String(data.importsInTransit), 'Processos em acompanhamento'],
    ['Lead time', `${data.leadTimeDays} dias`, 'Da aprovação ao recebimento'],
    ['Compras fora do planejado', `${data.outsidePlanPercent}%`, 'Participação no valor comprado'],
  ] : []
  const maxPurchase = data ? Math.max(...data.monthlyPurchases) : 0

  return <div className="executive-dashboard">
    <header className="executive-heading">
      <div>
        <p className="ws-eyebrow">SUA OPERAÇÃO, EM PERSPECTIVA</p>
        <h1>Panorama executivo<span>.</span></h1>
        <div className="executive-profile"><span className="executive-profile-dot" aria-hidden="true" />{profileName}</div>
        <p>Capital, risco e oportunidades em uma mesma decisão.</p>
      </div>
      <div className="executive-period"><strong>{unit}</strong><span>1º semestre de 2026 · Demonstração</span></div>
    </header>
    {data ? <>
      <section className="executive-indicators" aria-label="Indicadores executivos">
        {indicators.map(([label, value, caption], index) => <article key={label} aria-label={label} className={index < 4 ? 'executive-featured' : undefined}>
          <h2>{label}</h2><strong>{value}</strong><p>{caption}</p>
        </article>)}
      </section>
      <div className="executive-panels">
        <section className="executive-panel executive-purchases" aria-label="Compras e estoque">
          <div className="executive-panel-heading"><h2>Compras realizadas por mês</h2><span>R$ mil</span></div>
          <ol className="executive-chart" aria-label="Compras realizadas por mês em milhares de reais">
            {data.monthlyPurchases.map((value, index) => <li key={months[index]}>
              <span className="executive-chart-value">{number.format(value / 1000)}</span>
              <div className="executive-chart-track" aria-hidden="true"><div className="executive-chart-bar" style={{height: `${maxPurchase ? value / maxPurchase * 100 : 0}%`}} /></div>
              <span>{months[index]}</span>
            </li>)}
          </ol>
          <p className="executive-chart-caption">{money(data.purchaseValue)} no semestre · {months[data.monthlyPurchases.indexOf(maxPurchase)]} concentra o maior desembolso.</p>
          <section className="executive-health" aria-label="Saúde do estoque">
            <div className="executive-panel-heading"><h2>Saúde do estoque</h2><strong>{data.stockHealth[0]}% em equilíbrio</strong></div>
            <div className="executive-health-track" aria-hidden="true">{data.stockHealth.map((value, index) => <span key={index} className={`health-${index}`} style={{width:`${value}%`}} />)}</div>
            <p><span>{data.stockHealth[0]}% equilibrado</span><span>{data.stockHealth[1]}% atenção</span><span>{data.stockHealth[2]}% crítico</span></p>
          </section>
        </section>
        <section className="executive-panel executive-priorities" aria-label="O que precisa da sua atenção">
          <div className="executive-panel-heading"><h2>O que precisa da sua atenção</h2><span>PRIORIDADES</span></div>
          <article className="executive-priority priority-critical">
            <div><strong><span aria-hidden="true">△</span> Crítico</strong><small>Supply Chain · hoje</small></div>
            <h3>Abastecimento em risco</h3>
            <p>{data.criticalProcesses} processos críticos podem afetar a disponibilidade de produtos.</p>
            <p><b>Próximo passo:</b> Alinhar um plano de contingência {profileName === 'Diretoria' ? 'com a coordenação' : 'com os responsáveis'}.</p>
          </article>
          <article className="executive-priority priority-warning">
            <div><strong><span aria-hidden="true">ⓘ</span> Atenção</strong><small>Estoque e Compras · esta semana</small></div>
            <h3>Capital parado em estoque</h3>
            <p>{money(data.excessCapital)} acima da cobertura de referência.</p>
            <p><b>Próximo passo:</b> Avaliar redistribuição antes de autorizar novas compras.</p>
          </article>
          <article className="executive-priority priority-healthy">
            <div><strong><span aria-hidden="true">✓</span> Saudável</strong><small>Gestão · próximo ciclo</small></div>
            <h3>{data.stockHealth[0]}% do estoque em equilíbrio</h3>
            <p>Maior parte dos itens dentro da faixa de cobertura definida.</p>
            <p><b>Próximo passo:</b> Manter o acompanhamento e revisar exceções.</p>
          </article>
        </section>
      </div>
    </> : <section className="executive-panel executive-empty"><h2>Sem dados demonstrativos neste contexto.</h2><p>Selecione outra empresa ou unidade para explorar o panorama.</p></section>}
    <p className="executive-disclaimer">Dados fictícios para demonstração · sem atualização ao vivo. Indicadores referentes a {company}.</p>
  </div>
}
