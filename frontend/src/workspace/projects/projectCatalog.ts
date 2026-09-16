/** Fictional demonstration data for HiAtlas Obras Foundation. */
export type ProjectStatus =
  | 'Planejada'
  | 'Em andamento'
  | 'Em risco'
  | 'Atrasada'
  | 'Concluída'

export type ProjectRecord = {
  id: string
  name: string
  company: string
  unit: string
  manager: string
  status: ProjectStatus
  plannedStart: string
  actualStart?: string
  plannedEnd: string
  projectedEnd: string
  plannedProgress: number
  actualProgress: number
  approvedBudget: number
  revisedBudget: number
  committedCost: number
  realizedCost: number
  projectedFinalCost: number
  riskCount: number
  decisionCount: number
  summary: string
}

export type ProjectMetrics = {
  active: number
  atRisk: number
  delayed: number
  totalRevisedBudget: number
  totalProjectedCost: number
}

export const demoProjects: ProjectRecord[] = [
  {
    id: 'OBR-2026-014',
    name: 'Ampliação CD Bauru',
    company: 'Aurora Distribuição',
    unit: 'CD Sul',
    manager: 'Marcos Almeida',
    status: 'Em risco',
    plannedStart: '2026-08-03',
    actualStart: '2026-08-05',
    plannedEnd: '2027-01-20',
    projectedEnd: '2027-01-28',
    plannedProgress: 48,
    actualProgress: 42,
    approvedBudget: 2500000,
    revisedBudget: 2640000,
    committedCost: 1720000,
    realizedCost: 1340000,
    projectedFinalCost: 2780000,
    riskCount: 5,
    decisionCount: 3,
    summary: 'Estrutura metálica e abastecimento de aço exigem acompanhamento de prazo e custo.'
  },
  {
    id: 'OBR-2026-009',
    name: 'Retrofit Loja Centro',
    company: 'Aurora Distribuição',
    unit: 'Loja Centro',
    manager: 'Fernanda Costa',
    status: 'Em andamento',
    plannedStart: '2026-07-15',
    actualStart: '2026-07-15',
    plannedEnd: '2026-10-30',
    projectedEnd: '2026-10-30',
    plannedProgress: 71,
    actualProgress: 73,
    approvedBudget: 1320000,
    revisedBudget: 1370000,
    committedCost: 1040000,
    realizedCost: 910000,
    projectedFinalCost: 1350000,
    riskCount: 1,
    decisionCount: 0,
    summary: 'Execução acima do progresso planejado e projeção financeira dentro do orçamento revisado.'
  },
  {
    id: 'OBR-2026-018',
    name: 'Implantação Centro Logístico',
    company: 'Horizonte Industrial',
    unit: 'Matriz',
    manager: 'Ricardo Nunes',
    status: 'Atrasada',
    plannedStart: '2026-06-01',
    actualStart: '2026-06-06',
    plannedEnd: '2026-12-18',
    projectedEnd: '2027-01-09',
    plannedProgress: 61,
    actualProgress: 49,
    approvedBudget: 4100000,
    revisedBudget: 4280000,
    committedCost: 3310000,
    realizedCost: 2890000,
    projectedFinalCost: 4520000,
    riskCount: 7,
    decisionCount: 4,
    summary: 'Atraso acumulado em infraestrutura pressiona a data final e a projeção de custos.'
  },
  {
    id: 'OBR-2026-021',
    name: 'Adequação Área de Expedição',
    company: 'Aurora Distribuição',
    unit: 'CD Sul',
    manager: 'Juliana Prado',
    status: 'Em risco',
    plannedStart: '2026-09-01',
    actualStart: '2026-09-02',
    plannedEnd: '2026-11-28',
    projectedEnd: '2026-12-04',
    plannedProgress: 22,
    actualProgress: 18,
    approvedBudget: 2950000,
    revisedBudget: 3100000,
    committedCost: 1610000,
    realizedCost: 880000,
    projectedFinalCost: 3000000,
    riskCount: 4,
    decisionCount: 2,
    summary: 'Dependências de fornecedores e liberações internas podem deslocar próximas etapas.'
  },
  {
    id: 'OBR-2026-024',
    name: 'Nova Área de Treinamento',
    company: 'Horizonte Industrial',
    unit: 'Matriz',
    manager: 'Paulo Lima',
    status: 'Planejada',
    plannedStart: '2026-10-05',
    plannedEnd: '2027-02-12',
    projectedEnd: '2027-02-12',
    plannedProgress: 0,
    actualProgress: 0,
    approvedBudget: 980000,
    revisedBudget: 980000,
    committedCost: 180000,
    realizedCost: 0,
    projectedFinalCost: 960000,
    riskCount: 0,
    decisionCount: 1,
    summary: 'Obra em planejamento, com orçamento-base aprovado e mobilização ainda não iniciada.'
  }
]

export function getProjectMetrics(projects: ProjectRecord[]): ProjectMetrics {
  const activeProjects = projects.filter(project =>
    ['Em andamento', 'Em risco', 'Atrasada'].includes(project.status)
  )

  return {
    active: activeProjects.length,
    atRisk: projects.filter(project => project.status === 'Em risco').length,
    delayed: projects.filter(project => project.status === 'Atrasada').length,
    totalRevisedBudget: projects.reduce((sum, project) => sum + project.revisedBudget, 0),
    totalProjectedCost: projects.reduce((sum, project) => sum + project.projectedFinalCost, 0)
  }
}
