import { useMemo, useState } from 'react'
import { demoProjects, getProjectMetrics, type ProjectRecord } from './projectCatalog'
import './ProjectsModule.css'

type ProjectsModuleProps = {
  company: string
  unit: string
  section: string
}

const currency = new Intl.NumberFormat('pt-BR', {
  style: 'currency',
  currency: 'BRL',
  maximumFractionDigits: 0
})

function formatDate(value: string) {
  return new Date(`${value}T12:00:00`).toLocaleDateString('pt-BR')
}

export default function ProjectsModule({ company, unit, section }: ProjectsModuleProps) {
  const [selected, setSelected] = useState<ProjectRecord | null>(null)

  const projects = useMemo(
    () => demoProjects.filter(project =>
      project.company === company &&
      (unit === 'Todas as unidades' || project.unit === unit)
    ),
    [company, unit]
  )

  const metrics = getProjectMetrics(projects)
  const variance = metrics.totalProjectedCost - metrics.totalRevisedBudget
  const portfolioMode = section === 'Portfólio de Obras'

  if (selected) {
    const delayDays = Math.round(
      (new Date(selected.projectedEnd).getTime() - new Date(selected.plannedEnd).getTime()) /
      86400000
    )
    const costVariance = selected.projectedFinalCost - selected.revisedBudget

    return (
      <section className="projects-module"><p className="projects-demo">Foundation · dados demonstrativos</p>
        <button className="projects-back" onClick={() => setSelected(null)}>
          ← Voltar ao portfólio
        </button>

        <div className="projects-detail-head">
          <div>
            <span>{selected.id}</span>
            <h2>{selected.name}</h2>
            <p>{selected.summary}</p>
          </div>
          <strong className={`projects-status status-${selected.status.toLowerCase().replaceAll(' ', '-')}`}>
            {selected.status}
          </strong>
        </div>

        <div className="projects-detail-grid">
          <article>
            <small>Progresso</small>
            <strong>{selected.actualProgress}%</strong>
            <span>Planejado {selected.plannedProgress}%</span>
          </article>
          <article>
            <small>Entrega prevista</small>
            <strong>{formatDate(selected.plannedEnd)}</strong>
            <span>Projeção {formatDate(selected.projectedEnd)}</span>
          </article>
          <article>
            <small>Desvio de prazo</small>
            <strong>{delayDays > 0 ? `+${delayDays} dias` : 'No prazo'}</strong>
            <span>Baseado na projeção atual</span>
          </article>
          <article>
            <small>Projeção de custo</small>
            <strong>{currency.format(selected.projectedFinalCost)}</strong>
            <span>{costVariance > 0 ? `+${currency.format(costVariance)}` : `${currency.format(Math.abs(costVariance))} abaixo`}</span>
          </article>
        </div>

        <div className="projects-detail-panels">
          <article>
            <h3>Cronograma</h3>
            <dl>
              <dt>Início previsto</dt><dd>{formatDate(selected.plannedStart)}</dd>
              <dt>Início real</dt><dd>{selected.actualStart ? formatDate(selected.actualStart) : 'Não iniciado'}</dd>
              <dt>Entrega prevista</dt><dd>{formatDate(selected.plannedEnd)}</dd>
              <dt>Entrega projetada</dt><dd>{formatDate(selected.projectedEnd)}</dd>
            </dl>
          </article>
          <article>
            <h3>Orçamento</h3>
            <dl>
              <dt>Aprovado</dt><dd>{currency.format(selected.approvedBudget)}</dd>
              <dt>Revisado</dt><dd>{currency.format(selected.revisedBudget)}</dd>
              <dt>Comprometido</dt><dd>{currency.format(selected.committedCost)}</dd>
              <dt>Realizado</dt><dd>{currency.format(selected.realizedCost)}</dd>
              <dt>Projeção final</dt><dd>{currency.format(selected.projectedFinalCost)}</dd>
            </dl>
          </article>
          <article>
            <h3>Gestão</h3>
            <dl>
              <dt>Responsável</dt><dd>{selected.manager}</dd>
              <dt>Unidade</dt><dd>{selected.unit}</dd>
              <dt>Riscos abertos</dt><dd>{selected.riskCount}</dd>
              <dt>Decisões pendentes</dt><dd>{selected.decisionCount}</dd>
            </dl>
          </article>
        </div>
      </section>
    )
  }

  return (
    <section className="projects-module"><p className="projects-demo">Foundation · dados demonstrativos</p>
      <div className="projects-heading">
        <div>
          <span className="projects-eyebrow">OBRAS & PROJETOS</span>
          <h2>Obras & Projetos</h2>
          <p>Prazo, custo e execução no mesmo horizonte operacional.</p>
        </div>
        <span className="projects-context">{projects.length} obras no contexto</span>
      </div>

      {!portfolioMode && (
        <div className="projects-metrics">
          <article><span>Obras ativas</span><strong>{metrics.active}</strong><small>Em execução neste contexto</small></article>
          <article><span>Em risco</span><strong>{metrics.atRisk}</strong><small>Exigem acompanhamento</small></article>
          <article><span>Atrasadas</span><strong>{metrics.delayed}</strong><small>Prazo projetado comprometido</small></article>
          <article>
            <span>Projeção financeira</span>
            <strong>{currency.format(metrics.totalProjectedCost)}</strong>
            <small>{variance > 0 ? `${currency.format(variance)} acima do revisado` : 'Dentro do orçamento revisado'}</small>
          </article>
        </div>
      )}

      <div className="projects-panel">
        <div className="projects-panel-head">
          <div>
            <h3>{portfolioMode ? 'Portfólio de Obras' : 'Obras em foco'}</h3>
            <p>Acompanhe progresso, prazo, custo e riscos.</p>
          </div>
        </div>

        <div className="projects-list">
          {projects.map(project => (
            <button key={project.id} onClick={() => setSelected(project)}>
              <div>
                <span className="projects-id">{project.id}</span>
                <strong>{project.name}</strong>
                <small>{project.manager} · {project.unit}</small>
              </div>
              <div className="projects-progress">
                <span>{project.actualProgress}%</span>
                <small>planejado {project.plannedProgress}%</small>
              </div>
              <div>
                <span>{formatDate(project.projectedEnd)}</span>
                <small>entrega projetada</small>
              </div>
              <div>
                <span>{currency.format(project.projectedFinalCost)}</span>
                <small>custo final projetado</small>
              </div>
              <span className={`projects-status status-${project.status.toLowerCase().replaceAll(' ', '-')}`}>
                {project.status}
              </span>
              <span aria-hidden="true">→</span>
            </button>
          ))}
          {projects.length === 0 && <p className="projects-empty">Nenhuma obra encontrada neste contexto.</p>}
        </div>
      </div>
    </section>
  )
}
